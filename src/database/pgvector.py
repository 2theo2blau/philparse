import asyncio
import asyncpg
import numpy as np
from typing import List, Optional, Any, Dict, Tuple
from contextlib import asynccontextmanager
import logging
import json

logger = logging.getLogger(__name__)

class PGVectorConfig:
    host: str = "philparse-postgres"
    port: int = 5432
    database: str = "documents"
    user: str = "postgres"
    password: str
    min_size: int = 1
    max_size: int = 1000
    timeout: int = 30
    server_settings: Optional[Dict[str, Any]] = None

class PGVector:
    def __init__(self, config: PGVectorConfig):
        self.config = config
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    # --- Connection Management & Transactions ---

    async def initialize(self):
        """Initializes the connection pool and ensures the vector extension is enabled."""
        if self._initialized:
            return
        try:
            logger.info(f"Initializing database connection to {self.config.host}:{self.config.port}/{self.config.database}")
            self.pool = await asyncpg.create_pool(
                host=self.config.host, port=self.config.port, database=self.config.database,
                user=self.config.user, password=self.config.password,
                min_size=self.config.min_size, max_size=self.config.max_size,
                timeout=self.config.timeout, server_settings=self.config.server_settings,
            )
            async with self.pool.acquire() as connection:
                await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self._initialized = True
            logger.info("PostgreSQL database connection initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL database connection: {e}")
            raise

    @asynccontextmanager
    async def transaction(self):
        """Provides a transactional context. Operations are committed on success or rolled back on error."""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                logger.debug("Beginning new transaction.")
                yield connection
                logger.debug("Committing transaction.")

    async def close(self):
        """Closes the database connection pool."""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Database connection pool closed.")

    # --- Document Operations (documents table) ---

    async def add_document(self, title: str, raw_content: str, parsed_content: Dict) -> int:
        """Adds a new document and returns its ID."""
        query = "INSERT INTO documents (title, raw_content, parsed_content) VALUES ($1, $2, $3) RETURNING id"
        parsed_content_json = json.dumps(parsed_content) if parsed_content else None
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, title, raw_content, parsed_content_json)

    async def get_document(self, document_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single document by its ID."""
        query = "SELECT * FROM documents WHERE id = $1"
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, document_id)
        if not record:
            return None
        
        doc = dict(record)
        if doc.get("parsed_content") and isinstance(doc["parsed_content"], str):
            try:
                doc["parsed_content"] = json.loads(doc["parsed_content"])
            except json.JSONDecodeError:
                logger.warning(f"Could not parse 'parsed_content' for document {document_id}")
                doc["parsed_content"] = None
        return doc

    async def get_documents(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """Retrieves a paginated list of documents."""
        offset = (page - 1) * page_size
        query = "SELECT id, title, created_at FROM documents ORDER BY created_at DESC LIMIT $1 OFFSET $2;"
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, page_size, offset)
        return [dict(r) for r in records]

    async def update_document_parsed_content(self, document_id: int, parsed_content: Dict):
        """Updates the parsed_content of a document."""
        query = "UPDATE documents SET parsed_content = $1 WHERE id = $2"
        parsed_content_json = json.dumps(parsed_content)
        async with self.pool.acquire() as conn:
            await conn.execute(query, parsed_content_json, document_id)

    async def delete_document(self, document_id: int) -> bool:
        """Deletes a document and all its associated data via cascading deletes."""
        query = "DELETE FROM documents WHERE id = $1"
        async with self.pool.acquire() as conn:
            status = await conn.execute(query, document_id)
        # "DELETE 1" means one row was deleted
        return status.endswith('1')

    # --- Structure Operations (document_structure table) ---

    async def add_document_structure(self, document_id: int, parsed_content: Dict):
        """Populates the document_structure table by traversing parsed_content."""
        if not parsed_content:
            return

        async def _insert_recursive(conn, element: Dict, parent_id: Optional[int], element_type: str):
            query = """
                INSERT INTO document_structure (document_id, parent_id, type, title, text_content, start_offset, end_offset)
                VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id
            """
            new_id = await conn.fetchval(
                query, document_id, parent_id, element_type, element.get("title"),
                element.get("text"), element.get("start_offset"), element.get("end_offset")
            )
            # Handle nested children (e.g., subsections in chapters, paragraphs in sections)
            if element_type == 'chapter':
                for sub in element.get('subsections', []):
                    await _insert_recursive(conn, sub, new_id, 'subsection')
                for para in element.get('paragraphs', []):
                    await _insert_recursive(conn, para, new_id, 'paragraph')
            elif element_type in ['introduction', 'section', 'subsection', 'end_section']:
                for para in element.get('paragraphs', []):
                    await _insert_recursive(conn, para, new_id, 'paragraph')

        async with self.transaction() as conn:
            for intro in parsed_content.get('introductions', []):
                await _insert_recursive(conn, intro, None, 'introduction')
            for title, data in parsed_content.get('chapters', {}).items():
                data['title'] = data.get('title', title)
                await _insert_recursive(conn, data, None, 'chapter')
            for end_sec in parsed_content.get('end_sections', []):
                await _insert_recursive(conn, end_sec, None, 'end_section')
        logger.info(f"Successfully populated document_structure for document {document_id}")

    async def get_document_structure_tree(self, document_id: int) -> List[Dict[str, Any]]:
        """Retrieves the entire document structure as a nested tree."""
        query = "SELECT * FROM document_structure WHERE document_id = $1 ORDER BY start_offset;"
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, document_id)
        
        nodes = {record['id']: dict(record) for record in records}
        tree = []
        for node_id, node in nodes.items():
            node['children'] = []
            parent_id = node.get('parent_id')
            if parent_id in nodes:
                nodes[parent_id]['children'].append(node)
            else:
                tree.append(node)
        return tree
    
    async def update_structure_summary(self, structure_id: int, summary: str):
        """Adds or updates the summary for a structure element."""
        query = "UPDATE document_structure SET summary = $1 WHERE id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, summary, structure_id)

    # --- Atom Operations (atoms table) ---

    async def add_atoms(self, atoms: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Adds atoms in a single transaction and returns a map of their temporary
        graph_id to their new database ID.
        """
        if not atoms:
            return {}
        
        id_map = {}
        query = """
            INSERT INTO atoms (document_id, paragraph_id, text, classification, start_offset, end_offset)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """
        async with self.transaction() as conn:
            for atom in atoms:
                db_id = await conn.fetchval(
                    query, atom["document_id"], atom["paragraph_id"], atom["text"],
                    atom["classification"], atom["start_offset"], atom["end_offset"]
                )
                id_map[atom["graph_id"]] = db_id
        return id_map

    async def get_atom(self, atom_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a single atom by its ID."""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow("SELECT * FROM atoms WHERE id = $1", atom_id)
        return dict(record) if record else None

    async def update_atom_vector(self, atom_id: int, vector: np.ndarray):
        """Updates the vector for a single atom."""
        query = "UPDATE atoms SET vector = $1 WHERE id = $2"
        async with self.pool.acquire() as conn:
            await conn.execute(query, vector, atom_id)

    # --- Relationship Operations (relationships table) ---

    async def add_relationships(self, relationships: List[Dict[str, Any]]):
        """Bulk-adds relationships to the database."""
        if not relationships:
            return
        
        # Prepare data for executemany
        data_to_insert = [
            (r["document_id"], r["source_atom_id"], r["target_atom_id"], r["type"], r["justification"])
            for r in relationships
        ]
        query = "INSERT INTO relationships (document_id, source_atom_id, target_atom_id, type, justification) VALUES ($1, $2, $3, $4, $5)"
        async with self.pool.acquire() as conn:
            await conn.executemany(query, data_to_insert)

    # --- Note & Citation Operations (notes, bibliography_entries, etc.) ---

    async def add_note(self, document_id: int, identifier: str, text: str) -> int:
        query = "INSERT INTO notes (document_id, note_identifier, text_content) VALUES ($1, $2, $3) RETURNING id"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, document_id, identifier, text)

    async def add_bibliography_entry(self, document_id: int, key: str, text: str, start: int, end: int) -> int:
        query = "INSERT INTO bibliography_entries (document_id, entry_key, full_text, start_offset, end_offset) VALUES ($1, $2, $3, $4, $5) RETURNING id"
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, document_id, key, text, start, end)

    # --- High-Level & Combined Retrieval Operations ---

    async def get_atoms_in_structure(self, structure_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all atoms within a given document structure ID (e.g., a chapter),
        traversing the hierarchy downwards.
        """
        query = """
        WITH RECURSIVE descendant_structures AS (
            SELECT id FROM document_structure WHERE id = $1
            UNION ALL
            SELECT ds.id FROM document_structure ds
            JOIN descendant_structures de ON ds.parent_id = de.id
        )
        SELECT a.* FROM atoms a
        JOIN document_structure ds ON a.paragraph_id = ds.id
        WHERE ds.id IN (SELECT id FROM descendant_structures);
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, structure_id)
        return [dict(r) for r in records]

    async def get_relationships_in_structure(self, structure_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all relationships where both source and target atoms are within
        a given document structure ID (e.g., a chapter).
        """
        query = """
        WITH RECURSIVE descendant_structures AS (
            SELECT id FROM document_structure WHERE id = $1
            UNION ALL
            SELECT ds.id FROM document_structure ds
            JOIN descendant_structures de ON ds.parent_id = de.id
        ),
        atoms_in_structure AS (
            SELECT a.id FROM atoms a
            JOIN document_structure ds ON a.paragraph_id = ds.id
            WHERE ds.id IN (SELECT id FROM descendant_structures)
        )
        SELECT r.* FROM relationships r
        WHERE r.source_atom_id IN (SELECT id FROM atoms_in_structure)
          AND r.target_atom_id IN (SELECT id FROM atoms_in_structure);
        """
        async with self.pool.acquire() as conn:
            records = await conn.fetch(query, structure_id)
        return [dict(r) for r in records]

    async def get_local_graph_context(self, document_id: int, structure_id: int) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        A high-level method to fetch all atoms and their interconnecting relationships
        for a specific part of the document (e.g., a chapter or section).
        Verifies that the structure ID belongs to the given document ID to prevent data leakage.
        Ideal for powering frontend visualizations.
        """
        # First, verify that the structure_id belongs to the document_id.
        query = "SELECT EXISTS(SELECT 1 FROM document_structure WHERE id = $1 AND document_id = $2)"
        async with self.pool.acquire() as conn:
            is_valid_request = await conn.fetchval(query, structure_id, document_id)

        if not is_valid_request:
            logger.warning(f"Access denied: structure_id {structure_id} does not belong to document_id {document_id}.")
            return None

        atoms = await self.get_atoms_in_structure(structure_id)
        relationships = await self.get_relationships_in_structure(structure_id)
        return {"atoms": atoms, "relationships": relationships}

    async def get_atom_neighborhood(self, atom_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves an atom and its direct neighbors and relationships."""
        async with self.pool.acquire() as conn:
            center_atom_rec = await conn.fetchrow("SELECT * FROM atoms WHERE id = $1", atom_id)
            if not center_atom_rec:
                return None
            
            rel_query = "SELECT * FROM relationships WHERE source_atom_id = $1 OR target_atom_id = $1"
            rel_recs = await conn.fetch(rel_query, atom_id)
            
            neighbor_ids = {r['source_atom_id'] for r in rel_recs} | {r['target_atom_id'] for r in rel_recs}
            neighbor_ids.discard(atom_id)
            
            neighbor_atom_recs = []
            if neighbor_ids:
                atom_query = "SELECT * FROM atoms WHERE id = ANY($1::int[])"
                neighbor_atom_recs = await conn.fetch(atom_query, list(neighbor_ids))

        return {
            "center_atom": dict(center_atom_rec),
            "relationships": [dict(r) for r in rel_recs],
            "neighbor_atoms": [dict(a) for a in neighbor_atom_recs]
        }