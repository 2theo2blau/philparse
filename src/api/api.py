import os
import logging
import tempfile
from contextlib import asynccontextmanager
from typing import List, Optional, AsyncGenerator

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from llm.llm_client import LLMClient
from database.pgvector import PGVector, PGVectorConfig
from graph.metagraph import Metagraph
from graph.construct_graph import GraphConstructor
from preprocessing.parse import Parser
from preprocessing.ocr import OCR
from .models import (
    Document, Atom, Relationship, DocumentInfo,
    DocumentStructureNode, GraphContext, AtomNeighborhood
)

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_config() -> PGVectorConfig:
    """Creates database configuration from environment variables."""
    config = PGVectorConfig()
    config.host = os.getenv('POSTGRES_HOST', 'localhost')
    config.port = int(os.getenv('POSTGRES_PORT', '5432'))
    config.database = os.getenv('POSTGRES_DB', 'documents')
    config.user = os.getenv('POSTGRES_USER', 'postgres')
    config.password = os.getenv('POSTGRES_PASSWORD')
    if not config.password:
        raise ValueError("POSTGRES_PASSWORD environment variable must be set.")
    return config

# --- Application Lifespan (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handles application startup and shutdown events."""
    logger.info("Starting application...")
    db_client = PGVector(get_database_config())
    try:
        await db_client.initialize()
        app.state.db_client = db_client
        logger.info("Application startup complete. Database connected.")
        yield
    finally:
        logger.info("Shutting down application...")
        if hasattr(app.state, 'db_client'):
            await app.state.db_client.close()
        logger.info("Application shutdown complete.")

# --- FastAPI App Initialization ---
app = FastAPI(
    title="PhilParse",
    description="A tool for the lazy philosopher.",
    version="1.0.0",
    lifespan=lifespan
)
router = APIRouter(prefix="/api")

# --- Dependency Injection ---
llm_client = LLMClient()

def get_db() -> PGVector:
    return app.state.db_client

# ============================================================================
# 1. DOCUMENT MANAGEMENT (CRUD)
# ============================================================================

