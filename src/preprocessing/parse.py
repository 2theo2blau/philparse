import re
import os


class Parser:
    def __init__(self, text):
        self.text = text

    def find_notes(self):
        notes_map = {}
        
        header_pattern = re.compile(r'^#{0,4}\s*Notes\s*$', re.MULTILINE | re.IGNORECASE) # check for headers with "Notes" (e.g. "## Notes")
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

            # Find all list items in the block
            list_matches = list(listitem_pattern.finditer(self.text, pos=block_start, endpos=block_end_offset))
            
            for i, match in enumerate(list_matches):
                note_num = match.group(1)
                note_start = match.start(2)  # Start of the note text
                
                # Find the end of this note's text
                if i + 1 < len(list_matches):
                    # Next list item exists, note ends at start of next item
                    note_end = list_matches[i + 1].start()
                else:
                    # Last item, note ends at block end
                    note_end = block_end_offset
                
                # Extract and clean the note text
                note_text = self.text[note_start:note_end].strip().replace('\n', ' ')
                notes_map[note_num] = note_text

            if notes_map:
                return notes_map
        
        return notes_map
    
    def find_footnotes(self):
        reference_pattern = re.compile(r'\[\^([^\]]+)\](?!:)')
        definition_pattern = re.compile(r'\[\^([^\]]+)\]:\s*(.+?)(?=\n\n|\[\^|$)', re.DOTALL)
        
        references = []
        ref_id = 1

        for match in reference_pattern.finditer(self.text):
            reference = {
                'id': ref_id,
                'identifier': match.group(1),
                'start_offset': match.start(),
                'end_offset': match.end()
            }

            references.append(reference)
            ref_id += 1

        definitions = []
        def_id = 1

        for match in definition_pattern.finditer(self.text):
            definition = {
                'id': def_id,
                'identifier': match.group(1),
                'content': match.group(2).strip(),
                'start_offset': match.start(),
                'end_offset': match.end()
            }
            
            definitions.append(definition)
            def_id += 1

        return {
            'references': references,
            'definitions': definitions
        }

    def find_chapters(self):
        chapter_pattern = re.compile(
            # Pattern 1: Markdown style: # NUM \n ## TITLE
            r"^\s*#+\s*(?:Chapter\s+)?(?:\d+|[IVXLC]+)\s*\n+\s*#+\s*[^#\n].*$"
            # Pattern 2: Simple style: Chapter NUM
            r"|^\s*Chapter\s+(?:\d+|[IVXLC]+)\s*$",
            re.MULTILINE | re.IGNORECASE
        )

        terminator_pattern = re.compile(
            r"^\s*#*\s*(?:Index|Bibliography|References|Appendix|Appendices|Glossary|Acknowledgements|Notes|Endnotes|Afterword)\s*$",
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
    
    def find_intro_sections(self):
        chapters = self.find_chapters()
        if not chapters:
            return []
        
        first_chapter_start_offset = chapters[0][1]
        truncated_text = self.text[:first_chapter_start_offset]
        
        # Updated pattern to include Contents and handle apostrophes
        intro_pattern = re.compile(
            r'^#+\s*(?:Contents|Introduction|Preface|Prologue|Publisher\'?s?\s*Acknowledgements?|Acknowledgements?)\s*$', 
            re.MULTILINE | re.IGNORECASE
        )
        
        # Find all intro section headers
        intro_matches = list(intro_pattern.finditer(truncated_text))
        if not intro_matches:
            return []
        
        # Extract full sections with their content
        intro_sections = []
        for i, match in enumerate(intro_matches):
            title = match.group(0).strip().lstrip('#').strip()
            start_offset = match.start()
            content_start = match.end()
            
            # Skip the newline after the header if present
            if content_start < len(truncated_text) and truncated_text[content_start] == '\n':
                content_start += 1
            
            # Find the end of this section
            if i + 1 < len(intro_matches):
                # Next intro section exists
                end_offset = intro_matches[i + 1].start()
            else:
                # Last intro section, ends at first chapter
                end_offset = first_chapter_start_offset
            
            intro_sections.append({
                'title': title,
                'start_offset': start_offset,
                'content_start': content_start,
                'end_offset': end_offset,
                'content': self.text[content_start:end_offset].strip()
            })
        
        return intro_sections
        
    def find_chapter_subsections(self):
        chapters = self.find_chapters()
        if not chapters:
            return {}

        chapter_map = {}

        # Regex to find markdown headers (e.g., #, ## Subsection)
        subsection_pattern = re.compile(r"^\s*#+\s*(.+?)\s*$", re.MULTILINE)

        # Re-run chapter search to get header end positions
        chapter_header_pattern_str = (
            r"^\s*#+\s*(?:Chapter\s+)?(?:\d+|[IVXLC]+)\s*\n+\s*#+\s*[^#\n].*$"
            r"|^\s*Chapter\s+(?:\d+|[IVXLC]+)\s*$"
        )
        chapter_header_pattern = re.compile(chapter_header_pattern_str, re.MULTILINE | re.IGNORECASE)
        chapter_header_matches = {match.start(): match for match in chapter_header_pattern.finditer(self.text)}

        for i, (title, start_offset, end_offset) in enumerate(chapters):
            chapter_map[title] = []
            
            header_match = chapter_header_matches.get(start_offset)
            content_start = header_match.end() if header_match else start_offset

            # Find all subsection headers within the chapter's content
            subsection_matches = list(subsection_pattern.finditer(self.text, pos=content_start, endpos=end_offset))

            for j, match in enumerate(subsection_matches):
                sub_title = match.group(1).strip()
                sub_start_offset = match.start()
                sub_content_start_offset = match.end()

                if sub_content_start_offset < end_offset and self.text[sub_content_start_offset] == '\n':
                    sub_content_start_offset += 1

                if j + 1 < len(subsection_matches):
                    sub_end_offset = subsection_matches[j + 1].start()
                else:
                    sub_end_offset = end_offset
                
                sub_content = self.text[sub_content_start_offset:sub_end_offset].strip()

                chapter_map[title].append({
                    'id': j + 1,
                    'title': sub_title,
                    'start_offset': sub_start_offset,
                    'end_offset': sub_end_offset,
                    'content': sub_content
                })

        return chapter_map
    
    def find_end_sections(self):
        chapters = self.find_chapters()
        if not chapters:
            return []

        last_chapter_end_offset = chapters[-1][2]
        truncated_text = self.text[last_chapter_end_offset:]

        end_pattern = re.compile(
            r"^\s*#*\s*(?:Index|Bibliography|References|Appendix|Appendices|Glossary|Acknowledgements?|Notes|Endnotes|Afterword)\s*$",
            re.MULTILINE | re.IGNORECASE
        )

        end_sections = []

        matches = list(end_pattern.finditer(truncated_text))

        for i, match in enumerate(matches):
            title = match.group(0).strip().lstrip('#').strip()
            start_offset = match.start()
            content_start = match.end()

            if content_start < len(truncated_text) and truncated_text[content_start] == '\n':
                content_start += 1

            if i + 1 < len(matches):
                end_offset = matches[i + 1].start()
            else:
                end_offset = len(truncated_text)
            
            global_start_offset = last_chapter_end_offset + start_offset
            global_content_start = last_chapter_end_offset + content_start
            global_end_offset = last_chapter_end_offset + end_offset

            end_sections.append({
                'title': title,
                'start_offset': global_start_offset,
                'content_start': global_content_start,
                'end_offset': global_end_offset,
                'content': truncated_text[content_start:end_offset].strip()
            })

        return end_sections
    
    def find_paragraphs(self):
        return
    
    def find_note_references(self):
        reference_pattern = re.compile(r'\$\{\s*\}\^\{(\d+(?:,\d+)*)\}\$')
        references = []
        for match in reference_pattern.finditer(self.text):
            note_ids = match.group(1).split(',')
            offset = match.start()
            for note_id in note_ids:
                references.append((note_id.strip(), offset))

        return references
    
    def link_notes_to_text(self):
        chapters = self.find_chapters()
        notes_map = self.find_notes()
        references = self.find_note_references()

        if not chapters or not notes_map:
            return {"error": "Could not find chapters or notes to link."}

        chapters_with_notes = {title: [] for title, _, _ in chapters}
        chapters_with_notes['Unlinked Notes'] = []

        # Find the notes section boundaries to avoid matching references within it
        notes_header = re.search(r'^#{0,4}\s*Notes\s*$', self.text, re.MULTILINE | re.IGNORECASE)
        notes_section_start = notes_header.start() if notes_header else len(self.text)
        notes_section_end = len(self.text)  # Default to end of text
        
        if notes_header:
            # Try to find the end of the notes section by looking for the next major section
            next_section_pattern = re.compile(
                r"^\s*(?:Index|Bibliography|References|Appendix|Appendices|Glossary|Acknowledgements|Chapter|#)"
                r"(?:\s+\d+)?\s*$", 
                re.MULTILINE | re.IGNORECASE
            )
            next_section_match = next_section_pattern.search(self.text, pos=notes_header.end())
            if next_section_match:
                notes_section_end = next_section_match.start()

        # Group references by note_id to collect all offsets for each note
        note_references = {}
        for note_id, ref_offset in references:
            # Ignore references found within the notes section itself
            if notes_section_start <= ref_offset < notes_section_end:
                continue
                
            if note_id not in note_references:
                note_references[note_id] = []
            note_references[note_id].append(ref_offset)

        # Associate notes with chapters based on where their references appear
        for note_id, ref_offsets in note_references.items():
            note_text = notes_map.get(note_id)
            if not note_text:
                continue # skip if there is no corresponding note text

            # Find all chapters that contain references to this note
            found_in_any_chapter = False
            for title, start_offset, end_offset in chapters:
                # Check if any reference for this note is within this chapter
                chapter_refs = [offset for offset in ref_offsets if start_offset <= offset < end_offset]
                if chapter_refs:
                    chapters_with_notes[title].append({
                        'id': note_id, 
                        'text': note_text,
                        'reference_offsets': chapter_refs
                    })
                    found_in_any_chapter = True
                    # Don't break - continue to check other chapters

            if not found_in_any_chapter:
                chapters_with_notes['Unlinked Notes'].append({
                    'id': note_id, 
                    'text': note_text,
                    'reference_offsets': ref_offsets
                })

        return chapters_with_notes
