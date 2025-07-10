import base64
import os
import argparse
from mistralai import Mistral


class OCR:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path

    def encode_pdf(self):
        try:
            with open(self.pdf_path, "rb") as pdf_file:
                return base64.b64encode(pdf_file.read()).decode('utf-8')
        except FileNotFoundError:
            print(f"Error: The file {self.pdf_path} was not found.")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

    def run_ocr(self):
        base64_pdf = self.encode_pdf(self.pdf_path)

        if not base64_pdf:
            return

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("Error: MISTRAL_API_KEY environment variable not set.")
            return

        client = Mistral(api_key=api_key)

        print(f"Processing {self.pdf_path}...")
        try:
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{base64_pdf}" 
                },
                include_image_base64=False
            )

            output_dir = "../../processed_pdfs"
            os.makedirs(output_dir, exist_ok=True)
            
            file_name = os.path.basename(self.pdf_path)
            output_filename = os.path.splitext(file_name)[0] + ".txt"
            output_path = os.path.join(output_dir, output_filename)

            full_text = "".join(index.markdown for index in ocr_response.pages)

            with open(output_path, "w", encoding="utf-8") as output_file:
                output_file.write(full_text)
                
            print(f"OCR result saved to {output_path}")

        except Exception as e:
            print(f"An error occurred during OCR processing: {e}")



