import fitz
import os
import re

class MetadataExtractor:
    def __init__(self, pdf_path: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"File not found: {pdf_path}")
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self._cache = {}

        self.intro_keywords = [
            "contents", "introduction", "preface", "prologue", "foreword", "acknowledgements"
        ]
        self.end_section_keywords = [
            "bibliography", "references", "index", "appendices", "glossary", "appendix",
            "endnotes", "afterword", "conclusion", "notes"
        ]
    
    def __del__(self):
        # ensures document is closed when object is destroyed
        if self.doc:
            self.doc.close()

    def get_toc(self) -> list | None:
        if 'toc' in self._cache:
            return self._cache['toc']
        
        toc = self.doc.get_toc()
        if not toc:
            self._cache['toc'] = None
            return None
        
        self._cache['toc'] = toc
        return toc
    
    def get_chapters(self, toc: list) -> list[dict]:
        chapters = []
        in_main_content = False

        for level, title, page_number in self.get_toc():
            clean_title = title.lower().strip()

            # simple check for end keywords, checking for beginning of end section
            if any(keyword in clean_title for keyword in self.end_section_keywords):
                break

            is_intro = any(keyword in clean_title for keyword in self.intro_keywords)

            # start collecting once past intro sections
            if not is_intro:
                in_main_content = True
            
            if in_main_content:
                if not any(keyword in clean_title for keyword in self.end_section_keywords):
                    chapters.append({'title': title, 'start_page': page_number - 1, 'level': level})

        return chapters
    
    def get_chapter_page_ranges(self) -> list[dict | None]:
        toc = self.get_toc()
        if not toc:
            return None
        
        chapters = self.get_chapters(toc)
        if not chapters:
            return None
        
        chapter_ranges = []
        for i, chapter in enumerate(chapters):
            start_page = chapter['start_page']

            # determine end page
            if i + 1 < len(chapters): # pymupdf uses 0-based indexing
                end_page = chapters[i + 1]['start_page'] - 1 # set end page to one page before start of next chapter
            else:
                end_page = self.doc.page_count - 1 # for last chapter, set end page to last page of document

            if start_page <= end_page: # check that range is valid
                chapter_ranges.append({
                    'title': chapter['title'],
                    'start_page': start_page,
                    'end_page': end_page
                })

        return chapter_ranges

    def extract_chapters_as_pdfs(self) -> list[str]:
        chapter_ranges = self.get_chapter_page_ranges()
        if not chapter_ranges:
            return []

        # Create a temporary directory for the chapter PDFs
        base_dir = os.path.dirname(self.pdf_path)
        output_dir = os.path.join(base_dir, "temp_chapters")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        pdf_paths = []
        for i, chapter in enumerate(chapter_ranges):
            new_doc = fitz.open()  # Create a new, empty PDF
            
            # Insert pages from the original document
            new_doc.insert_pdf(self.doc, from_page=chapter['start_page'], to_page=chapter['end_page'])
            
            # Sanitize title for filename
            safe_title = re.sub(r'[^\w\s-]', '', chapter['title'].lower()).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            if not safe_title:
                safe_title = f"chapter-{i+1}"
            
            output_path = os.path.join(output_dir, f"{i:03d}_{safe_title}.pdf")
            new_doc.save(output_path)
            new_doc.close()
            pdf_paths.append(output_path)
            
        return pdf_paths

