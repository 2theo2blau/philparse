from src.llm.llm_client import LLMClient
from src.database.pgvector import PGVector
from src.graph.metagraph import Metagraph
from src.graph.construct_graph import GraphConstructor
from src.preprocessing.parse import Parser
from src.preprocessing.ocr import OCR
from .models import *

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Query, Path
from typing import List, Optional

app = FastAPI()
router = APIRouter()

# Initialize clients
db_client = PGVector()
llm_client = LLMClient()

# ============================================================================
# 1. DOCUMENT MANAGEMENT
# ============================================================================

@router.get("/documents")
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """Retrieve paginated list of documents."""
    return await db_client.get_documents(page=page, page_size=page_size)

@router.get("/documents/{document_id}")
async def get_document(document_id: int = Path(...)):
    """Retrieve detailed information about a specific document."""
    document = await db_client.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.delete("/documents/{document_id}")
async def delete_document(document_id: int = Path(...)):
    """Delete a document and all associated data."""
    # This would need a corresponding db_client method
    # await db_client.delete_document(document_id)
    return {"message": f"Document {document_id} deletion process initiated."}


# ============================================================================
# 2. PROCESSING PIPELINE
# ============================================================================

async def run_full_pipeline(document_id: int):
    """Helper function for background processing."""
    await parse_document(document_id)
    await construct_graph(document_id)
    await summarize_document(document_id)
    # The embedding step is left manual for now

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Step 1: Upload a document, run OCR, and create the initial document record.
    Returns the new document's ID.
    """
    allowed_content_types = ["application/pdf", "image/png", "image/jpeg", "image/avif"]
    if file.content_type not in allowed_content_types:
        raise HTTPException(status_code=400, detail="File must be a PDF, PNG, JPG, or AVIF")

    ocr_client = OCR(file.file)
    document_text = ocr_client.run_ocr()
    
    # Create a basic document structure to be saved
    # The parser will add the rich structure later
    parser = Parser(document_text)
    title = parser.find_title() or "Untitled Document"

    doc_id = await db_client.add_document(
        title=title,
        raw_content=document_text,
        parsed_content={} # Initially empty
    )
    
    return {"document_id": doc_id, "message": "File uploaded and OCR processed successfully."}

@router.post("/documents/{document_id}/process")
async def process_document(
    document_id: int,
    background_tasks: BackgroundTasks
):
    """Run the full processing pipeline in the background."""
    background_tasks.add_task(run_full_pipeline, document_id)
    return {"message": "Full document processing started in the background."}

@router.post("/documents/{document_id}/parse")
async def parse_document(document_id: int):
    """
    Step 2: Parse the document's raw text to extract its structure
    and populate the document_structure table.
    """
    document = await db_client.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    parser = Parser(document["raw_content"])
    parsed_json = parser.parse()
    
    await db_client.update_document_parsed_content(document_id, parsed_json)
    await db_client.add_document_structure(document_id, parsed_json)

    return {"message": "Document parsed and structure saved."}

@router.post("/documents/{document_id}/graph")
async def construct_graph(document_id: int):
    """
    Step 3: Construct the knowledge graph from the parsed document structure.
    """
    document = await db_client.get_document(document_id)
    if not document or not document.get("parsed_content"):
        raise HTTPException(status_code=400, detail="Document has not been parsed yet.")

    graph_constructor = GraphConstructor(document["parsed_content"], llm_client)
    graph = graph_constructor.build_graph()
    
    atoms = graph_constructor.get_atoms_from_graph(graph, document_id)
    atom_id_map = await db_client.add_atoms(atoms)

    relationships = graph_constructor.get_relationships_from_graph(graph, document_id, atom_id_map)
    await db_client.add_relationships(relationships)

    return {"message": "Graph constructed and added to database"}

@router.post("/documents/{document_id}/summarize")
async def summarize_document(document_id: int):
    """
    Step 4: Create a metagraph by summarizing chapters, sections, etc.
    """
    metagraph = Metagraph(llm_client=llm_client, db_client=db_client)
    await metagraph.construct_metagraph(document_id)
    return {"message": "Metagraph constructed and summaries generated."}

@router.post("/documents/{document_id}/embed")
async def embed_document(document_id: int):
    """
    Step 5: Generate and save embeddings for all components of the document.
    (This is a placeholder for a more robust implementation)
    """
    # This would require a more complex orchestration logic
    return {"message": "Embedding process initiated for document."}


# ============================================================================
# 3. DATA RETRIEVAL
# ============================================================================

@router.get("/documents/{document_id}/structure")
async def get_document_structure(document_id: int):
    """
    Retrieve the hierarchical structure of a document (chapters, sections, etc.).
    """
    structure = await db_client.get_document_structure_tree(document_id)
    if not structure:
        raise HTTPException(status_code=404, detail="No structure found for this document. Has it been parsed?")
    return structure

@router.get("/documents/{document_id}/atoms")
async def get_document_atoms(
    document_id: int = Path(...),
    classification: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200)
):
    """Retrieve atoms for a document with filtering and pagination."""
    atoms = await db_client.get_atoms_in_document(
        document_id=document_id,
        classification=classification,
        page=page,
        page_size=page_size
    )
    return atoms

@router.get("/documents/{document_id}/relationships")
async def get_document_relationships(
    document_id: int = Path(...),
    relationship_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500)
):
    """Retrieve relationships for a document with filtering and pagination."""
    relationships = await db_client.get_relationships_in_document(
        document_id=document_id,
        rel_type=relationship_type,
        page=page,
        page_size=page_size
    )
    return relationships

@router.get("/atoms/{atom_id}/neighborhood")
async def get_atom_neighborhood(
    atom_id: int = Path(...),
    depth: int = Query(1, ge=1, le=3)
):
    """Retrieve the neighborhood of an atom (connected atoms and relationships)."""
    neighborhood = await db_client.get_atom_neighborhood(atom_id, depth)
    if not neighborhood:
        raise HTTPException(status_code=404, detail="Atom not found or has no relationships.")
    return neighborhood

app.include_router(router, prefix="/api")

