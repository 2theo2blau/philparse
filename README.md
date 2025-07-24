# Philosophical Text Analysis and Knowledge Graph Construction

## Concept Proposal

This project creates a system for deep analysis of philosophical texts by transforming unstructured documents into structured, sequence-aware knowledge graphs. The core innovation lies in decomposing text into atomic units of meaning ("atoms") and constructing locally-linked graphs that preserve both the linear progression of the original text and the logical relationships between ideas.

The system is designed for scholars, students, and enthusiasts of philosophy to:

- **Visualize argumentative structure at multiple levels:** From atomic sentence-level relationships to high-level argument flows across entire documents.
- **Preserve textual sequence while revealing logical connections:** The graph maintains the original reading order while exposing non-linear argumentative relationships.
- **Navigate complex philosophical arguments:** Through both detailed atomic-level analysis and high-level metagraph summaries.
- **Perform granular analysis:** Ask specific questions about the text and receive precise answers based on the knowledge graph structure.

This approach goes beyond keyword extraction or topic modeling by creating a formally structured representation that captures both the semantic content and argumentative logic of philosophical texts.

## Architecture Overview

### Atomic Graph Construction

The system operates on the principle of **atomic decomposition**: each paragraph is broken down into individual sentences or meaningful units (atoms), which are then classified and linked based on their logical and argumentative relationships. The key insight is that atoms are processed **sequentially within local contexts** (paragraphs and sections) while **chapters are processed in parallel**, creating naturally bounded subgraphs that correspond to self-contained arguments.

This approach produces knowledge graphs composed of many interconnected subgraphs, where each subgraph represents a logically coherent argumentative unit. The local context approach ensures that atoms can reference and build upon preceding atoms within their immediate textual vicinity, while the parallel chapter processing maintains efficiency and prevents the context window from becoming unwieldy.

### Locally-Linked Structure

The graph construction maintains the **linear progression** of the original text while simultaneously representing **self-contained arguments** within this progression. Each atom is aware of its position in the text and can form relationships with atoms that precede it in the local context, creating clusters of linked atoms that form closed subgraphs corresponding to complete argumentative units spanning paragraphs or sections.

## Current Implementation Status

The system is in **beta** stage with a mostly functional backend capable of end-to-end document processing and knowledge graph construction.

### Backend Capabilities

The system currently supports:

- **Intelligent Document Processing**: 
  - **Metadata-first parsing strategy**: Attempts to extract chapter boundaries from PDF table of contents before falling back to regex-based pattern matching
  - **OCR processing**: Converts PDF documents to structured text using Mistral's OCR API
  - **Hierarchical structure extraction**: Identifies chapters, sections, paragraphs, footnotes, and bibliography

- **Atomic Graph Construction**:
  - **Sequential atom processing**: Each sentence/meaningful unit is classified using a comprehensive taxonomy (18 categories including Claims, Premises, Definitions, etc.)
  - **Local context linking**: Atoms form relationships with preceding atoms in their immediate textual vicinity
  - **Ontology-based validation**: Relationships are validated against a formal ontology defining valid source-target pairs for each relationship type
  - **Self-contained argument detection**: The local linking approach naturally creates bounded subgraphs representing complete argumentative units

- **Database Storage**: 
  - **Hierarchical document structure**: Stores the complete document hierarchy (chapters → sections → paragraphs → atoms)
  - **Graph relationships**: Maintains atom-to-atom relationships with typed connections (Supports, Rebuts, Clarifies, etc.)
  - **Vector embeddings**: Prepared for semantic search capabilities using pgvector

- **RESTful API**: FastAPI-based endpoints for document upload, processing pipeline management, and graph querying

### In Development

- **Metadata extraction enhancement**: Currently implementing more robust PDF metadata extraction to reduce reliance on regex-based chapter detection as a fallback

## Features

### Document Processing Pipeline

1. **Upload and OCR**: PDF documents are processed using Mistral's OCR API for high-quality text extraction
2. **Intelligent Parsing Strategy**: 
   - **Primary**: Extract chapter boundaries from PDF metadata/table of contents
   - **Fallback**: Use regex patterns to identify document structure when metadata is unavailable
3. **Hierarchical Structure Extraction**: Parse chapters, sections, paragraphs, footnotes, notes, and bibliography
4. **Atomic Decomposition**: Break paragraphs into individual atoms (sentences/meaningful units) while preserving citations and complex punctuation

### Knowledge Graph Construction

1. **Sequential Classification**: Each atom is classified using a comprehensive taxonomy:
   - **Argumentative**: Claim, Premise, Conclusion, Rebuttal, Concession, Implication
   - **Definitional**: Definition, Stipulation, Example, Distinction  
   - **Attributive**: Position Statement, Quotation, Citation
   - **Structural**: Thesis, Roadmap, Problem Statement, Inquiry

2. **Local Context Linking**: Atoms form relationships with preceding atoms in their immediate vicinity using a formal relationship ontology:
   - **Logical**: Supports, Rebuts, Implies
   - **Clarifying**: Clarifies, Illustrates, Quantifies
   - **Structural**: Addresses, Outlines, Continues
   - **Attributive**: Attributes, Cites

