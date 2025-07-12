from mistralai import Mistral
import os
import json
import numpy as np

class LLMClient:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = os.getenv("MISTRAL_MODEL")
        self.api_key = os.getenv("MISTRAL_API_KEY")
        self.client = Mistral(api_key=self.api_key)

    def embed_mistral(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(
            model="mistral-embed",
            inputs=text
        )
        return np.array(response.data[0].embedding)

    def process_atom(self, target_component: dict, context_components: list):
        # Read the prompt template
        prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
        with open(prompt_path, "r") as f:
            system_prompt_template = f.read()
        
        # Convert context and target_component to JSON strings
        context_json = json.dumps(context_components, indent=2)
        target_component_json = json.dumps(target_component, indent=2)
        
        # Substitute the placeholders in the prompt template
        system_prompt = system_prompt_template.replace("{{CONTEXT_JSON}}", context_json)
        system_prompt = system_prompt.replace("{{TARGET_COMPONENT_JSON}}", target_component_json)
        
        # Make the API call with the properly formatted prompt
        response = self.client.chat.complete(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": "Please analyze the target component according to the instructions provided."
                }
            ]
        )
        
        response_text = response.choices[0].message.content
        
        # Parse the JSON response
        try:
            parsed_response = json.loads(response_text)
            return parsed_response
        except json.JSONDecodeError:
            # If parsing fails, return a default structure
            return {
                "classification": "Error",
                "relationships": [],
                "error": "Failed to parse LLM response",
                "raw_response": response_text
            }
    
    def check_taxonomy(self, response: str) -> bool:
        with open("models/taxonomy.json", "r") as f:
            taxonomy = json.load(f)

        try:
            # Parse the response as JSON
            parsed_response = json.loads(response)
            
            # Check if classification field is present and valid
            if "classification" not in parsed_response:
                return False
            
            # Check if classification is valid
            return parsed_response["classification"] in taxonomy["valid_classes"]
            
        except (json.JSONDecodeError, KeyError, TypeError):
            return False

    