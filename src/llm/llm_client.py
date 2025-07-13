from mistralai import Mistral
import os
import json
import numpy as np
import dotenv
import time
import asyncio

class LLMClient:
    def __init__(self):
        # Load .env file from the project root (one level above src/)
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        dotenv.load_dotenv(env_path)
        
        self.model_name = os.getenv("MISTRAL_MODEL")
        self.api_key = os.getenv("MISTRAL_API_KEY")
        
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not found in environment variables")
        if not self.model_name:
            raise ValueError("MISTRAL_MODEL not found in environment variables")
            
        self.client = Mistral(api_key=self.api_key)

    def embed_mistral(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(
            model="mistral-embed",
            inputs=text
        )
        return np.array(response.data[0].embedding)

    def process_atom(self, target_component: dict, context_components: list):
        # Read the prompt template
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "atom_graph.md")
        with open(prompt_path, "r") as f:
            system_prompt_template = f.read()
        
        # Convert context and target_component to JSON strings
        context_json = json.dumps(context_components, indent=2)
        target_component_json = json.dumps(target_component, indent=2)
        
        # Substitute the placeholders in the prompt template
        system_prompt = system_prompt_template.replace("{{CONTEXT_JSON}}", context_json)
        system_prompt = system_prompt.replace("{{TARGET_COMPONENT_JSON}}", target_component_json)
        
        retries = 3
        backoff_factor = 0.5

        for i in range(retries):
            try:
                response = self.client.chat.complete(
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": "Please analyze the target component according to the instructions provided."}
                    ]
                )

                if not response.choices:
                    raise ValueError("LLM response has no choices.")

                response_text = response.choices[0].message.content
                
                if response_text:
                    try:
                        parsed_response = json.loads(response_text)
                        
                        # Validate the response structure
                        if self.check_taxonomy(parsed_response):
                            return parsed_response
                        else:
                            print(f"Warning: LLM response failed validation. Retrying attempt {i+1}/{retries}...")
                            print(f"Response: {response_text}")
                    except json.JSONDecodeError:
                        print(f"Warning: Failed to parse LLM JSON response. Retrying attempt {i+1}/{retries}...")
                        print(f"Response: {response_text}")
                else:
                    print(f"Warning: Empty response from LLM. Retrying attempt {i+1}/{retries}...")
            
            except Exception as e:
                print(f"Warning: An unexpected error occurred: {e}. Retrying attempt {i+1}/{retries}...")

            if i < retries - 1:
                time.sleep(backoff_factor * (2 ** i))
        
        # If all retries fail, return a default structure
        return {
            "classification": "Error",
            "justification": "LLM API call failed after multiple retries.",
            "relationships": []
        }
    
    def check_taxonomy(self, response: dict) -> bool:
        taxonomy_path = os.path.join(os.path.dirname(__file__), "..", "models", "taxonomy.json")
        ontology_path = os.path.join(os.path.dirname(__file__), "..", "models", "ontology.json")
        
        with open(taxonomy_path, "r") as f:
            taxonomy = json.load(f)
        with open(ontology_path, "r") as f:
            ontology = json.load(f)

        try:
            # Check if classification field is present and valid
            if "classification" not in response:
                return False
            
            # Check if classification is valid
            if response["classification"] not in taxonomy["valid_classes"]:
                return False
            
            # Check if relationships field is present and properly structured
            if "relationships" not in response:
                return False
            
            if not isinstance(response["relationships"], list):
                return False
            
            # Validate each relationship
            for relationship in response["relationships"]:
                if not isinstance(relationship, dict):
                    return False
                
                # Check required fields
                required_fields = ["target_id", "type", "direction", "justification"]
                for field in required_fields:
                    if field not in relationship:
                        return False
                
                # Check if relationship type is valid
                if relationship["type"] not in ontology["relationships"]:
                    return False
                
                # Check if direction is valid
                if relationship["direction"] not in ["outgoing", "incoming"]:
                    return False
            
            return True
            
        except (KeyError, TypeError):
            return False
        
    async def get_summary(self, text: str):
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "summarize.md")
        with open(prompt_path, "r") as f:
            system_prompt = f.read()

        retries = 3
        backoff_factor = 0.5

        for i in range(retries):
            try:
                response = await self.client.chat.complete(
                    model=self.model_name,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ]
                )

                if not response.choices:
                    raise ValueError("LLM response has no choices.")

                response_text = response.choices[0].message.content
                
                if response_text:
                    try:
                        json.loads(response_text)
                        return response_text
                    except json.JSONDecodeError:
                        print(f"Warning: Failed to parse summary JSON response. Retrying attempt {i+1}/{retries}...")
                        print(f"Response: {response_text}")
                else:
                    print(f"Warning: Empty summary response from LLM. Retrying attempt {i+1}/{retries}...")
            
            except Exception as e:
                print(f"Warning: An unexpected error occurred during summarization: {e}. Retrying attempt {i+1}/{retries}...")

            if i < retries - 1:
                await asyncio.sleep(backoff_factor * (2 ** i))
        
        return json.dumps({
            "summary": "Error: Failed to generate summary.",
            "theme": "Error",
            "keywords": []
        })

    