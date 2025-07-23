import base64
import os
import argparse
from mistralai import Mistral
import fitz  # Import PyMuPDF
import concurrent.futures

class OCR:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)

    def __del__(self):
        if self.doc:
            self.doc.close()

    def encode_pages(self, start_page: int, end_page: int) -> str | None:
        try:
            # Create a new in-memory PDF with only the specified pages
            temp_doc = fitz.open()
            temp_doc.insert_pdf(self.doc, from_page=start_page, to_page=end_page)
            pdf_bytes = temp_doc.write()
            temp_doc.close()
            return base64.b64encode(pdf_bytes).decode('utf-8')
        except Exception as e:
            print(f"Error encoding pages {start_page}-{end_page}: {e}")
            return None

    def run_ocr_on_pages(self, start_page: int, end_page: int) -> str | None:
        base64_pdf_chunk = self.encode_pages(start_page, end_page)
        if not base64_pdf_chunk:
            return None

        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            print("Error: MISTRAL_API_KEY environment variable not set.")
            return None

        client = Mistral(api_key=api_key)

        try:
            ocr_response = client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{base64_pdf_chunk}",
                },
                include_image_base64=False,
            )
            return "".join(index.markdown for index in ocr_response.pages)
        except Exception as e:
            print(f"An error occurred during OCR on pages {start_page}-{end_page}: {e}")
            return None

    def run_ocr_on_all_pages(self) -> str | None:
        # To maintain backward compatibility, we can treat the whole document as a single chunk
        return self.run_ocr_on_pages(0, self.doc.page_count - 1)

    def run_ocr_on_chapters(self, chapter_ranges: list[dict]) -> list[dict]:
        chapter_texts = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_chapter = {
                executor.submit(self.run_ocr_on_pages, chapter['start_page'], chapter['end_page']): chapter
                for chapter in chapter_ranges
            }
            for future in concurrent.futures.as_completed(future_to_chapter):
                chapter = future_to_chapter[future]
                try:
                    text = future.get()
                    if text:
                        chapter_texts.append({
                            'title': chapter['title'],
                            'text': text
                        })
                except Exception as exc:
                    print(f"Chapter '{chapter['title']}' generated an exception: {exc}")
        
        # Sort chapters by their original order (based on start_page)
        chapter_texts.sort(key=lambda x: next(c['start_page'] for c in chapter_ranges if c['title'] == x['title']))
        return chapter_texts