3. **Ontology Validation**: All relationships are validated against formal rules defining valid source-target pairs for each relationship type

4. **Self-Contained Argument Formation**: The local linking approach creates bounded subgraphs where atoms within argumentative units are highly interconnected while connections across distant text portions are naturally limited

### Data Storage and Retrieval

- **Hierarchical Document Storage**: Complete document structure with offset tracking for precise location mapping
- **Graph Database**: Atoms and relationships stored with full provenance and classification metadata
- **Vector Embeddings**: Support for semantic search using pgvector (infrastructure ready, search features pending implementation)

## Project Structure

```
├── src/
│   ├── api/
│   │   ├── api.py              # FastAPI application with document processing pipeline
│   │   └── models.py           # Pydantic models for API requests/responses
│   ├── database/
│   │   └── pgvector.py         # Database client with hierarchical structure support
│   ├── graph/
│   │   ├── construct_graph.py  # Core graph construction logic with local context processing
│   │   └── metagraph.py        # Metagraph overlay construction (in development)
│   ├── llm/
│   │   ├── llm_client.py       # Mistral API client with rate limiting and validation
│   │   └── prompts/
│   │       ├── atom_graph.md   # Classification and relationship extraction prompt
│   │       └── summarize.md    # Text summarization prompt for metagraph
│   ├── models/
│   │   ├── ontology.json       # Formal relationship ontology with validation rules
│   │   ├── taxonomy.json       # Atom classification taxonomy
│   │   └── schema.json         # Complete data schema specification
│   ├── preprocessing/
│   │   ├── metadata.py         # PDF metadata extraction for chapter boundaries
│   │   ├── ocr.py              # OCR processing with chapter-aware chunking
│   │   ├── parse.py            # Text parsing with metadata-first strategy
│   │   └── clean.py            # Text cleaning and normalization utilities
│   └── semantics/
│       └── semantics.py        # Semantic analysis infrastructure (prepared for semantic search)
├── postgres/
│   └── docker/
│       ├── Dockerfile          # PostgreSQL with pgvector extension
│       └── init/
│           └── PGVECTOR_INIT.SQL # Database schema with hierarchical structure support
├── docker-compose.yml          # Complete development environment
├── Dockerfile                  # Application container
└── requirements.txt            # Python dependencies
```

## Getting Started

### Development Setup

1. **Prerequisites**: Docker and Docker Compose
2. **Environment Variables**: Set `MISTRAL_API_KEY` for OCR and LLM processing
3. **Launch**: `docker-compose up` starts the complete stack (application + PostgreSQL with pgvector)
4. **API Documentation**: Available at `http://localhost:8000/docs` when running

### Usage Pipeline

1. **Upload Document**: POST `/documents/process` with PDF file
2. **Monitor Processing**: Check parsing and structure extraction progress
3. **Construct Graph**: POST `/documents/{id}/graph` to begin knowledge graph construction
4. **Query Results**: Use various endpoints to explore the hierarchical structure and atomic graph

## TODO

### High Priority

- **Semantic Search Implementation**:
  - Complete semantic search features using stored embeddings
  - Add API endpoints for finding semantically similar atoms and concepts
  - Implement embedding-based document comparison capabilities

- **Metagraph Module Enhancement**:
  - **Argument-level summarization**: Create overlay graphs by either summarizing the contents of each self-contained argument (composed of interconnected atoms) OR selecting the conclusory/position statement that best represents each argument
  - **Cross-argument relationship detection**: Identify and represent relationships between different self-contained arguments across the document
  - **Multi-level navigation**: Enable traversal from atomic-level details to high-level argumentative structure
  - **Resource efficiency consideration**: Implement both summarization and selection approaches, where selecting conclusory statements is more resource-efficient but local summaries may yield better analytical results

### Medium Priority

- **Performance Optimization**:
  - **Resource efficiency**: Current processing is expensive (e.g., "Debating the A Priori" uses 10.5M tokens input, 1.5M tokens output)
  - **Task-specific classifier development**: Consider training specialized models on high-quality LLM outputs to reduce API costs once schema is stabilized

- **Frontend Development**:
  - **File upload interface**: Web interface for document upload and automatic processing pipeline
  - **Reader view**: Text display with atoms color-coded by classification, clickable atoms showing first-degree connections in popups (augmented reading experience)
  - **Graph visualization**: Interactive node-edge graphical interface for metagraph traversal, revealing high-level and non-local argumentative connections
  - **Multi-level navigation**: Seamless transitions between detailed atomic analysis and high-level argument structure

### Future Enhancements

- **Logical validation**: Automated detection of logical fallacies, circular reasoning, and argumentative inconsistencies
- **Cross-document analysis**: Compare argumentative structures across multiple philosophical texts
- **Export capabilities**: Generate structured summaries, argument maps, and analytical reports

## Contributing

This project represents a novel approach to computational philosophy and digital humanities. Contributions are welcome, particularly in:

- Enhancing the relationship ontology and classification taxonomies
- Improving the metagraph construction algorithms  
- Developing specialized models for philosophical text analysis
- Creating intuitive interfaces for exploring complex argumentative structures

