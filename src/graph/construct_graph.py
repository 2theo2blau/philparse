import json
import os
from collections import deque
from llm.llm_client import LLMClient
from threading import Lock
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

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
        
        # Validate required fields exist before accessing directly
        if "title" not in self.doc_data:
            raise ValueError("Document data must contain 'title' field")
        if "chapters" not in self.doc_data:
            raise ValueError("Document data must contain 'chapters' field")
        if "bibliography" not in self.doc_data:
            raise ValueError("Document data must contain 'bibliography' field")
        
        # Now safely access the fields directly
        self.title = self.doc_data["title"]
        self.chapters = self.doc_data["chapters"]
        self.bibliography = self.doc_data["bibliography"]

        # Extract the paragraph ID map from the metadata, if it exists.
        self.paragraph_id_map = self.doc_data.get("metadata", {}).get("paragraph_id_map", {})

        self.llm_client = llm_client
        self.context_window_size = context_window_size
        self.annotated_components = []
        self.print_lock = Lock()
        
        # Simple progress tracking for API endpoints
        self.total_atoms = 0
        self.processed_atoms = 0
        self.current_status = "idle"
        self.pbar = None

        # add cache for ontology and taxonomy
        self._cache = {}

    def _count_atoms_in_chapter(self, chapter_data: dict) -> int:
        """Count total atoms in a chapter for progress tracking"""
        total_atoms = 0
        
        # Count atoms in chapter-level paragraphs
        for paragraph in chapter_data.get("paragraphs", []):
            total_atoms += len(paragraph.get("atoms", []))
        
        # Count atoms in subsections (excluding Notes)
        for subsection in chapter_data.get("subsections", []):
            if subsection.get("title") == "Notes":
                continue
            for paragraph in subsection.get("paragraphs", []):
                total_atoms += len(paragraph.get("atoms", []))
        
        return total_atoms

    def get_progress_info(self) -> dict:
        """Get current progress information for API endpoints"""
        if self.total_atoms == 0:
            progress_percent = 0
        else:
            progress_percent = int(100 * self.processed_atoms / self.total_atoms)
        
        return {
            "status": self.current_status,
            "total_atoms": self.total_atoms,
            "processed_atoms": self.processed_atoms,
            "progress_percent": progress_percent
        }

    def _process_chapter(self, chapter_idx: int, chapter_title: str, chapter_data: dict):
        # Calculate total atoms for progress tracking
        total_atoms = 0
        all_paragraphs = []
        
        chapter_paragraphs = chapter_data.get("paragraphs", [])
        all_paragraphs.extend(chapter_paragraphs)
        
        for subsection in chapter_data.get("subsections", []):
            if subsection.get("title") == "Notes":
                continue
            all_paragraphs.extend(subsection.get("paragraphs", []))

        for para in all_paragraphs:
            total_atoms += len(para.get("atoms", []))

        if total_atoms == 0:
            return []

        processed_atoms_in_chapter = 0
        chapter_components = []
        # context_window = deque(maxlen=self.context_window_size)  # REMOVE global context window

        # Process chapter-level paragraphs first (sequential to maintain context)
        prev_paragraph_atoms = []
        for paragraph in chapter_data.get("paragraphs", []):
            atoms = paragraph.get("atoms", [])
            for atom_idx, atom in enumerate(atoms):
                atom_id = f"chap{chapter_idx}_par{paragraph['id']}_atom{atom_idx+1}"
                target_component = {"id": atom_id, "text": atom["text"]}
                # Build local context: all atoms from previous paragraph + previous atoms in this paragraph
                context = []
                context.extend(prev_paragraph_atoms)
                context.extend([
                    {"id": f"chap{chapter_idx}_par{paragraph['id']}_atom{idx+1}", "text": atoms[idx]["text"]}
                    for idx in range(atom_idx)
                ])
                llm_response = self.llm_client.process_atom(target_component, context)
                annotated_component = {
                    "id": atom_id, "chapter_title": chapter_title, "section_id": None,
                    "paragraph_id": paragraph['id'], "text": atom["text"],
                    "start_offset": atom.get("start_offset", -1), "end_offset": atom.get("end_offset", -1),
                    "classification": llm_response.get("classification", "Error"),
                    "relationships": llm_response.get("relationships", [])
                }
                chapter_components.append(annotated_component)
                processed_atoms_in_chapter += 1
                
                # Update global progress counter (thread-safe)
                with self.print_lock:
                    self.processed_atoms += 1
                    if self.pbar:
                        self.pbar.update(1)
            # After processing this paragraph, update prev_paragraph_atoms
            prev_paragraph_atoms = [
                {"id": f"chap{chapter_idx}_par{paragraph['id']}_atom{idx+1}", "text": atom["text"]}
                for idx, atom in enumerate(atoms)
            ]

        # Define a nested function to process one subsection
        def _process_subsection(subsection_data: dict):
            subsection_components = []
            prev_paragraph_atoms = []
            for paragraph in subsection_data.get("paragraphs", []):
                atoms = paragraph.get("atoms", [])
                for atom_idx, atom in enumerate(atoms):
                    atom_id = f"chap{chapter_idx}_sec{subsection_data['id']}_par{paragraph['id']}_atom{atom_idx+1}"
                    target_component = {"id": atom_id, "text": atom["text"]}
                    # Build local context: all atoms from previous paragraph + previous atoms in this paragraph
                    context = []
                    context.extend(prev_paragraph_atoms)
                    context.extend([
                        {"id": f"chap{chapter_idx}_sec{subsection_data['id']}_par{paragraph['id']}_atom{idx+1}", "text": atoms[idx]["text"]}
                        for idx in range(atom_idx)
                    ])
                    llm_response = self.llm_client.process_atom(target_component, context)
                    annotated_component = {
                        "id": atom_id, "chapter_title": chapter_title, "section_id": subsection_data['id'],
                        "paragraph_id": paragraph['id'], "text": atom["text"],
                        "start_offset": atom.get("start_offset", -1), "end_offset": atom.get("end_offset", -1),
                        "classification": llm_response.get("classification", "Error"),
                        "relationships": llm_response.get("relationships", [])
                    }
                    subsection_components.append(annotated_component)
                    with self.print_lock:
                        self.processed_atoms += 1
                        if self.pbar:
                            self.pbar.update(1)
                # After processing this paragraph, update prev_paragraph_atoms
                prev_paragraph_atoms = [
                    {"id": f"chap{chapter_idx}_sec{subsection_data['id']}_par{paragraph['id']}_atom{idx+1}", "text": atom["text"]}
                    for idx, atom in enumerate(atoms)
                ]
            return subsection_components

        # Process subsections in parallel using ThreadPoolExecutor
        subsections_to_process = [
            s for s in chapter_data.get("subsections", []) if s.get("title") != "Notes"
        ]
        
        if subsections_to_process:
            with ThreadPoolExecutor(max_workers=min(len(subsections_to_process), 4)) as executor:
                futures = [
                    executor.submit(_process_subsection, s)
                    for s in subsections_to_process
                ]
                for future in futures:
                    subsection_components = future.result()
                    chapter_components.extend(subsection_components)

        return chapter_components

    def build_graph(self):
        self.annotated_components = []
        self.processed_atoms = 0
        self.current_status = "building"
        # print(f"Building graph for document: {self.title}")
        
        # Calculate total atoms for overall progress tracking
        self.total_atoms = 0
        chapters_to_process = self.chapters if isinstance(self.chapters, (dict, list)) else {}
        
        if isinstance(chapters_to_process, dict):
            for chapter_data in chapters_to_process.values():
                self.total_atoms += self._count_atoms_in_chapter(chapter_data)
        elif isinstance(chapters_to_process, list):
            for chapter_data in chapters_to_process:
                self.total_atoms += self._count_atoms_in_chapter(chapter_data)
        
        if self.total_atoms > 0:
            self.pbar = tqdm(total=self.total_atoms, desc=f"Building graph for '{self.title}'", unit="atom")
        else:
            print(f"No atoms to process for document '{self.title}'.")
            self.current_status = "complete"
            return {"document_title": self.title, "components": []}

        # Ensure chapters is in the correct format
        if isinstance(self.chapters, str):
            raise ValueError(f"Expected chapters to be dict or list, but got string: {self.chapters}")
        elif isinstance(self.chapters, dict):
            num_chapters = len(self.chapters)
            # print(f"Found {num_chapters} chapters with {self.total_atoms} total atoms to process...")
        elif isinstance(self.chapters, list):
            num_chapters = len(self.chapters)
            # print(f"Found {num_chapters} chapters with {self.total_atoms} total atoms to process...")
        else:
            raise ValueError(f"Unexpected chapters type: {type(self.chapters)}")

        # Process chapters in parallel using ThreadPoolExecutor
        # Handle both dictionary and list formats for chapters
        if isinstance(self.chapters, dict):
            chapter_args = [
                (idx, title, data)
                for idx, (title, data) in enumerate(self.chapters.items())
            ]
        else:
            # chapters is a list, use index-based access
            chapter_args = [
                (idx, chapter.get('title', f'Chapter {idx+1}'), chapter)
                for idx, chapter in enumerate(self.chapters)
            ]
        
        try:
            with ThreadPoolExecutor(max_workers=min(len(chapter_args), 4)) as executor:
                futures = [
                    executor.submit(self._process_chapter, *args)
                    for args in chapter_args
                ]
                for future in futures:
                    chapter_components = future.result()
                    self.annotated_components.extend(chapter_components)
        except Exception as exc:
            self.current_status = "error"
            print(f"Error during chapter processing: {exc}")
            raise
        finally:
            if self.pbar:
                self.pbar.close()
                self.pbar = None

        self.current_status = "filtering"
        # print(f"Graph construction complete! Generated {len(self.annotated_components)} components")
        
        raw_graph = {"document_title": self.title, "components": self.annotated_components}
        
        # print("Filtering graph based on ontology...")
        filtered_graph = self.prune_by_ontology(raw_graph)
        # print(f"Graph filtering complete. {len(raw_graph['components'])} components remain.")
        
        self.current_status = "complete"
        return raw_graph
    
    def prune_by_ontology(self, graph: dict) -> dict:
        # Load the ontology and taxonomy (with caching)
        ontology_path = os.path.join(os.path.dirname(__file__), "..", "models", "ontology.json")
        taxonomy_path = os.path.join(os.path.dirname(__file__), "..", "models", "taxonomy.json")
        
        if "ontology" not in self._cache:
            with open(ontology_path, "r") as f:
                ontology = json.load(f)
            self._cache["ontology"] = ontology
        if "taxonomy" not in self._cache:
            with open(taxonomy_path, "r") as f:
                taxonomy = json.load(f)
            self._cache["taxonomy"] = taxonomy

        ontology = self._cache["ontology"]
        taxonomy = self._cache["taxonomy"]
        
        # Pre-compute efficient lookup structures
        valid_classes = set(taxonomy["valid_classes"])
        relationship_rules = ontology["relationships"]
        
        # Pre-build component ID set for fast lookups during relationship validation
        component_ids = {comp["id"] for comp in graph["components"]}
        
        # Single pass: validate components and filter relationships simultaneously
        final_components = []
        valid_component_ids = set()
        
        for component in graph["components"]:
            component_id = component["id"]
            classification = component.get("classification")
            
            # Skip invalid components
            if classification not in valid_classes:
                # print(f"Warning: Filtering out component '{component_id}' with invalid classification: '{classification}'")
                continue
            
            # Component is valid, track it
            valid_component_ids.add(component_id)
            
            # Filter relationships for this component
            valid_relationships = []
            for relationship in component.get("relationships", []):
                target_id = relationship.get("target_id")
                relationship_type = relationship.get("type")
                direction = relationship.get("direction")
                
                # Quick validation checks
                if (target_id not in component_ids or 
                    direction not in ["outgoing", "incoming"] or
                    relationship_type not in relationship_rules):
                    
                    # if target_id not in component_ids:
                    #     print(f"Warning: Filtering relationship from '{component_id}' to invalid/filtered target '{target_id}'")
                    # elif direction not in ["outgoing", "incoming"]:
                    #     print(f"Warning: Filtering relationship from '{component_id}' with invalid direction '{direction}'")
                    # else:
                    #     print(f"Warning: Filtering relationship from '{component_id}' with invalid relationship type '{relationship_type}'")
                    continue
                
                # We'll validate ontology rules in the second pass since we need all valid components first
                valid_relationships.append(relationship)
            
            # Update component with filtered relationships
            component['relationships'] = valid_relationships
            final_components.append(component)
        
        # Build classification lookup map for fast access
        classification_map = {comp["id"]: comp["classification"] for comp in final_components}
        
        # Second pass: validate ontology rules for relationships (now that we know all valid components)
        for component in final_components:
            source_class = component["classification"]
            filtered_relationships = []
            
            for relationship in component["relationships"]:
                target_id = relationship.get("target_id")
                relationship_type = relationship.get("type")
                direction = relationship.get("direction")
                
                # Skip if target component was filtered out
                if target_id not in valid_component_ids:
                    # print(f"Warning: Filtering relationship from '{component['id']}' to invalid/filtered target '{target_id}'")
                    continue
                
                # Get target component classification (fast lookup)
                target_class = classification_map.get(target_id)
                if not target_class:
                    continue
                
                # Validate ontology rules
                rules = relationship_rules[relationship_type]
                is_valid = False
                
                if direction == "outgoing":
                    is_valid = (source_class in rules["valid_sources"] and 
                               target_class in rules["valid_targets"])
                elif direction == "incoming":
                    is_valid = (target_class in rules["valid_sources"] and 
                               source_class in rules["valid_targets"])
                
                if is_valid:
                    filtered_relationships.append(relationship)
                # else:
                #     print(f"Warning: Filtering invalid ontology relationship: {source_class} --({relationship_type}, {direction})--> {target_class}")
            
            component['relationships'] = filtered_relationships
        
        return {
            "document_title": graph["document_title"],
            "components": final_components
        }
                    
    def get_atoms_from_graph(self, pruned_graph: Dict[str, Any], document_id: int) -> List[Dict[str, Any]]:
        atoms_for_db = []
        components = pruned_graph.get("components", [])
        for component in components:
            source_paragraph_id = component.get("paragraph_id")
            
            # Use the map to get the correct DB paragraph ID.
            # The map keys are strings because of JSON serialization.
            db_paragraph_id = self.paragraph_id_map.get(str(source_paragraph_id))
            
            if db_paragraph_id is None:
                # Fallback or error handling if a paragraph ID is not in the map.
                # For now, we'll log a warning and skip it to prevent crashes.
                # logger.warning(f"Could not find mapping for paragraph_id: {source_paragraph_id}. Skipping atom.")
                continue

            atom_data = {
                "graph_id": component["id"],  # Temporary field for mapping
                "document_id": document_id,
                "paragraph_id": db_paragraph_id,
                "text": component.get("text"),
                "classification": component.get("classification"),
                "start_offset": component.get("start_offset", -1),
                "end_offset": component.get("end_offset", -1),
            }
            atoms_for_db.append(atom_data)
        
        return atoms_for_db

    def get_relationships_from_graph(self, pruned_graph: Dict[str, Any], document_id: int, atom_id_map: Dict[str, int]) -> List[Dict[str, Any]]:
        relationships_for_db = []
        components = pruned_graph.get("components", [])
        
        for component in components:
            source_id_str = component.get("id")
            if "relationships" in component:
                for rel in component["relationships"]:
                    target_id_str = rel.get("target_id")
                    direction = rel.get("direction")
                    
                    if direction == "outgoing":
                        source_graph_id = source_id_str
                        target_graph_id = target_id_str
                    elif direction == "incoming":
                        source_graph_id = target_id_str
                        target_graph_id = source_id_str
                    else:
                        continue
                    
                    source_atom_id = atom_id_map.get(source_graph_id)
                    target_atom_id = atom_id_map.get(target_graph_id)
                    
                    if source_atom_id is None or target_atom_id is None:
                        continue

                    rel_data = {
                        "document_id": document_id,
                        "source_atom_id": source_atom_id,
                        "target_atom_id": target_atom_id,
                        "type": rel.get("type"),
                        "justification": rel.get("justification")
                    }
                    relationships_for_db.append(rel_data)
        
        # Deduplicate relationships to handle cases where they might be defined from both ends
        unique_relationships = []
        seen_relationships = set()
        for rel in relationships_for_db:
            # A directed relationship is unique by (source, target, type)
            rel_tuple = (rel["source_atom_id"], rel["target_atom_id"], rel["type"])
            if rel_tuple not in seen_relationships:
                unique_relationships.append(rel)
                seen_relationships.add(rel_tuple)

        return unique_relationships