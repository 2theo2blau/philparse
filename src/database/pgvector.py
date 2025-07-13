import asyncio
import asyncpg
import numpy as np
from typing import List, Optional, Any, Dict, Union
from contextlib import asynccontextmanager
import logging
import os

logger = logging.getLogger(__name__)

class PGVectorConfig:
    host: str = "localhost"
    port: int = 5432
    database: str = "philparse-vectordb"
    user: str = "pgvec"
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

    async def initialize(self):
        if self._initialized:
            return
        
        try:
            self.pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                timeout=self.config.timeout,
                server_settings=self.config.server_settings,
            )

            await self._setup_pgvector()
            self._initialized = True
            logger.info("PostgreSQL database connection initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL database connection: {e}")
            raise

    async def add_vector(self, table_name: str, id: str, vector: np.ndarray):
        async with self.pool.acquire() as connection:
            await connection.execute(
                f"INSERT INTO {table_name} (id, vector) VALUES ($1, $2)",
                id,
                vector
            )
        return True
    
    async def get_vector(self, table_name: str, id: str):
        async with self.pool.acquire() as connection:
            result = await connection.fetch(
                f"SELECT vector FROM {table_name} WHERE id = $1",
                id
            )
        return result[0]["vector"] if result else None
    
    async def get_atoms_in_structure(self, structure_id: int) -> List[Dict[str, Any]]:
        query = """
        WITH RECURSIVE descendant_structures AS (
            SELECT id
            FROM document_structure
            WHERE id = $1

            UNION ALL

            SELECT ds.id
            FROM document_structure ds
            JOIN descendant_structures de ON ds.parent_id = de.id
        )
        SELECT a.*
        FROM atoms a
        WHERE a.paragraph_id IN (SELECT id FROM descendant_structures);
        """

        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, structure_id)
        
        return [dict(record) for record in records]
    
    async def add_structure_summary(self, structure_id: int, summary: str):
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE document_structure SET summary = $1 WHERE id = $2",
                summary,
                structure_id
            )
        return True
    
    async def get_structure_summary(self, structure_id: int) -> str:
        async with self.pool.acquire() as connection:
            result = await connection.fetch(
                "SELECT summary FROM document_structure WHERE id = $1",
                structure_id
            )
        return result[0]["summary"] if result else None

    async def get_paragraphs_in_structure(self, structure_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all paragraph structures within a given document structure ID,
        traversing the hierarchy downwards.
        """
        query = """
        WITH RECURSIVE descendant_structures AS (
            SELECT id
            FROM document_structure
            WHERE id = $1
            UNION ALL
            SELECT ds.id
            FROM document_structure ds
            JOIN descendant_structures de ON ds.parent_id = de.id
        )
        SELECT *
        FROM document_structure
        WHERE id IN (SELECT id FROM descendant_structures) AND type = 'paragraph'
        ORDER BY start_offset;
        """
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, structure_id)
        return [dict(record) for record in records]

    async def get_sections_in_structure(self, structure_id: int) -> List[Dict[str, Any]]:
        query = """
        WITH RECURSIVE descendant_structures AS (
            SELECT id
            FROM document_structure
            WHERE id = $1
            UNION ALL
            SELECT ds.id
            FROM document_structure ds
            JOIN descendant_structures de ON ds.parent_id = de.id
        )
        SELECT ds.*
        FROM document_structure ds
        JOIN descendant_structures de ON ds.id = de.id
        WHERE ds.type LIKE '%section%' AND ds.id != $1
        ORDER BY ds.start_offset;
        """
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, structure_id)
        return [dict(record) for record in records]

    async def get_chapters_in_document(self, document_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM document_structure WHERE document_id = $1 AND type = 'chapter' ORDER BY start_offset;"
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, document_id)
        return [dict(record) for record in records]
    
    async def get_documents(self, page: int = 1, page_size: int = 20) -> List[Dict[str, Any]]:
        """Retrieves a paginated list of documents."""
        offset = (page - 1) * page_size
        query = "SELECT id, title, created_at, status FROM documents ORDER BY created_at DESC LIMIT $1 OFFSET $2;"
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, page_size, offset)
        return [dict(record) for record in records]

    async def add_document(self, title: str, raw_content: str, parsed_content: Dict) -> int:
        """Adds a new document to the database and returns its ID."""
        async with self.pool.acquire() as connection:
            # Note: You might want to add a 'status' field to your documents table
            query = "INSERT INTO documents (title, raw_content, parsed_content) VALUES ($1, $2, $3) RETURNING id"
            doc_id = await connection.fetchval(query, title, raw_content, parsed_content)
        return doc_id

    async def update_document_parsed_content(self, document_id: int, parsed_content: Dict):
        """Updates the parsed_content JSON of a specific document."""
        async with self.pool.acquire() as connection:
            query = "UPDATE documents SET parsed_content = $1 WHERE id = $2"
            await connection.execute(query, parsed_content, document_id)
        return True

    async def get_document(self, document_id: int):
        async with self.pool.acquire() as connection:
            result = await connection.fetch(
                "SELECT * FROM documents WHERE id = $1",
                document_id
            )
        return dict(result[0]) if result else None
    
    async def add_document_structure(self, document_id: int, structure: Dict[str, Any]):
        """
        Populates the document_structure table by traversing the parsed_content JSON
        of a document.
        """
        if not structure:
            logger.warning(f"Document {document_id} has no parsed_content to build structure from.")
            return

        async def _insert_recursive(conn, element: Dict[str, Any], parent_id: Optional[int], element_type: str):
            """Recursively inserts a structure element and its children."""
            
            # Determine the correct key for child elements
            child_map = {
                'introduction': 'paragraphs',
                'chapter': 'subsections',
                'section': 'paragraphs',
                'subsection': 'paragraphs',
                'end_section': 'paragraphs'
            }
            # Default to an empty list of children
            children = []
            
            # Nested structures, like chapter -> subsections -> paragraphs
            if element_type == 'chapter':
                # First, process paragraphs directly under the chapter, if any
                for para in element.get('paragraphs', []):
                     await _insert_recursive(conn, para, parent_id, 'paragraph')
                # Then, process subsections
                children = element.get('subsections', [])
                child_type = 'subsection'

            elif element_type in ['introduction', 'section', 'end_section']:
                 children = element.get('paragraphs', [])
                 child_type = 'paragraph'
            
            elif element_type == 'subsection':
                 children = element.get('paragraphs', [])
                 child_type = 'paragraph'
            
            else: # paragraphs and other types have no children
                children = []
                child_type = ''

            # Insert the current element
            insert_data = {
                "document_id": document_id,
                "parent_id": parent_id,
                "type": element_type,
                "title": element.get("title"),
                "text_content": element.get("text"), # 'text' for paragraphs, 'content' for sections
                "start_offset": element.get("start_offset"),
                "end_offset": element.get("end_offset"),
            }

            query = """
                INSERT INTO document_structure (document_id, parent_id, type, title, text_content, start_offset, end_offset)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """
            
            new_id = await conn.fetchval(query, *insert_data.values())

            # Recursively insert children
            if children and child_type:
                for child_element in children:
                    await _insert_recursive(conn, child_element, new_id, child_type)

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                # Process introductions
                for intro in structure.get('introductions', []):
                    await _insert_recursive(connection, intro, None, 'introduction')
                
                # Process chapters, which is a dictionary
                for chapter_title, chapter_data in structure.get('chapters', {}).items():
                    # Add chapter title to chapter_data if not present
                    if 'title' not in chapter_data:
                        chapter_data['title'] = chapter_title
                    await _insert_recursive(connection, chapter_data, None, 'chapter')

                # Process end sections
                for end_section in structure.get('end_sections', []):
                    await _insert_recursive(connection, end_section, None, 'end_section')
        
        logger.info(f"Successfully populated document_structure for document {document_id}")

    async def get_document_structure_tree(self, document_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves the entire document structure as a nested tree.
        """
        query = """
        SELECT id, parent_id, type, title, start_offset, end_offset, summary
        FROM document_structure
        WHERE document_id = $1
        ORDER BY start_offset;
        """
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, document_id)

        if not records:
            return []

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

    async def add_atoms(self, atoms: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Adds atoms to the database and returns a map of graph_id -> db_id.
        """
        if not atoms:
            return {}
            
        async with self.pool.acquire() as connection:
            # Prepare data for executemany, separating graph_id
            data_to_insert = [
                (
                    atom["document_id"], atom["paragraph_id"], atom["text"],
                    atom["classification"], atom["start_offset"], atom["end_offset"]
                )
                for atom in atoms
            ]
            
            query = """
                INSERT INTO atoms (document_id, paragraph_id, text, classification, start_offset, end_offset)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """
            
            # executemany doesn't support RETURNING in the way we need.
            # We must insert one by one to get the IDs back.
            # A transaction ensures this is atomic.
            id_map = {}
            async with connection.transaction():
                for i, atom in enumerate(atoms):
                    db_id = await connection.fetchval(
                        query,
                        atom["document_id"], atom["paragraph_id"], atom["text"],
                        atom["classification"], atom["start_offset"], atom["end_offset"]
                    )
                    id_map[atom["graph_id"]] = db_id
        
        return id_map
    
    async def get_atoms_in_document(self, document_id: int, classification: Optional[str], page: int, page_size: int) -> List[Dict[str, Any]]:
        """Retrieves atoms for a document with optional filtering and pagination."""
        offset = (page - 1) * page_size
        
        if classification:
            query = "SELECT * FROM atoms WHERE document_id = $1 AND classification = $2 ORDER BY id LIMIT $3 OFFSET $4;"
            params = (document_id, classification, page_size, offset)
        else:
            query = "SELECT * FROM atoms WHERE document_id = $1 ORDER BY id LIMIT $2 OFFSET $3;"
            params = (document_id, page_size, offset)
            
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, *params)
            
        return [dict(record) for record in records]

    async def get_relationships_in_document(self, document_id: int, rel_type: Optional[str], page: int, page_size: int) -> List[Dict[str, Any]]:
        """Retrieves relationships for a document with optional filtering and pagination."""
        offset = (page - 1) * page_size
        
        if rel_type:
            query = "SELECT * FROM relationships WHERE document_id = $1 AND type = $2 ORDER BY id LIMIT $3 OFFSET $4;"
            params = (document_id, rel_type, page_size, offset)
        else:
            query = "SELECT * FROM relationships WHERE document_id = $1 ORDER BY id LIMIT $2 OFFSET $3;"
            params = (document_id, page_size, offset)
            
        async with self.pool.acquire() as connection:
            records = await connection.fetch(query, *params)
            
        return [dict(record) for record in records]

    async def get_atom_neighborhood(self, atom_id: int, depth: int) -> Dict[str, Any]:
        """
        Retrieves an atom and its neighbors up to a certain depth.
        This is a simplified version. A full recursive CTE would be more powerful.
        """
        # Get the central atom
        async with self.pool.acquire() as connection:
            center_atom_record = await connection.fetchrow("SELECT * FROM atoms WHERE id = $1", atom_id)
            if not center_atom_record:
                return None
            
            # Get connected relationships
            rel_query = "SELECT * FROM relationships WHERE source_atom_id = $1 OR target_atom_id = $1"
            relationships_records = await connection.fetch(rel_query, atom_id)
            
            # Get neighbor atom IDs
            neighbor_ids = set()
            for rel in relationships_records:
                neighbor_ids.add(rel['source_atom_id'])
                neighbor_ids.add(rel['target_atom_id'])
            
            # Fetch neighbor atoms
            neighbor_atoms_records = []
            if neighbor_ids:
                atom_query = "SELECT * FROM atoms WHERE id = ANY($1::int[])"
                neighbor_atoms_records = await connection.fetch(atom_query, list(neighbor_ids))

        return {
            "center_atom": dict(center_atom_record),
            "relationships": [dict(r) for r in relationships_records],
            "neighbor_atoms": [dict(a) for a in neighbor_atoms_records]
        }

    async def add_relationships(self, relationships: List[Dict[str, Any]]):
        async with self.pool.acquire() as connection:
            await connection.executemany(
                "INSERT INTO relationships (document_id, source_atom_id, target_atom_id, type, justification, vector) VALUES ($1, $2, $3, $4, $5, $6)",
                relationships
            )
        return True
    
    async def add_structure_summary(self, structure_id: int, summary: str):
        async with self.pool.acquire() as connection:
            await connection.execute(
                "UPDATE document_structure SET summary = $1 WHERE id = $2",
                summary,
                structure_id
            )
        return True
    
    async def get_structure_summary(self, structure_id: int) -> str:
        async with self.pool.acquire() as connection:
            result = await connection.fetch(
                "SELECT summary FROM document_structure WHERE id = $1",
                structure_id
            )
        return result[0]["summary"] if result else None