from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


# --- Base Models ---
# These models define the core fields for each data structure, used for creation.
class DocumentBase(BaseModel):
    title: Optional[str] = None
    raw_content: str
    parsed_content: Optional[Dict] = None


class DocumentStructureBase(BaseModel):
    document_id: int
    parent_id: Optional[int] = None
    type: str
    title: Optional[str] = None
    text_content: Optional[str] = None
    summary: Optional[str] = None
    start_offset: int
    end_offset: int
    vector: Optional[List[float]] = None


class AtomBase(BaseModel):
    document_id: int
    paragraph_id: int
    text: str
    classification: str
    start_offset: int
    end_offset: int
    vector: Optional[List[float]] = None


class RelationshipBase(BaseModel):
    document_id: int
    source_atom_id: int
    target_atom_id: int
    type: str
    justification: Optional[str] = None
    vector: Optional[List[float]] = None


class NoteBase(BaseModel):
    document_id: int
    note_identifier: str
    text_content: str


class NoteReferenceBase(BaseModel):
    note_id: int
    document_id: int
    start_offset: int
    end_offset: int


class BibliographyEntryBase(BaseModel):
    document_id: int
    entry_key: str
    full_text: str
    start_offset: int
    end_offset: int


class InTextCitationBase(BaseModel):
    bib_entry_id: int
    document_id: int
    page_info: Optional[str] = None
    full_citation_text: str
    start_offset: int
    end_offset: int


# --- Create Models ---
# These models are used when creating new entries via the API.
# They inherit from Base models and can be extended if creation logic differs.
class DocumentCreate(DocumentBase):
    pass


class DocumentStructureCreate(DocumentStructureBase):
    pass


class AtomCreate(AtomBase):
    pass


class RelationshipCreate(RelationshipBase):
    pass


class NoteCreate(NoteBase):
    pass


class NoteReferenceCreate(NoteReferenceBase):
    pass


class BibliographyEntryCreate(BibliographyEntryBase):
    pass


class InTextCitationCreate(InTextCitationBase):
    pass


# --- DB Read Models ---
# These models represent the data as it is stored in the database, including read-only fields.
# `from_attributes = True` allows Pydantic to work with ORM objects.
class Document(DocumentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentStructure(DocumentStructureBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Atom(AtomBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Relationship(RelationshipBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Note(NoteBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class NoteReference(NoteReferenceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BibliographyEntry(BibliographyEntryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class InTextCitation(InTextCitationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# --- API Response Models ---

class DocumentInfo(BaseModel):
    """A model for document list responses, containing summary information."""
    id: int
    title: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentStructureNode(DocumentStructure):
    """A recursive model for representing the document's hierarchical structure."""
    children: List['DocumentStructureNode'] = []


# Required for Pydantic to process the recursive model definition correctly.
DocumentStructureNode.model_rebuild()


class GraphContext(BaseModel):
    """A model representing the graph context for a part of a document."""
    atoms: List[Atom]
    relationships: List[Relationship]

    class Config:
        from_attributes = True


class AtomNeighborhood(BaseModel):
    """A model for an atom and its directly connected neighbors."""
    center_atom: Atom
    relationships: List[Relationship]
    neighbor_atoms: List[Atom]

    class Config:
        from_attributes = True