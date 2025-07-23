import os
import logging
import tempfile
import json
from contextlib import asynccontextmanager
from typing import List, Optional, AsyncGenerator

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from llm.llm_client import LLMClient
from database.pgvector import PGVector, PGVectorConfig
# from graph.metagraph import Metagraph
from graph.construct_graph import GraphConstructor
from preprocessing.parse import Parser
from preprocessing.ocr import OCR
from src.preprocessing.metadata import MetadataExtractor
from .models import (
    Document, Atom, Relationship, DocumentInfo,
    DocumentStructureNode, GraphContext, AtomNeighborhood, GraphConstructionProgress
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
        app.state.graph_constructors = {}  # For tracking progress
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

# --- CORS Middleware ---
# Allows the frontend to communicate with this API on any port.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://127.0.0.1:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@router.post("/documents/process", status_code=201, summary="Step 1 & 2: Upload, OCR, and Parse")
async def process_document(file: UploadFile = File(...), db: PGVector = Depends(get_db)):
    """
    Uploads a file, determines the best parsing strategy (metadata or regex),
    runs OCR, parses the document structure, and saves it to the database.
    This single endpoint replaces the separate upload and parse steps.
    """
    if file.content_type not in ["application/pdf"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF is supported for this endpoint.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        # 1. Decide on parsing strategy: Metadata-first or Regex-fallback
        metadata_extractor = MetadataExtractor(tmp_path)
        chapter_ranges = metadata_extractor.get_chapter_page_ranges()
        
        ocr_processor = OCR(tmp_path)
        parser: Parser
        parsed_json: dict
        title: str

        if chapter_ranges:
            logger.info(f"Strategy: Metadata-based parsing for {file.filename}")
            chapters_with_text = ocr_processor.run_ocr_on_chapters(chapter_ranges)
            if not chapters_with_text:
                raise HTTPException(status_code=500, detail="OCR processing failed for all chapters.")
            
            # Reconstruct full text for context-dependent parsing and to store in the database
            full_text = "\n\n".join([chapter['text'] for chapter in chapters_with_text])
            title = file.filename # Use filename as title, since metadata doesn't give a document title
            
            # Initialize parser with the full reconstructed text
            parser = Parser(full_text)
            parsed_json = parser.parse(chapters_with_text=chapters_with_text)

        else:
            logger.info(f"Strategy: Regex-fallback parsing for {file.filename}")
            full_text = ocr_processor.run_ocr_on_all_pages()
            if not full_text:
                raise HTTPException(status_code=500, detail="Full document OCR failed.")
            
            parser = Parser(full_text)
            parsed_json = parser.parse()
            title = parsed_json.get("title", "Untitled Document")

        # 2. Save to database
        doc_id = await db.add_document(title=title, raw_content=full_text, parsed_content={})
        await db.update_document_and_add_structure(doc_id, parsed_json)

        return {
            "document_id": doc_id,
            "title": title,
            "message": "Document processed and saved successfully."
        }

    except Exception as e:
        logger.error(f"Error processing document {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/documents/{document_id}/graph", summary="Step 3: Construct knowledge graph", status_code=202)
async def construct_graph(
    document_id: int,
    background_tasks: BackgroundTasks
):
    """
    Triggers knowledge graph construction for a document in the background.
    Poll the `/documents/{document_id}/graph/progress` endpoint to check status.
    """
    db = get_db()
    doc = await db.get_document(document_id)
    if not doc or not doc.get("parsed_content"):
        raise HTTPException(status_code=400, detail="Document must be parsed before constructing a graph.")

    if document_id in app.state.graph_constructors:
        constructor = app.state.graph_constructors[document_id]
        if constructor.current_status in ["building", "filtering"]:
            raise HTTPException(status_code=409, detail="Graph construction is already in progress.")

    graph_constructor = GraphConstructor(doc["parsed_content"], llm_client)
    app.state.graph_constructors[document_id] = graph_constructor

    background_tasks.add_task(_run_graph_construction, document_id, db, llm_client)
    
    return {"message": "Graph construction started in the background."}


async def _run_graph_construction(document_id: int, db: PGVector, llm: LLMClient):
    """Internal helper to run graph construction in the background."""
    graph_constructor = app.state.graph_constructors.get(document_id)
    if not graph_constructor:
        logger.error(f"Could not find graph constructor for document {document_id} to run in background.")
        return

    try:
        # Step 1: Build the graph in memory
        graph = graph_constructor.build_graph()
        
        # Step 2: Prepare data for the database
        atoms_to_add = graph_constructor.get_atoms_from_graph(graph, document_id)
        
        # If no valid atoms were produced, there's nothing to add.
        if not atoms_to_add:
            logger.warning(f"Graph construction for doc {document_id} produced 0 valid atoms to add. Aborting database insertion.")
            graph_constructor.current_status = "complete_with_warnings"
            return
        
        async with db.transaction() as conn:
            # Add atoms and get the mapping from graph_id to db_id
            atom_id_map = await db._add_atoms_with_conn(conn, atoms_to_add)
            
            # Prepare relationships using the new mapping
            rels_to_add = graph_constructor.get_relationships_from_graph(graph, document_id, atom_id_map)
            
            # Add relationships within the same transaction
            if rels_to_add:
                await db._add_relationships_with_conn(conn, rels_to_add)

        logger.info(f"Graph construction and database insertion complete for document {document_id}.")

    except Exception as e:
        logger.error(f"Background graph construction failed for doc {document_id}: {e}", exc_info=True)
        if graph_constructor:
            graph_constructor.current_status = "error"


@router.get("/documents/{document_id}/graph/progress", summary="Get graph construction progress", response_model=GraphConstructionProgress)
async def get_graph_construction_progress(document_id: int):
    """
    Poll this endpoint to check the status of a graph construction process
    that was started in the background.
    """
    constructor = app.state.graph_constructors.get(document_id)
    if not constructor:
        raise HTTPException(status_code=404, detail="No graph construction process found for this document. It may not have been started or has been cleaned up.")
    
    return constructor.get_progress_info()


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
        await db.update_document_and_add_structure(document_id, parsed_json)
        logger.info(f"Parsing complete for document {document_id}.")

        # Step 2: Construct Graph
        doc = await db.get_document(document_id) # Re-fetch to get parsed_content
        graph_constructor = GraphConstructor(doc["parsed_content"], llm_client)
        app.state.graph_constructors[document_id] = graph_constructor # Track progress
        
        graph = graph_constructor.build_graph()
        
        atoms_to_add = graph_constructor.get_atoms_from_graph(graph, document_id)
        atom_id_map = await db.add_atoms(atoms_to_add)
        rels_to_add = graph_constructor.get_relationships_from_graph(graph, document_id, atom_id_map)
        if rels_to_add:
            await db.add_relationships(rels_to_add)
        logger.info(f"Graph construction complete for document {document_id}.")
        
    except Exception as e:
        logger.error(f"Background processing failed for document {document_id}: {e}", exc_info=True)
        if document_id in app.state.graph_constructors:
            app.state.graph_constructors[document_id].current_status = "error"

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