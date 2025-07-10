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