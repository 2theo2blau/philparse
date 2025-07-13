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
        base64_pdf = self.encode_pdf()

        if not base64_pdf:
            return None

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("Error: MISTRAL_API_KEY environment variable not set.")
            return None

        client = Mistral(api_key=api_key)

        print(f"Processing {self.pdf_path}...")
        try:
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{base64_pdf}",
                },
                include_image_base64=False,
            )

            full_text = "".join(index.markdown for index in ocr_response.pages)
            return full_text

        except Exception as e:
            print(f"An error occurred during OCR processing: {e}")
            return None



