-- Ensure the postgres user exists (should be created by default, but just to be safe)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'postgres') THEN
        CREATE USER postgres WITH SUPERUSER;
    END IF;
END $$;

-- Create the database if it doesn't exist
SELECT 'CREATE DATABASE documents' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'documents')\gexec

-- Create the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- The 'documents' table stores the master record for each text, including the raw content
-- and the full parsed structure as a JSONB object for easy access and rehydration.
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT, -- Title can be derived from content, so it can be nullable
    raw_content TEXT NOT NULL,
    parsed_content JSONB, -- Store the result of Parser.parse() for debugging and to avoid re-parsing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);

-- The 'document_structure' table represents the hierarchical nature of the text (chapters, sections, paragraphs).
-- self-referencing parent_id allows us to represent the tree structure of the document.
CREATE TABLE IF NOT EXISTS document_structure (
    id SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_id INT REFERENCES document_structure(id) ON DELETE CASCADE,
    type TEXT NOT NULL, -- e.g., 'introduction', 'chapter', 'subsection', 'paragraph', 'end_section'
    title TEXT, -- The title of the chapter or section
    text_content TEXT, -- The text of the paragraph
    summary TEXT, -- summary of the section/chapter/paragraph used for constructing the metagraph
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    vector VECTOR(1024), -- Set to NULLABLE to allow for two-step creation/embedding process
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_structure_parent CHECK (parent_id IS NULL OR parent_id != id)
);
CREATE INDEX IF NOT EXISTS idx_structure_document_parent ON document_structure (document_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_structure_type ON document_structure (type);

-- The 'atoms' table holds the fundamental units of meaning (nodes in our graph).
CREATE TABLE IF NOT EXISTS atoms (
    id SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    paragraph_id INT NOT NULL REFERENCES document_structure(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    classification TEXT NOT NULL,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    vector VECTOR(1024), -- Set to NULLABLE to allow for two-step creation/embedding process
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_atoms_document_id ON atoms (document_id);
CREATE INDEX IF NOT EXISTS idx_atoms_classification ON atoms (classification);
CREATE INDEX IF NOT EXISTS idx_atoms_vector ON atoms USING ivfflat (vector vector_l2_ops) WITH (lists = 100);


-- The 'relationships' table defines the edges of our graph, connecting atoms.
CREATE TABLE IF NOT EXISTS relationships (
    id SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_atom_id INT NOT NULL REFERENCES atoms(id) ON DELETE CASCADE,
    target_atom_id INT NOT NULL REFERENCES atoms(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    justification TEXT,
    vector VECTOR(1024) NULLABLE, -- Set to NULLABLE to allow for two-step creation/embedding process
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_relationships_self_ref CHECK (source_atom_id != target_atom_id)
);
CREATE INDEX IF NOT EXISTS idx_relationships_source_target ON relationships (source_atom_id, target_atom_id);
CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships (type);


-- The 'notes' table stores the content of numbered endnotes or footnotes found in the text.
CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    note_identifier TEXT NOT NULL, -- e.g., '1', 'iv', 'a'. Not necessarily an integer.
    text_content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, note_identifier)
);

-- The 'note_references' table links the notes to their specific locations in the text.
-- A single note can be referenced multiple times.
CREATE TABLE IF NOT EXISTS note_references (
    id SERIAL PRIMARY KEY,
    note_id INT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_note_references_note_id ON note_references (note_id);


-- The 'bibliography_entries' table stores detailed information for each source in the bibliography.
CREATE TABLE IF NOT EXISTS bibliography_entries (
    id SERIAL PRIMARY KEY,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entry_key TEXT NOT NULL, -- e.g., 'author_year' like 'williamson_2007a'
    full_text TEXT NOT NULL,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, entry_key)
);

-- The 'intext_citations' table links bibliography entries to their reference points in the text.
CREATE TABLE IF NOT EXISTS intext_citations (
    id SERIAL PRIMARY KEY,
    bib_entry_id INT NOT NULL REFERENCES bibliography_entries(id) ON DELETE CASCADE,
    document_id INT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_info TEXT, -- e.g., 'p. 23', '99-105'
    full_citation_text TEXT NOT NULL,
    start_offset INT NOT NULL,
    end_offset INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_intext_citations_bib_entry_id ON intext_citations (bib_entry_id); 