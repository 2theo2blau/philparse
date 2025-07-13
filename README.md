# Philosophical Text Analysis and Knowledge Graph Construction

## Concept Proposal

This project aims to create a system for deep analysis of philosophical texts. The core idea is to transform unstructured text into a structured, sequence-aware knowledge graph. This graph will not only represent the entities and concepts within the text but also preserve the logical flow and argumentative structure. By doing so, we can enable new forms of interaction with and analysis of these complex texts.

The intended use case is to provide a tool for scholars, students, and enthusiasts of philosophy to:

- **Visualize the argumentative structure of a text:** See how arguments are built, what premises they rely on, and how they relate to other arguments.
- **Perform logical validation:** Check for inconsistencies, circular reasoning, or other logical fallacies within the text.
- **Gain granular insights:** Ask specific questions about the text and receive precise answers based on the knowledge graph. For example, "What is the basis for Kant's concept of the categorical imperative?" or "How does Searle's view on intentionality differ from Dennett's?"
- **Compare and contrast different philosophical systems:** By creating knowledge graphs for multiple texts, we can compare their structures, identify common themes, and highlight key differences.

This approach goes beyond simple keyword extraction or topic modeling. It seeks to understand the *meaning* of the text by representing it in a way that is both human-readable and machine-interpretable.

## Current Project Status

This project is currently in the **alpha** stage. The backend is partially implemented, but there is still much work to be done. The frontend is not yet started.

### Backend

The backend is capable of:

- Uploading and performing OCR on PDF documents.
- Parsing the text to identify chapters, sections, and paragraphs.
- Constructing a basic knowledge graph using an LLM.
- Storing the graph in a `pgvector` database.

However, the following features are still under development:

- **Logical validation:** The system cannot yet check for logical fallacies.
- **Advanced querying:** The API for querying the knowledge graph is still very basic.
- **Metagraph generation:** The metagraph is not yet fully implemented.

### Frontend

There is currently no frontend for this project. All interaction with the system must be done through the API.

## Features

- **Document Upload and OCR**: Upload PDF documents and have them automatically converted to text using OCR.
- **Text Parsing**: The raw text is parsed to identify structural elements like chapters, sections, paragraphs, and footnotes.
- **Knowledge Graph Construction**: An LLM is used to analyze the text and extract atoms (basic units of meaning) and the relationships between them. This information is used to build a detailed knowledge graph.
- **Metagraph Generation**: A higher-level "metagraph" is created by summarizing chapters and sections, providing a bird's-eye view of the document's structure and content.
- **API for Data Access**: A FastAPI-based API provides endpoints for managing documents, running the processing pipeline, and querying the knowledge graph.
- **Vector Database**: `pgvector` is used to store and query text embeddings, enabling semantic search and other advanced features.

## Getting Started

This project is not yet ready for use. The `TODO` section outlines the next steps for development.

## TODO

- **Containerization:**
  - Write a `Dockerfile` for the application.
  - Create a `docker-compose.yml` file to manage the application and the PostgreSQL instance.
- **Semantic Search:**
  - Implement semantic search features using the stored embeddings.
  - Add API endpoints for performing semantic searches.
- **Embedding Operations:**
  - Implement operations on embeddings, such as finding similar atoms or calculating the distance between concepts.

## Project Structure

```
.
├── postgres/
│   └── init/
│       └── PGVECTOR_INIT.SQL  # SQL script for database initialization
├── src/
│   ├── api/
│   │   └── api.py             # FastAPI application
│   ├── database/
│   │   └── pgvector.py        # Database client for pgvector
│   ├── graph/
│   │   ├── construct_graph.py # Logic for building the knowledge graph
│   │   └── metagraph.py       # Logic for building the metagraph
│   ├── llm/
│   │   └── llm_client.py      # Client for interacting with the LLM
│   ├── models/
│   │   ├── ontology.json      # Defines the types of relationships in the graph
│   │   ├── schema.json        # JSON schema for the data
│   │   └── taxonomy.json      # Defines the types of atoms in the graph
│   └── preprocessing/
│       ├── clean.py           # Text cleaning utilities
│       ├── ocr.py             # OCR functionality
│       └── parse.py           # Text parsing and structuring
├── texts/                     # Sample texts for testing
└── README.md                  # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## License

This project is licensed under the terms of the LICENSE file.
