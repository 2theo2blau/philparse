import re
import os


class Parser:
    def __init__(self, text):
        self.text = text

    def find_footnotes(self):
        detected_blocks = []
        
        header_pattern = re.compile(r'^#{0,4}\s*Notes\s*$', re.MULTILINE) # check for headers with "Notes" (e.g. "## Notes")
        listitem_pattern = re.compile(r'^(?:\[?(\d+|[ivxlc]+)\]?\.?\s+)(.*)', re.MULTILINE) # check for numbered list items (1. , 33. , etc.)
        terminator_pattern = re.compile(r"\n\n+") # set terminator to first instance of two or more newlines

        for header_match in header_pattern.finditer(self.text): # find all headers with "Notes"
            start_idx = header_match.end()
            if start_idx < len(self.text) and self.text[start_idx] == '\n':
                start_idx += 1

            if not listitem_pattern.search(self.text, pos=start_idx): # validation check -- make sure the header is followed by a list item
                continue

            block_start = start_idx
            block_end_offset = -1

            # check for terminators (double newlines)
            for terminator_match in terminator_pattern.finditer(self.text, pos=start_idx):
                terminator_end_idx = terminator_match.end()

                # check there is not a list item after the terminator
                if not listitem_pattern.search(self.text, pos=terminator_end_idx):
                    block_end_offset = terminator_match.start()
                    break # stop searching for terminators in this block

            if block_end_offset == -1:
                block_end_offset = len(self.text) # if no terminators are found, set the block end to the end of the text

            for match in listitem_pattern.finditer(self.text, pos=block_start, endpos=block_end_offset):
                detected_blocks.append((match.start(2), match.end(2)))

            if detected_blocks:
                return detected_blocks
        
        return detected_blocks
    
    def find_chapters(self):
        chapter_pattern = re.compile(
            # Pattern 1: Markdown style: # NUM \n ## TITLE
            r"^\s*#+\s*(?:Chapter\s+)?(?:\d+|[IVXLC]+)\s*\n+\s*#+\s*[^#\n].*$"
            # Pattern 2: Simple style: Chapter NUM
            r"|^\s*Chapter\s+(?:\d+|[IVXLC]+)\s*$",
            re.MULTILINE | re.IGNORECASE
        )

        terminator_pattern = re.compile(
            r"^\s*(?:Index|Bibliography|References|Appendix|Appendices|Glossary|Acknowledgements|Notes|Endnotes)\s*$",
            re.MULTILINE | re.IGNORECASE
        )

        chapter_matches = list(chapter_pattern.finditer(self.text))

        if not chapter_matches:
            return []

        last_chapter_start_offset = chapter_matches[-1].start()
    
        terminator_matches = list(terminator_pattern.finditer(self.text))

        valid_terminator_starts = [
            match.start() 
            for match in terminator_matches 
            if match.start() > last_chapter_start_offset
        ]

        if valid_terminator_starts:
            global_end_offset = min(valid_terminator_starts)
        else:
            global_end_offset = len(self.text)

        chapters = []
        for i, current_match in enumerate(chapter_matches):
            start_offset = current_match.start()
            
            title = current_match.group(0).strip()
            title_lines = title.split('\n')
            if len(title_lines) > 1:
                chapter_line = title_lines[0].strip()
                title_line = title_lines[1].strip().lstrip('#').strip()
                
                # Extract chapter number for consistent formatting
                num_match = re.search(r'(\d+|[IVXLC]+)', chapter_line)
                if num_match:
                    chapter_num = num_match.group(1)
                    title = f"Chapter {chapter_num}: {title_line}"
                else:
                    title = f"{chapter_line}: {title_line}" # Fallback
            else:
                 # For "Chapter X" style, keep the matched line as title
                 title = title.strip()

            if start_offset >= global_end_offset:
                continue

            is_last_chapter = (i == len(chapter_matches) - 1) or \
                            (chapter_matches[i + 1].start() >= global_end_offset)
            
            if is_last_chapter:
                end_offset = global_end_offset
            else:
                end_offset = chapter_matches[i + 1].start()

            chapters.append((title, start_offset, end_offset))

        return chapters
        