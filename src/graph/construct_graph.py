import json
import os
import re
import nltk
from collections import deque
from llm.llm_client import LLMClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
from threading import Lock
import time

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    print("Downloading NLTK punkt tokenizer...")
    nltk.download('punkt')

class GraphConstructor:
    def __init__(self, json_doc: dict, llm_client: LLMClient, context_window_size: int = 4096):
        # Check if the document data is nested under a single key or not
        if "chapters" in json_doc or "title" in json_doc:
            doc_dictionary = json_doc
        else:
            # It's likely nested, as in some test cases
            doc_key = list(json_doc.keys())[0]
            doc_dictionary = json_doc[doc_key]

        # Handle case where doc_data might be a list
        if isinstance(doc_dictionary, list) and doc_dictionary:
            doc_dictionary = doc_dictionary[0]

        self.doc_data = doc_dictionary
        self.title = self.doc_data.get("title") or "Untitled Document"
        self.chapters = self.doc_data.get("chapters", {})
        self.bibliography = self.doc_data.get("bibliography", {})

        self.llm_client = llm_client
        self.context_window_size = context_window_size
        self.annotated_components = []
        self.print_lock = Lock()

    def decompose_paragraph(self, paragraph_text: str):
        citation_pattern = r'(\s*\([^)]+\d{4}[^)]*\)|\s*\[\^?\d+\]|\s*\$\{\s*\}\^\{\d+\}\$)' # matches 

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
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    if ':' not in sentence:
                        atoms.append(sentence)
                        continue
                    
                    # If a sentence contains a colon, we might want to split it.
                    # However, we should not split if the colon is inside parentheses,
                    # as this is common in citations or asides.
                    paren_level = 0
                    colon_index = -1
                    for i, char in enumerate(sentence):
                        if char == '(':
                            paren_level += 1
                        elif char == ')':
                            paren_level = max(0, paren_level - 1) # handle malformed
                        elif char == ':' and paren_level == 0:
                            # Found a colon outside of parentheses, split here
                            colon_index = i
                            break
                    
                    if colon_index != -1:
                        # Split the sentence at the first valid colon
                        sub_parts = [sentence[:colon_index].strip(), sentence[colon_index+1:].strip()]
                        atoms.extend(p for p in sub_parts if p)
                    else:
                        # All colons are inside parentheses, so don't split
                        atoms.append(sentence)

        return atoms
    
    def _process_chapter(self, chapter_idx: int, chapter_title: str, chapter_data: dict, num_chapters: int):
        # First, calculate total atoms for progress bar
        total_atoms = 0
        all_paragraphs = []
        
        chapter_paragraphs = chapter_data.get("paragraphs", [])
        all_paragraphs.extend(chapter_paragraphs)
        
        for subsection in chapter_data.get("subsections", []):
            if subsection.get("title") == "Notes":
                continue
            all_paragraphs.extend(subsection.get("paragraphs", []))

        for para in all_paragraphs:
            total_atoms += len(self.decompose_paragraph(para["text"]))

        if total_atoms == 0:
            return []

        processed_atoms = 0
        chapter_components = []
        context_window = deque(maxlen=self.context_window_size)
        progress_lock = Lock()

        def update_progress():
            # Reading processed_atoms is atomic, but for correctness in displaying progress,
            # we rely on this being called right after an update.
            percent = 100 * (processed_atoms / float(total_atoms)) if total_atoms > 0 else 0
            bar_length = 30
            filled_length = int(bar_length * processed_atoms // total_atoms) if total_atoms > 0 else 0
            bar = '█' * filled_length + '-' * (bar_length - filled_length)
            percent_str = "{:.1f}".format(percent)
            
            # Prepare a tidy progress string
            progress_str = (
                f"  Chapter {chapter_idx + 1:<2} ({chapter_title[:20].ljust(20)}): "
                f"|{bar}| {processed_atoms: >4}/{total_atoms: >4} ({percent_str: >5}%)"
            )

            with self.print_lock:
                # Move cursor up to the correct line, clear it, print, then go back down
                sys.stdout.write(f"\x1b[{num_chapters - chapter_idx}A")
                sys.stdout.write(f"\r\x1b[K")  # Go to start of line, clear it
                sys.stdout.write(progress_str)
                sys.stdout.write(f"\x1b[{num_chapters - chapter_idx}B")
                sys.stdout.write(f"\r") # Back to start of line for the next thread
                sys.stdout.flush()

        update_progress() # Initial progress bar at 0%

        # Process chapter-level paragraphs sequentially
        for paragraph in chapter_data.get("paragraphs", []):
            paragraph_text = paragraph["text"]
            atoms = self.decompose_paragraph(paragraph_text)
            for atom_idx, atom_text in enumerate(atoms):
                atom_id = f"chap{chapter_idx}_par{paragraph['id']}_atom{atom_idx+1}"
                target_component = {"id": atom_id, "text": atom_text}
                context = list(context_window)
                time.sleep(0.2) # Avoid overwhelming the API
                llm_response = self.llm_client.process_atom(target_component, context)
                annotated_component = {
                    "id": atom_id, "chapter_title": chapter_title, "section_id": None,
                    "paragraph_id": paragraph['id'], "text": atom_text,
                    "start_offset": paragraph.get("start_offset", -1), "end_offset": paragraph.get("end_offset", -1),
                    "classification": llm_response.get("classification", "Error"),
                    "relationships": llm_response.get("relationships", [])
                }
                chapter_components.append(annotated_component)
                context_window.append(target_component)
                processed_atoms += 1
                update_progress()
        
        # Define a nested function to process one subsection
        def _process_subsection(subsection_data: dict, initial_context: deque):
            nonlocal processed_atoms
            subsection_components = []
            local_context_window = initial_context.copy()

            for paragraph in subsection_data.get("paragraphs", []):
                paragraph_text = paragraph["text"]
                atoms = self.decompose_paragraph(paragraph_text)
                for atom_idx, atom_text in enumerate(atoms):
                    atom_id = f"chap{chapter_idx}_sec{subsection_data['id']}_par{paragraph['id']}_atom{atom_idx+1}"
                    target_component = {"id": atom_id, "text": atom_text}
                    context = list(local_context_window)
                    time.sleep(0.1) # Avoid overwhelming the API
                    llm_response = self.llm_client.process_atom(target_component, context)
                    annotated_component = {
                        "id": atom_id, "chapter_title": chapter_title, "section_id": subsection_data['id'],
                        "paragraph_id": paragraph['id'], "text": atom_text,
                        "start_offset": paragraph.get("start_offset", -1), "end_offset": paragraph.get("end_offset", -1),
                        "classification": llm_response.get("classification", "Error"),
                        "relationships": llm_response.get("relationships", [])
                    }
                    subsection_components.append(annotated_component)
                    local_context_window.append(target_component)
                    with progress_lock:
                        processed_atoms += 1
                    update_progress()
            return subsection_components

        # Process subsections in parallel
        subsections_to_process = [
            s for s in chapter_data.get("subsections", []) if s.get("title") != "Notes"
        ]
        
        if subsections_to_process:
            with ThreadPoolExecutor() as executor:
                future_to_subsection = {
                    executor.submit(_process_subsection, s, context_window.copy()): s
                    for s in subsections_to_process
                }
                for future in as_completed(future_to_subsection):
                    subsection_data = future_to_subsection[future]
                    try:
                        subsection_components = future.result()
                        chapter_components.extend(subsection_components)
                    except Exception as exc:
                        print(f"Subsection '{subsection_data.get('title')}' in chapter '{chapter_title}' generated an exception: {exc}")

        return chapter_components

    def build_graph(self):
        self.annotated_components = []
        print(f"Building graph for document: {self.title}")
        num_chapters = len(self.chapters)
        print(f"Found {num_chapters} chapters to process in parallel...")

        # Make space for progress bars
        sys.stdout.write('\n' * num_chapters)
        sys.stdout.flush()

        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._process_chapter, idx, title, data, num_chapters): title
                for idx, (title, data) in enumerate(self.chapters.items())
            }
            
            for future in as_completed(futures):
                chapter_title = futures[future]
                try:
                    component_list = future.result()
                    self.annotated_components.extend(component_list)
                except Exception as exc:
                    print(f"Chapter '{chapter_title}' generated an exception: {exc}")

        print(f"\nGraph construction complete! Generated {len(self.annotated_components)} components")
        
        raw_graph = {"document_title": self.title, "components": self.annotated_components}
        
        print("\nFiltering graph based on ontology...")
        filtered_graph = self.prune_by_ontology(raw_graph)
        print(f"Graph filtering complete. {len(raw_graph['components'])} components remain.")
        
        return raw_graph
    
    def prune_by_ontology(self, graph: dict) -> dict:
        """
        Filters the graph by removing components with invalid classifications
        and relationships that are not compliant with the ontology.
        """
        # Load the ontology and taxonomy
        ontology_path = os.path.join(os.path.dirname(__file__), "..", "models", "ontology.json")
        taxonomy_path = os.path.join(os.path.dirname(__file__), "..", "models", "taxonomy.json")
        
        with open(ontology_path, "r") as f:
            ontology = json.load(f)
        with open(taxonomy_path, "r") as f:
            taxonomy = json.load(f)

        # First pass: Filter components with invalid classifications
        valid_components_by_id = {}
        for component in graph["components"]:
            classification = component.get("classification")
            if classification in taxonomy["valid_classes"]:
                valid_components_by_id[component["id"]] = component
            else:
                print(f"Warning: Filtering out component '{component.get('id')}' with invalid classification: '{classification}'")

        # Second pass: Filter invalid relationships
        final_components = []
        for component_id, component in valid_components_by_id.items():
            source_class = component["classification"]
            
            valid_relationships = []
            if "relationships" in component:
                for relationship in component["relationships"]:
                    target_id = relationship.get("target_id")
                    relationship_type = relationship.get("type")
                    direction = relationship.get("direction")

                    # Check if target component is valid
                    target_component = valid_components_by_id.get(target_id)
                    if not target_component:
                        print(f"Warning: Filtering relationship from '{component_id}' to invalid/filtered target '{target_id}'")
                        continue

                    if direction not in ["outgoing", "incoming"]:
                        print(f"Warning: Filtering relationship from '{component_id}' with invalid direction '{direction}'")
                        continue

                    if relationship_type not in ontology["relationships"]:
                        print(f"Warning: Filtering relationship from '{component_id}' with invalid relationship type '{relationship_type}'")
                        continue

                    target_class = target_component["classification"]
                    
                    # Check if the relationship is valid according to ontology
                    is_valid = False
                    relationship_rules = ontology["relationships"][relationship_type]
                    
                    if direction == "outgoing":
                        # Source connects to target
                        if (source_class in relationship_rules["valid_sources"] and 
                            target_class in relationship_rules["valid_targets"]):
                            is_valid = True
                    elif direction == "incoming":
                        # Target connects to source (so source receives from target)
                        if (target_class in relationship_rules["valid_sources"] and 
                            source_class in relationship_rules["valid_targets"]):
                            is_valid = True
                    
                    if is_valid:
                        valid_relationships.append(relationship)
                    else:
                        print(f"Warning: Filtering invalid ontology relationship: {source_class} --({relationship_type}, {direction})--> {target_class}")
            
            # Update component with filtered relationships
            component['relationships'] = valid_relationships
            final_components.append(component)
            
        return {
            "document_title": graph["document_title"],
            "components": final_components
        }
                    