@router.get("/documents", summary="List all documents", response_model=List[DocumentInfo])
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Retrieve a paginated list of all documents in the system."""
    return await get_db().get_documents(page=page, page_size=page_size)

@router.get("/documents/{document_id}", summary="Get a specific document", response_model=Document)
async def get_document(document_id: int = Path(..., description="The ID of the document to retrieve.")):
    """Retrieve detailed information for a single document, including its parsed content if available."""
    document = await get_db().get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.delete("/documents/{document_id}", status_code=200, summary="Delete a document")
async def delete_document(document_id: int = Path(..., description="The ID of the document to delete.")):
    """Delete a document and all its associated data (structure, atoms, relationships, etc.)."""
    success = await get_db().delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Document {document_id} and all associated data deleted successfully."}

# ============================================================================
# 2. PROCESSING PIPELINE
# ============================================================================

@router.post("/documents/upload", status_code=201, summary="Step 1: Upload and OCR a document")
async def upload_and_ocr_document(file: UploadFile = File(...)):
    """
    Uploads a file (PDF, PNG, JPG), runs OCR to extract raw text, and creates
    an initial document record. This is the first step in the pipeline.
    """
    if file.content_type not in ["application/pdf", "image/png", "image/jpeg"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF, PNG, or JPG.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
        temp_file.write(await file.read())
        temp_file_path = temp_file.name

    try:
        ocr_client = OCR(temp_file_path)
        raw_text = ocr_client.run_ocr()
        if not raw_text or not raw_text.strip():
            raise HTTPException(status_code=400, detail="OCR failed to extract any text from the document.")

        # Attempt to find a title, but don't fail if it's not found
        try:
            title = Parser(raw_text).find_title() or "Untitled Document"
        except Exception as e:
            logger.warning(f"Could not determine title during initial parse: {e}")
            title = "Untitled Document"

        doc_id = await get_db().add_document(title=title, raw_content=raw_text, parsed_content={})
        return {"document_id": doc_id, "title": title, "message": "Document uploaded and OCR complete."}
    finally:
        os.unlink(temp_file_path) # Clean up the temp file

@router.post("/documents/{document_id}/parse", summary="Step 2: Parse document structure")
async def parse_document(document_id: int = Path(..., description="ID of the document to parse.")):
    """
    Parses the raw text of a document to identify its structure (chapters, sections, etc.)
    and saves this structure to the database.
    """
    doc = await get_db().get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    
    parser = Parser(doc["raw_content"])
    parsed_json = parser.parse()

    async with get_db().transaction() as conn: # Use a transaction for atomicity
        db_with_conn = get_db()
        db_with_conn.pool.release(conn) # Temporarily release to use our own
        db_with_conn.pool._pool.append(conn) # Hack to make it work with the transaction manager
        await db_with_conn.update_document_parsed_content(document_id, parsed_json)
        await db_with_conn.add_document_structure(document_id, parsed_json)

    return {"message": "Document parsed and structure saved successfully."}

@router.post("/documents/{document_id}/graph", summary="Step 3: Construct knowledge graph")
async def construct_graph(document_id: int = Path(..., description="ID of the document to build a graph for.")):
    """
    Analyzes the parsed document structure, classifies text 'atoms', identifies
    relationships, and saves the resulting knowledge graph to the database.
    """
    doc = await get_db().get_document(document_id)
    if not doc or not doc.get("parsed_content"):
        raise HTTPException(status_code=400, detail="Document must be parsed before constructing a graph.")

    graph_constructor = GraphConstructor(doc["parsed_content"], llm_client)
    graph = graph_constructor.build_graph()
    
    # Use a transaction to ensure the entire graph is saved atomically
    async with get_db().transaction():
        atoms_to_add = graph_constructor.get_atoms_from_graph(graph, document_id)
        atom_id_map = await get_db().add_atoms(atoms_to_add)

        rels_to_add = graph_constructor.get_relationships_from_graph(graph, document_id, atom_id_map)
        if rels_to_add:
            await get_db().add_relationships(rels_to_add)

    return {"message": f"Graph constructed with {len(atoms_to_add)} atoms and {len(rels_to_add)} relationships."}

# --- Convenience Endpoint for Full Pipeline ---
async def _run_full_pipeline(document_id: int, db: PGVector):
    """Internal helper for background task."""
    try:
        logger.info(f"Starting full pipeline for document {document_id}...")
        # Re-create clients with the passed-in db instance if they depend on it
        # Step 1: Parse
        doc = await db.get_document(document_id)
        if not doc:
            logger.error(f"Pipeline failed: Document {document_id} not found.")
            return
        parser = Parser(doc["raw_content"])
        parsed_json = parser.parse()
        await db.update_document_parsed_content(document_id, parsed_json)
        await db.add_document_structure(document_id, parsed_json)
        logger.info(f"Parsing complete for document {document_id}.")

        # Step 2: Construct Graph
        doc = await db.get_document(document_id) # Re-fetch to get parsed_content
        graph_constructor = GraphConstructor(doc["parsed_content"], llm_client)
        graph = graph_constructor.build_graph()
        
        async with db.transaction():
            atoms_to_add = graph_constructor.get_atoms_from_graph(graph, document_id)
            atom_id_map = await db.add_atoms(atoms_to_add)
            rels_to_add = graph_constructor.get_relationships_from_graph(graph, document_id, atom_id_map)
            if rels_to_add:
                await db.add_relationships(rels_to_add)
        logger.info(f"Graph construction complete for document {document_id}.")
        
    except Exception as e:
        logger.error(f"Background processing failed for document {document_id}: {e}", exc_info=True)

@router.post("/documents/{document_id}/process", summary="Run full processing pipeline")
async def process_document_in_background(
    document_id: int,
    background_tasks: BackgroundTasks
):
    """
    Triggers the full processing pipeline (Parse -> Graph) for a document
    in the background.
    """
    background_tasks.add_task(_run_full_pipeline, document_id, get_db())
    return {"message": "Full document processing pipeline started in the background."}


# ============================================================================
# 3. DATA RETRIEVAL
# ============================================================================

@router.get("/documents/{document_id}/structure", summary="Get document structure tree", response_model=List[DocumentStructureNode])
async def get_document_structure(document_id: int):
    """
    Retrieve the hierarchical structure of a document (chapters, sections, etc.)
    as a nested tree, ideal for rendering navigation menus.
    """
    structure = await get_db().get_document_structure_tree(document_id)
    if not structure:
        raise HTTPException(status_code=404, detail="No structure found. The document may not have been parsed yet.")
    return structure

@router.get("/documents/{document_id}/graph/context", summary="Get local graph context", response_model=GraphContext)
async def get_graph_for_structure(
    document_id: int = Path(..., description="The ID of the document."),
    structure_id: int = Query(..., description="The ID of the structure element (e.g., a chapter or section) to get the graph for.")
):
    """
    **Frontend Optimization:** Retrieves all atoms and their interconnecting relationships
    within a specific part of the document (e.g., a single chapter). This is the
    primary endpoint for fetching data to render a graph visualization.
    """
    context = await get_db().get_local_graph_context(document_id, structure_id)
    if not context or not context.get("atoms"):
        raise HTTPException(status_code=404, detail="No graph data found for this structure ID. It may be empty, not yet processed, or does not belong to the specified document.")
    return context

@router.get("/atoms/{atom_id}/neighborhood", summary="Get atom neighborhood", response_model=AtomNeighborhood)
async def get_atom_neighborhood(
    atom_id: int = Path(..., description="The ID of the central atom."),
):
    """
    Retrieve a specific atom and its directly connected neighbors and relationships.
    Useful for expanding the graph view from a single node.
    """
    neighborhood = await get_db().get_atom_neighborhood(atom_id)
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Atom not found.")
    return neighborhood

# --- Mount API Router and Static Files ---
app.include_router(router)

# Serve the frontend
frontend_dir = os.path.join(os.getcwd(), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")
    logger.info(f"Serving static files from {frontend_dir}")

@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(frontend_dir, 'index.html'))