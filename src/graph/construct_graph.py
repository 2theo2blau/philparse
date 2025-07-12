import json
import os
import re
import nltk
from collections import deque
from ..llm.llm_client import LLMClient

class GraphConstructor:
    def __init__(self, json_doc: dict, llm_client: LLMClient, context_window_size: int = 4096):
        doc_key = list(json_doc.keys())[0]
        self.doc_data = json_doc[doc_key]

        self.title = self.doc_data.get("title", "Untitled Document")
        self.chapters = self.doc_data.get("chapters", {})
        self.bibliography = self.doc_data.get("bibliography", {})

        self.llm_client = llm_client
        self.context_window_size = context_window_size
        self.annotated_components = []

    def decompose_paragraph(self, paragraph_text: str):
        citation_pattern = r'(\s*\([^)]+\d{4}[^)]*\)|\s*\[\^?\d+\]|\s*\$\{\}\^\d+\})'

        parts = re.split(citation_pattern, paragraph_text)

        atoms = []
        for part in parts:
            if not part or part.isspace():
                continue
            # if part is a citation, add it after skipping whitespace
            if re.fullmatch(citation_pattern, part):
                atoms.append(part.strip())
            # otherwise, tokenize as regular sentence
            else:
                sentences = nltk.sent_tokenize(part)
                atoms.extend(s.strip() for s in sentences if s.strip())

        return atoms
    
    def build_graph(self):
        self.annotated_components = []
        context_window = deque(maxlen=self.context_window_size)

        # iterate through chapters
        for chapter_idx, (chapter_title, chapter_data) in enumerate(self.chapters.items()):
            for section in chapter_data.get("sections", []):
                if section.get("title") == "Notes":
                    continue
                for paragraph in section.get("paragraphs", []):
                    paragraph_text = paragraph["text"]
                    atoms = self.decompose_paragraph(paragraph_text)

                    search_start_idx = 0
                    for atom_idx, atom_text in enumerate(atoms):
                        # generate globally unique id
                        atom_id = f"chap{chapter_idx}_sec{section['id']}_par{paragraph['id']}_atom{atom_idx+1}"

                        try:
                            relative_start = paragraph_text.index(atom_text, search_start_idx)
                            start_offset = paragraph["start_offset"] + relative_start
                            end_offset = start_offset + len(atom_text)
                            search_start_idx = relative_start + len(atom_text)
                        except ValueError:
                            start_offset, end_offset = -1, -1

                        target_component = {"id": atom_id, "text": atom_text}
                        context = list(context_window)

                        # call LLM client
                        llm_response = self.llm_client.process_atom(
                            target_component=target_component,
                            context_components=context
                        )

                        annotated_component = {
                            "id": atom_id,
                            "chapter_title": chapter_title,
                            "section_id": section['id'],
                            "paragraph_id": paragraph['id'],
                            "text": atom_text,
                            "start_offset": start_offset,
                            "end_offset": end_offset,
                            "classification": llm_response.get("classification", "Error"),
                            "relationships": llm_response.get("relationships", [])
                        }

                        self.annotated_components.append(annotated_component)
                        context_window.append(target_component)

        return {
            "document_title": self.title,
            "components": self.annotated_components
        }
    
    def check_ontology(self, graph: dict) -> bool:
        for component in graph["components"]:
            connections = component["relationships"]
            component_class = component["classification"]
            for connection in connections:
                connection_class = connection["class"]
                direction = connection["direction"]
                    