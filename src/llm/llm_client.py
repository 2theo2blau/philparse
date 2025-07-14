from mistralai import Mistral
import os
import json
import numpy as np
import time
from typing import List, Dict, Any

class LLMClient:
    def __init__(self, retries: int = 3, backoff_factor: float = 0.5):
        self.model_name = os.getenv("MISTRAL_MODEL")
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.retries = retries
        self.backoff_factor = backoff_factor
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment variables")
        if not self.model_name:
            raise ValueError("MISTRAL_MODEL not found in environment variables")
            
        self.client = Mistral(api_key=self.api_key)
        self._cache_resources()

    def _cache_resources(self):
        """Loads prompts, taxonomy, and ontology into memory to avoid redundant file I/O."""
        base_dir = os.path.dirname(__file__)
        
        # Load prompts
        prompt_path = os.path.join(base_dir, "prompts", "atom_graph.md")
        with open(prompt_path, "r") as f:
            self.atom_prompt_template = f.read()
            
        summary_prompt_path = os.path.join(base_dir, "prompts", "summarize.md")
        with open(summary_prompt_path, "r") as f:
            self.summary_prompt_template = f.read()

        # Load validation models
        taxonomy_path = os.path.join(base_dir, "..", "models", "taxonomy.json")
        with open(taxonomy_path, "r") as f:
            self.taxonomy = json.load(f)
        
        ontology_path = os.path.join(base_dir, "..", "models", "ontology.json")
        with open(ontology_path, "r") as f:
            self.ontology = json.load(f)
            
        # Pre-compile valid sets for faster lookups
        self.valid_classes = set(self.taxonomy.get("valid_classes", []))
        self.valid_relationships = set(self.ontology.get("relationships", {}).keys())
        self.valid_directions = {"outgoing", "incoming"}

    def _run_completion_request(self, messages: List[Dict[str, str]], temperature: float = 0.1) -> Dict[str, Any] | None:
        """
        Executes the chat completion API call with a retry mechanism.
        Returns the parsed JSON object on success, or None on failure.
        """
        for i in range(self.retries):
            try:
                response = self.client.chat.complete(
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    messages=messages
                )

                if not response.choices:
                    raise ValueError("LLM response contained no choices.")

                response_text = response.choices[0].message.content
                if not response_text:
                    raise ValueError("LLM response was empty.")
                
                return json.loads(response_text)

            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse JSON response. Attempt {i+1}/{self.retries}. Error: {e}")
            except Exception as e:
                print(f"Warning: API call failed. Attempt {i+1}/{self.retries}. Error: {e}")

            if i < self.retries - 1:
                time.sleep(self.backoff_factor * (2 ** i))
        
        print(f"Error: API call failed after {self.retries} retries.")
        return None

    def embed_mistral(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(
            model="mistral-embed",
            inputs=text
        )
        return np.array(response.data[0].embedding)

    def process_atom(self, target_component: dict, context_components: list) -> Dict[str, Any]:
        # --- REFACTORED: Streamlined using cached resources and helper method ---
        context_json = json.dumps(context_components, indent=2)
        target_component_json = json.dumps(target_component, indent=2)
        
        system_prompt = self.atom_prompt_template.replace("{{CONTEXT_JSON}}", context_json)
        system_prompt = system_prompt.replace("{{TARGET_COMPONENT_JSON}}", target_component_json)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please analyze the target component according to the instructions provided."}
        ]
        
        parsed_response = self._run_completion_request(messages)

        if parsed_response and self.check_taxonomy(parsed_response):
            return parsed_response
        
        # Return a default error structure if call fails or validation fails
        return {
            "classification": "Error",
            "justification": "LLM API call failed, response was invalid, or validation failed after retries.",
            "relationships": []
        }
    
    def check_taxonomy(self, response: dict) -> bool: 
        # refactored to use cached sets to reduce file I/O
        if "classification" not in response or response["classification"] not in self.valid_classes:
            return False
        
        if "relationships" not in response or not isinstance(response["relationships"], list):
            return False
            
        for rel in response["relationships"]:
            if not isinstance(rel, dict): return False
            if not all(k in rel for k in ["target_id", "type", "direction", "justification"]): return False
            if rel["type"] not in self.valid_relationships: return False
            if rel["direction"] not in self.valid_directions: return False
            
        return True
        
    def get_summary(self, text: str) -> str:
        messages = [
            {"role": "system", "content": self.summary_prompt_template},
            {"role": "user", "content": text}
        ]
        
        parsed_response = self._run_completion_request(messages)
        
        if parsed_response:
            return json.dumps(parsed_response)
            
        return json.dumps({
            "summary": "Error: Failed to generate summary.",
            "theme": "Error",
            "keywords": []
        })

    