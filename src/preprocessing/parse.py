import re
import os
import nltk
import logging

logger = logging.getLogger(__name__)


class Parser:
    def __init__(self, text):
        self.original_text = text
        self.text = self._preprocess_note_references(text)
        self.offset_map = []  # Track original offsets for reference mapping
        self._cache = {}

    def _preprocess_note_references(self, text) -> str:
        reference_pattern = re.compile(r'\$\{\s*\}\^\{(\d+(?:,\d+)*)\}\$')
        
        # Find all note references
        matches = list(reference_pattern.finditer(text))
        if not matches:
            return text
        
        # Process matches in reverse order to maintain correct offsets
        processed_text = text
        for match in reversed(matches):
            start_pos = match.start()
            end_pos = match.end()
            note_ref = match.group(0)
            
            # Check if the note reference is on the same line as other text
            line_start = processed_text.rfind('\n', 0, start_pos) + 1
            line_end = processed_text.find('\n', end_pos)
            if line_end == -1:
                line_end = len(processed_text)
            
            # Check if there's other non-whitespace text on the same line
            before_text = processed_text[line_start:start_pos].strip()
            after_text = processed_text[end_pos:line_end].strip()
            
            if before_text or after_text:
                # There's other text on the same line, so isolate the note reference
                replacement = f"\n\n{note_ref}\n\n"
                processed_text = processed_text[:start_pos] + replacement + processed_text[end_pos:]
            else:
                # Note reference is already on its own line, just ensure proper spacing
                if start_pos > 0 and processed_text[start_pos-1] != '\n':
                    replacement = f"\n{note_ref}"
                    processed_text = processed_text[:start_pos] + replacement + processed_text[end_pos:]
                if end_pos < len(processed_text) and processed_text[end_pos] != '\n':
                    replacement = f"{note_ref}\n"
                    processed_text = processed_text[:start_pos] + replacement + processed_text[end_pos:]
        
        return processed_text
    
    def _remove_extraneous_newlines(self, text) -> str:
        """
        Remove newlines that appear mid-sentence, but preserve justified newlines
        like those after titles, notes, or at natural paragraph breaks.
        """
        if not text:
            return text
        
        # First, preserve double newlines (paragraph breaks) by replacing with placeholder
        placeholder = "<<<PARAGRAPH_BREAK>>>"
        text = re.sub(r'\n\n+', placeholder, text)
        
        # Split into lines for processing
        lines = text.split('\n')
        processed_lines = []
        
        i = 0
        while i < len(lines):
            current_line = lines[i].strip()
            
            # Always preserve empty lines
            if not current_line:
                processed_lines.append(lines[i])
                i += 1
                continue
            
            # Check if we should join this line with the next one
            should_join = False
            
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Join if:
                # 1. Current line doesn't end with sentence-ending punctuation
                # 2. Next line exists and is not empty
                # 3. Neither line looks like a structural element (header, note, etc.)
                
                if (next_line and  # Next line exists and is not empty
                    not re.search(r'[.!?]\s*$', current_line) and  # Current line doesn't end with sentence punctuation
                    not re.match(r'^\s*#+\s', current_line) and  # Current line is not a header (consistent with title_pattern)
                    not re.match(r'^\s*#+\s', next_line) and  # Next line is not a header
                    not re.match(r'^\s*#+\s*(?:\d+|[IVXLC]+)\s*$', current_line, re.IGNORECASE) and  # Current line is not a numbered chapter (consistent with main_content_pattern)
                    not re.match(r'^\s*#+\s*(?:\d+|[IVXLC]+)\s*$', next_line, re.IGNORECASE) and  # Next line is not a numbered chapter
                    not re.match(r'^(?:\[?(\d+|[ivxlc]+)\]?\.?\s+)', next_line) and  # Next line is not a numbered list item (consistent with listitem_pattern)
                    not re.match(r'^\[\^([^\]]+)\](?!:)', next_line) and  # Next line is not a footnote reference (consistent with footnote reference_pattern)
                    not re.match(r'^\[\^([^\]]+)\]:\s*', next_line) and  # Next line is not a footnote definition (consistent with footnote definition_pattern)
                    not re.search(r'\$\{\s*\}\^\{(\d+(?:,\d+)*)\}\$', current_line) and  # Current line doesn't have note reference (consistent with note reference_pattern)
                    not re.search(r'\$\{\s*\}\^\{(\d+(?:,\d+)*)\}\$', next_line) and  # Next line doesn't have note reference
                    not re.match(r'^#{0,4}\s*Notes\s*$', current_line, re.IGNORECASE) and  # Current line is not "Notes" header (consistent with header_pattern)
                    not re.match(r'^#{0,4}\s*Notes\s*$', next_line, re.IGNORECASE) and  # Next line is not "Notes" header
                    not re.match(r'^\s*#*\s*(?:Bibliography|Index|References|Appendix|Appendices|Glossary|(?:Publisher\'?s?\s*)?Acknowledgements?|Endnotes|Afterword|Notes)\s*$', current_line, re.IGNORECASE) and  # Current line is not end section (consistent with end_pattern)
                    not re.match(r'^\s*#*\s*(?:Bibliography|Index|References|Appendix|Appendices|Glossary|(?:Publisher\'?s?\s*)?Acknowledgements?|Endnotes|Afterword|Notes)\s*$', next_line, re.IGNORECASE) and  # Next line is not end section
                    not re.match(r'^#+\s*(?:Contents|Introduction|Preface|Prologue|(?:Publisher\'?s?\s*)?Acknowledgements?)\s*$', current_line, re.IGNORECASE) and  # Current line is not intro section (consistent with intro_pattern)
                    not re.match(r'^#+\s*(?:Contents|Introduction|Preface|Prologue|(?:Publisher\'?s?\s*)?Acknowledgements?)\s*$', next_line, re.IGNORECASE)):  # Next line is not intro section
                    should_join = True
            
            if should_join:
                # Join current line with next line, adding a space
                joined_line = lines[i].rstrip() + ' ' + lines[i + 1].lstrip()
                processed_lines.append(joined_line)
                i += 2  # Skip the next line since we've joined it
            else:
                processed_lines.append(lines[i])
                i += 1
        
        # Join the lines back and restore paragraph breaks
        result = '\n'.join(processed_lines)
        result = result.replace(placeholder, '\n\n')
        
        return result

    def find_title(self) -> str:
        if 'title' in self._cache:
            return self._cache['title']
        
        title_pattern = re.compile(r"^\s*#+\s*([^\n]+)")
        match = title_pattern.match(self.text)
        if match:
            title = match.group(1).strip()
            self._cache['title'] = title
            return title
        
        self._cache['title'] = None
        return None

    def find_notes(self) -> dict:
        if 'notes' in self._cache:
            return self._cache['notes']

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
                self._cache['notes'] = notes_map
                return notes_map
        
        self._cache['notes'] = notes_map
        return notes_map
    
    def find_footnotes(self) -> dict:
        if 'footnotes' in self._cache:
            return self._cache['footnotes']

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
                'text': match.group(2).strip(),
                'start_offset': match.start(),
                'end_offset': match.end()
            }
            
            definitions.append(definition)
            def_id += 1

        result = {
            'references': references,
            'definitions': definitions
        }
        self._cache['footnotes'] = result
        return result

    def find_chapters(self, intro_sections, end_sections) -> list[dict]:
        # Calculate the search boundaries from arguments
        intro_end_offset = 0
        if intro_sections:
            intro_end_offset = max(section['end_offset'] for section in intro_sections)
        
        end_start_offset = len(self.text)
        if end_sections:
            end_start_offset = min(section['start_offset'] for section in end_sections)
        
        logger.debug(f"Chapter search boundaries: intro_end={intro_end_offset}, end_start={end_start_offset}")
        
        # Search for chapters only in the content between intro and end sections
        search_text = self.text[intro_end_offset:end_start_offset]
        
        # Pattern to match: # NUM followed by ## Title
        # This matches the structure: # 1 \n ## Title
        # Be more specific to avoid matching subsection headers as chapters
        main_chapter_pattern = re.compile(
            r'^\s*#\s*(?:\d+|[IVXLC]+)\s*\n+\s*#{1,2}\s*([^#\n]+)',
            re.MULTILINE | re.IGNORECASE
        )

        chapter_matches = list(main_chapter_pattern.finditer(search_text))
        logger.debug(f"Found {len(chapter_matches)} chapters with main pattern")

        if not chapter_matches:
            # Fallback: look for numbered headers with substantial content
            fallback_pattern = re.compile(
                r"^\s*#+\s*(?:\d+|[IVXLC]+)\s*$",
                re.MULTILINE | re.IGNORECASE
            )
            fallback_matches = list(fallback_pattern.finditer(search_text))
            logger.debug(f"Using fallback pattern, found {len(fallback_matches)} potential chapters")
            
            # Filter to only include chapters with substantial content and meaningful titles
            main_chapters = []
            for i, match in enumerate(fallback_matches):
                start_offset = match.start() + intro_end_offset
                header_end_offset = match.end() + intro_end_offset
                chapter_num_text = match.group(0).strip()
                
                # Look for content after the chapter number
                content_start = match.end()
                if content_start < len(search_text) and search_text[content_start] == '\n':
                    content_start += 1
                
                # Find the end of this chapter
                if i + 1 < len(fallback_matches):
                    next_chapter_start = fallback_matches[i + 1].start()
                    end_offset = next_chapter_start + intro_end_offset
                else:
                    end_offset = end_start_offset
                
                chapter_content = search_text[content_start:end_offset - intro_end_offset]
                
                # Look for a title in the first few lines
                lines = chapter_content.split('\n')[:10]  # Increased from 5 to 10 lines
                title_text = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith('#') and not re.match(r'^\s*#+\s*(?:\d+|[IVXLC]+)\s*$', line):
                        title_text = line.lstrip('#').strip()
                        break
                
                # More flexible content validation:
                # 1. Has a meaningful title (not empty) OR has substantial content
                # 2. Reduced minimum content length requirement
                # 3. Skip if it's likely a Notes section masquerading as a chapter
                is_likely_notes = (
                    title_text.lower() == 'notes' or 
                    chapter_content.strip().lower().startswith('notes') or
                    (len(chapter_content.strip()) > 0 and 
                     re.match(r'^\s*\d+\.\s', chapter_content.strip()))  # Starts with numbered list
                )
                
                content_length = len(chapter_content.strip())
                has_meaningful_title = title_text and title_text.lower() != 'notes'
                has_substantial_content = content_length > 1000
                
                if (has_meaningful_title or has_substantial_content) and not is_likely_notes:
                    num_match = re.search(r'(\d+|[IVXLC]+)', chapter_num_text)
                    if num_match:
                        chapter_num = num_match.group(1)
                        if title_text:
                            title = f"Chapter {chapter_num}: {title_text}"
                        else:
                            title = f"Chapter {chapter_num}"
                    else:
                        title = title_text or f"Chapter {i + 1}"
                    
                    main_chapters.append({
                        'title': title,
                        'start_offset': start_offset,
                        'end_offset': end_offset,
                        'header_end_offset': header_end_offset
                    })
            
            logger.debug(f"After filtering, found {len(main_chapters)} valid chapters")
            return main_chapters

        # Process the main pattern matches
        chapters = []
        for i, match in enumerate(chapter_matches):
            start_offset = match.start() + intro_end_offset
            header_end_offset = match.end() + intro_end_offset
            title_text = match.group(1).strip()
            
            # Extract chapter number from the full match
            full_match = match.group(0)
            num_match = re.search(r'(\d+|[IVXLC]+)', full_match)
            if num_match:
                chapter_num = num_match.group(1)
                title = f"Chapter {chapter_num}: {title_text}"
            else:
                title = title_text
            
            # Calculate end offset
            if i + 1 < len(chapter_matches):
                end_offset = chapter_matches[i + 1].start() + intro_end_offset
            else:
                end_offset = end_start_offset
            
            chapters.append({
                'title': title,
                'start_offset': start_offset,
                'end_offset': end_offset,
                'header_end_offset': header_end_offset
            })

        # Improved filtering to remove subsections that might be mistaken for chapters
        # while being more permissive of legitimate chapters
        # Also extend chapter boundaries to include any skipped content
        filtered_chapters = []
        seen_chapter_numbers = set()
        max_chapter_number = 0
        
        for i, chapter in enumerate(chapters):
            title = chapter['title']
            start = chapter['start_offset']
            end = chapter['end_offset']
            
            # Extract the chapter number
            num_match = re.search(r'Chapter (\d+)', title)
            if num_match:
                chapter_num = int(num_match.group(1))
                
                # If this chapter number is lower than the highest we've seen,
                # it's likely a subsection that was incorrectly identified as a chapter
                if chapter_num < max_chapter_number:
                    logger.debug(f"Skipping '{title}' - chapter number {chapter_num} appears after chapter {max_chapter_number}")
                    # Extend the previous chapter to include this skipped content
                    if filtered_chapters:
                        # Extend to include the skipped chapter's content
                        filtered_chapters[-1]['end_offset'] = end
                        logger.debug(f"Extended previous chapter '{filtered_chapters[-1]['title']}' to include skipped content, new end: {end}")
                    continue
                
                # Allow duplicate chapter numbers but with different titles at the same level
                # This handles cases where parsing might create multiple entries for the same chapter
                chapter_key = (chapter_num, title)
                if chapter_key not in seen_chapter_numbers:
                    seen_chapter_numbers.add(chapter_key)
                    max_chapter_number = max(max_chapter_number, chapter_num)
                    filtered_chapters.append(chapter)
                else:
                    logger.debug(f"Skipping duplicate chapter: {title}")
                    # Also extend previous chapter for duplicate content
                    if filtered_chapters:
                        filtered_chapters[-1]['end_offset'] = end
                        logger.debug(f"Extended previous chapter '{filtered_chapters[-1]['title']}' to include duplicate content, new end: {end}")
            else:
                # If no chapter number found, include it anyway (but don't update max_chapter_number)
                filtered_chapters.append(chapter)

        logger.debug(f"After filtering, found {len(filtered_chapters)} final chapters")
        return filtered_chapters

    def find_intro_sections(self) -> list[dict]:
        if 'intro_sections' in self._cache:
            return self._cache['intro_sections']

        # First, find where the main content (numbered chapters) starts
        main_content_pattern = re.compile(
            r'^\s*#+\s*(?:\d+|[IVXLC]+)\s*$',  # Numbered headers
            re.MULTILINE | re.IGNORECASE
        )
        
        main_content_matches = list(main_content_pattern.finditer(self.text))
        if main_content_matches:
            first_chapter_start = main_content_matches[0].start()
        else:
            # If no numbered chapters, search the entire text
            first_chapter_start = len(self.text)
        
        # Only look for intro sections before the first chapter
        intro_search_text = self.text[:first_chapter_start]
        
        # More flexible pattern that handles variations in section names
        intro_pattern = re.compile(
            r'^#+\s*(?:Contents|Introduction|Preface|Prologue|(?:Publisher\'?s?\s*)?Acknowledgements?)\s*$', 
            re.MULTILINE | re.IGNORECASE
        )
        
        # Find all intro section headers within the search range
        intro_matches = list(intro_pattern.finditer(intro_search_text))
        if not intro_matches:
            self._cache['intro_sections'] = []
            return []
        
        # Extract full sections with their content
        intro_sections = []
        for i, match in enumerate(intro_matches):
            # Normalize the title for consistent output
            title = match.group(0).strip().lstrip('#').strip()
            # Simplify "Publisher's Acknowledgements" to "Acknowledgements" for consistency
            if 'publisher' in title.lower() and 'acknowledgement' in title.lower():
                title = "Acknowledgements"
            
            start_offset = match.start()
            content_start = match.end()
            
            # Skip the newline after the header if present
            if content_start < len(intro_search_text) and intro_search_text[content_start] == '\n':
                content_start += 1
            
            # Find the end of this section
            if i + 1 < len(intro_matches):
                # Next intro section exists
                end_offset = intro_matches[i + 1].start()
            else:
                # Last intro section, ends at main content
                end_offset = first_chapter_start
            
            intro_sections.append({
                'title': title,
                'start_offset': start_offset,
                'content_start': content_start,
                'end_offset': end_offset,
                'text': self.text[content_start:end_offset].strip()
            })
        
        self._cache['intro_sections'] = intro_sections
        return intro_sections

    def find_end_sections(self) -> list[dict]:
        if 'end_sections' in self._cache:
            return self._cache['end_sections']

        # Look for end sections like Bibliography, Index, etc.
        end_pattern = re.compile(
            r"^\s*#*\s*(?:Bibliography|Index|References|Appendix|Appendices|Glossary|(?:Publisher\'?s?\s*)?Acknowledgements?|Endnotes|Afterword|Notes)\s*$",
            re.MULTILINE | re.IGNORECASE
        )

        end_matches = list(end_pattern.finditer(self.text))
        if not end_matches:
            self._cache['end_sections'] = []
            return []

        # Find ALL numbered chapters to better understand document structure
        main_content_pattern = re.compile(
            r'^\s*#+\s*(?:\d+|[IVXLC]+)\s*$',  # Numbered headers
            re.MULTILINE | re.IGNORECASE
        )
        
        main_content_matches = list(main_content_pattern.finditer(self.text))
        if main_content_matches:
            # Find the last numbered chapter
            last_chapter = main_content_matches[-1]
            min_end_start = last_chapter.end()
            num_chapters = len(main_content_matches)
        else:
            min_end_start = 0
            num_chapters = 0

        # Only include sections that come after the last numbered chapter
        # with improved filtering for chapter-level Notes sections
        valid_end_matches = []
        for match in end_matches:
            if match.start() >= min_end_start:
                title = match.group(0).strip().lstrip('#').strip()
                
                # Enhanced filtering for Notes sections
                if title.lower() == 'notes':
                    # Multiple checks to determine if this is a document-level notes section
                    is_document_level = False
                    
                    # Check 1: Position relative to document end (must be in last 15% of document)
                    distance_from_end = len(self.text) - match.start()
                    position_ratio = distance_from_end / len(self.text)
                    
                    # Check 2: Must come after a substantial number of chapters (at least 3)
                    comes_after_chapters = num_chapters >= 3
                    
                    # Check 3: Look ahead to see if there are more numbered chapters after this Notes section
                    # If there are, it's likely a chapter-level Notes section
                    text_after_notes = self.text[match.start():]
                    subsequent_chapters = main_content_pattern.findall(text_after_notes)
                    has_subsequent_chapters = len(subsequent_chapters) > 0
                    
                    # Check 4: Content length - document-level notes are typically substantial
                    content_start = match.end()
                    if content_start < len(self.text) and self.text[content_start] == '\n':
                        content_start += 1
                    
                    # Find the end of this notes section
                    next_section_start = len(self.text)
                    for future_match in end_matches:
                        if future_match.start() > match.start():
                            next_section_start = future_match.start()
                            break
                    
                    notes_content = self.text[content_start:next_section_start].strip()
                    content_length = len(notes_content)
                    
                    # A Notes section is document-level if:
                    # - It's in the last 15% of the document AND
                    # - It comes after multiple chapters AND
                    # - It has no subsequent numbered chapters AND
                    # - It has substantial content (>1000 characters)
                    is_document_level = (
                        position_ratio <= 0.15 and
                        comes_after_chapters and
                        not has_subsequent_chapters and
                        content_length > 1000
                    )
                    
                    if not is_document_level:
                        logger.debug(f"Skipping chapter-level Notes section at position {match.start()}")
                        continue  # Skip chapter-level notes sections
                
                valid_end_matches.append(match)

        if not valid_end_matches:
            logger.debug("No valid end sections found")
            self._cache['end_sections'] = []
            return []
        
        logger.debug(f"Found {len(valid_end_matches)} valid end sections")

        end_sections = []
        for i, match in enumerate(valid_end_matches):
            title = match.group(0).strip().lstrip('#').strip()
            start_offset = match.start()
            content_start = match.end()

            if content_start < len(self.text) and self.text[content_start] == '\n':
                content_start += 1

            if i + 1 < len(valid_end_matches):
                end_offset = valid_end_matches[i + 1].start()
            else:
                end_offset = len(self.text)

            logger.debug(f"Processing end section '{title}' at position {start_offset}-{end_offset}")

            end_sections.append({
                'title': title,
                'start_offset': start_offset,
                'content_start': content_start,
                'end_offset': end_offset,
                'text': self.text[content_start:end_offset].strip()
            })

        logger.debug(f"Final end sections: {[s['title'] for s in end_sections]}")
        self._cache['end_sections'] = end_sections
        return end_sections

    def find_chapter_subsections(self, chapters: list[dict]) -> dict:
        if not chapters:
            return {}

        chapter_map = {}

        # Regex to find markdown headers (e.g., #, ## Subsection)
        subsection_pattern = re.compile(r"^\s*#+\s*(.+?)\s*$", re.MULTILINE)

        for i, chapter in enumerate(chapters):
            title = chapter['title']
            start_offset = chapter['start_offset']
            end_offset = chapter['end_offset']
            content_start = chapter.get('header_end_offset', start_offset)
            
            chapter_map[title] = []
            
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
                    'text': sub_content
                })

        return chapter_map
    
    def find_paragraphs_in_block(self, content_text, content_start_offset, decompose_into_atoms=False) -> list[dict]:
        paragraphs = []
        if not content_text:
            return paragraphs
        
        # Clean up extraneous newlines before processing
        content_text = self._remove_extraneous_newlines(content_text)

        # Find all paragraph breaks (double newlines)
        paragraph_breaks = list(re.finditer(r'\n\n+', content_text))
        
        current_pos = 0
        para_id = 1
        
        # Iterate through the breaks to identify paragraphs
        for p_break in paragraph_breaks:
            para_end = p_break.start()
            para_text = content_text[current_pos:para_end]
            
            stripped_text = para_text.strip()
            if stripped_text:
                paragraph = {
                    'id': para_id,
                    'text': stripped_text,
                    'start_offset': content_start_offset + current_pos,
                    'end_offset': content_start_offset + para_end,
                }
                
                # Add atoms if decomposition is requested
                if decompose_into_atoms:
                    paragraph['atoms'] = self.decompose_paragraph(
                        stripped_text, 
                        content_start_offset + current_pos
                    )
                
                paragraphs.append(paragraph)
                para_id += 1
            
            current_pos = p_break.end()

        # Handle the last paragraph after the final break
        last_para_text = content_text[current_pos:]
        stripped_last_para = last_para_text.strip()
        if stripped_last_para:
            paragraph = {
                'id': para_id,
                'text': stripped_last_para,
                'start_offset': content_start_offset + current_pos,
                'end_offset': content_start_offset + len(content_text),
            }
            
            # Add atoms if decomposition is requested
            if decompose_into_atoms:
                paragraph['atoms'] = self.decompose_paragraph(
                    stripped_last_para, 
                    content_start_offset + current_pos
                )
            
            paragraphs.append(paragraph)
            
        return paragraphs

    def find_paragraphs(self, intro_sections, chapters, chapter_subsections) -> dict:
        # Process introduction sections from arguments
        for intro in intro_sections:
            content_text = intro.get('text', '')
            content_start_offset = intro.get('content_start', 0)
            
            # Do not decompose introduction sections for now
            intro['paragraphs'] = self.find_paragraphs_in_block(
                content_text, 
                content_start_offset, 
                decompose_into_atoms=False
            )
        # Process chapters and subsections from arguments
        processed_chapters = {}
        for chapter in chapters:
            chapter_title = chapter['title']
            subsections = chapter_subsections.get(chapter_title, [])

            processed_chapter = {
                'title': chapter_title,
                'start_offset': chapter.get('start_offset'),
                'end_offset': chapter.get('end_offset'),
                'subsections': [],
                'paragraphs': []
            }

            if not subsections:
                # Find chapter content if there are no subsections
                content_start = chapter.get('header_end_offset', chapter.get('start_offset', 0))
                end_offset = chapter.get('end_offset', 0)

                if content_start < len(self.text) and self.text[content_start] == '\n':
                    content_start += 1
                
                content_text = self.text[content_start:end_offset]
                processed_chapter['paragraphs'] = self.find_paragraphs_in_block(content_text, content_start, decompose_into_atoms=True)
            else:
                for subsection in subsections:
                    subsection_content = subsection.get('text', '')
                    
                    header_end = self.text.find(subsection_content, subsection['start_offset'])
                    if header_end == -1:
                        header_end = subsection['start_offset']

                    subsection['paragraphs'] = self.find_paragraphs_in_block(subsection_content, header_end, decompose_into_atoms=True)
                    processed_chapter['subsections'].append(subsection)
            
            processed_chapters[chapter_title] = processed_chapter

        return {
            "introductions": intro_sections,
            "chapters": processed_chapters
        }
    
    def find_note_references(self) -> list[tuple[str, int]]:
        reference_pattern = re.compile(r'\$\{\s*\}\^\{(\d+(?:,\d+)*)\}\$') # matches on note references like ${ }^{(1,2,3)} $
        references = []
        for match in reference_pattern.finditer(self.original_text):
            note_ids = match.group(1).split(',')
            offset = match.start()
            for note_id in note_ids:
                references.append((note_id.strip(), offset))

        return references
    
    def link_notes_to_text(self, chapters, notes_map, note_references) -> dict:
        if not chapters or not notes_map:
            return {"error": "Could not find chapters or notes to link."}

        chapters_with_notes = {c['title']: [] for c in chapters}
        chapters_with_notes['Unlinked Notes'] = []

        # Find the notes section boundaries to avoid matching references within it
        notes_header = re.search(r'^#{0,4}\s*Notes\s*$', self.original_text, re.MULTILINE | re.IGNORECASE)
        notes_section_start = notes_header.start() if notes_header else len(self.original_text)
        notes_section_end = len(self.original_text)  # Default to end of text
        
        if notes_header:
            # Try to find the end of the notes section by looking for the next major section
            next_section_pattern = re.compile(
                r"^\s*(?:Index|Bibliography|References|Appendix|Appendices|Glossary|Acknowledgements|Chapter|#)"
                r"(?:\s+\d+)?\s*$", 
                re.MULTILINE | re.IGNORECASE
            )
            next_section_match = next_section_pattern.search(self.original_text, pos=notes_header.end())
            if next_section_match:
                notes_section_end = next_section_match.start()

        # Group references by note_id to collect all offsets for each note
        references_by_id = {}
        for note_id, ref_offset in note_references:
            # Ignore references found within the notes section itself
            if notes_section_start <= ref_offset < notes_section_end:
                continue
                
            if note_id not in references_by_id:
                references_by_id[note_id] = []
            references_by_id[note_id].append(ref_offset)

        # Associate notes with chapters based on where their references appear
        for note_id, ref_offsets in references_by_id.items():
            note_text = notes_map.get(note_id)
            if not note_text:
                continue # skip if there is no corresponding note text

            # Find all chapters that contain references to this note
            found_in_any_chapter = False
            for chapter in chapters:
                title, start_offset, end_offset = chapter['title'], chapter['start_offset'], chapter['end_offset']
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
    
    def parse_bibliography_entries(self, bibliography_content, bib_start_offset) -> dict:
        bib_map = {}
        bib_pattern = re.compile(r"^([A-Z][\w\s,.\-&]+?)\.\s*\((\d{4}[a-z]?|forthcoming)\)\.\s*(.*)", re.MULTILINE)

        for match in bib_pattern.finditer(bibliography_content):
            author_str = match.group(1).strip()
            year_str = match.group(2).strip()

            primary_author_last_name = author_str.split(',')[0].split()[-1].lower()
            key = f"{primary_author_last_name}_{year_str}"

            entry_start = match.start()
            next_match = bib_pattern.search(bibliography_content, pos=match.end())
            entry_end = next_match.start() if next_match else len(bibliography_content)

            full_text = bibliography_content[entry_start:entry_end].strip()

            bib_map[key] = {
                "key": key,
                "author": author_str,
                "year": year_str,
                "full_text": full_text,
                "start_offset": bib_start_offset + entry_start,
                "end_offset": bib_start_offset + entry_end,
                "citations": []
            }

        return bib_map
    
    def find_intext_citations(self, paragraphs) -> list[dict]:
        citations = []

        # Pattern 1: Standard parenthetical citation, e.g., (Williamson 2007a: 99-105) or (2004: 407)
        # This is intentionally broad to capture contents for later parsing.
        citation_pattern = re.compile(r'\(([^)]+?)\)')

        # heuristic -- keep track of last author in paragraph
        last_author_in_paragraph = None

        for paragraph in paragraphs:
            last_author_in_paragraph = None # reset for each paragraph

            explicit_authors = list(re.finditer(r'\b([A-Z][a-z]+)\s+\(?(?:\d{4}|forthcoming)', paragraph['text']))
            if explicit_authors:
                last_author_in_paragraph = explicit_authors[-1].group(1).lower()

            for match in citation_pattern.finditer(paragraph['text']):
                content = match.group(1)
                page_info = None

                page_match = re.search(r':\s*([0-9\-]+)$', content)
                if page_match:
                    page_info = page_match.group(1)
                    content = content[:page_match.start()].strip() # remove page info for easier parsing

                # Split by comma or semicolon to handle multiple citations like (Boghossian 1996, 2003b)
                parts = re.split(r'\s*[,;]\s*', content)

                for part in parts:
                    author = None
                    year = None

                    # try to parse author/year format
                    author_year_match = re.match(r'([A-Za-z\s,]+?)\s+(\d{4}[a-z]?|forthcoming)', part)
                    if author_year_match:
                        author = author_year_match.group(1).strip().split(',')[-1].strip().lower()
                        year = author_year_match.group(2)
                        last_author_in_paragraph = author

                    else:
                        # try to parse just year format
                        year_match = re.match(r'(\d{4}[a-z]?|forthcoming)', part)
                        if year_match and last_author_in_paragraph:
                            author = last_author_in_paragraph
                            year = year_match.group(1)

                    if author and year:
                        key = f"{author}_{year}"
                        citations.append({
                            'author': author,
                            'year': year,
                            'key': key,
                            'page_info': page_info,
                            'start_offset': paragraph['start_offset'] + match.start(),
                            'end_offset': paragraph['start_offset'] + match.end(),
                            'full_text': match.group(0)
                        })

        return citations
    
    def link_citations_to_bibliography(self, bibliography_section, all_paragraphs) -> dict:
        if not bibliography_section:
            return {"entries": {}, "unlinked_citations": []}
        
        bib_text = bibliography_section.get('text', '')
        bib_offset = bibliography_section.get('content_start', 0)

        bib_map = self.parse_bibliography_entries(bib_text, bib_offset)

        intext_citations = self.find_intext_citations(all_paragraphs)

        # link citations to bibliography
        unlinked_citations = []
        for citation in intext_citations:
            key = citation.get('key')
            if key and key in bib_map:
                citation_copy = citation.copy()
                citation_copy.pop('key', None)  # Remove key from citation before adding
                bib_map[key]['citations'].append(citation_copy)
            else:
                unlinked_citations.append(citation)

        return {
            "entries": bib_map,
            "unlinked_citations": unlinked_citations
        }
    
    def decompose_paragraph(self, paragraph_text: str, paragraph_start_offset: int) -> list[dict]:
        citation_pattern = r'(\s*\([^)]+\d{4}[^)]*\)|\s*\[\^?\d+\]|\s*\$\{\s*\}\^\{(\d+(?:,\d+)*)\}\$)' # matches 

        atoms = []
        atom_id = 1
        
        # Split by citation pattern and track where each part starts
        parts = re.split(citation_pattern, paragraph_text)
        current_offset = 0
        
        for part in parts:
            if not part or part.isspace():
                current_offset += len(part) if part else 0
                continue
                
            # Find the actual start position of this part in the original text
            part_start = paragraph_text.find(part, current_offset)
            if part_start == -1:
                part_start = current_offset
                
            # if part is a citation, add it after skipping whitespace
            if re.fullmatch(citation_pattern, part):
                clean_part = part.strip()
                if clean_part:
                    # Find where the cleaned part starts within the original part
                    clean_start = part.find(clean_part)
                    atom_start = part_start + clean_start
                    atom_end = atom_start + len(clean_part)
                    
                    atoms.append({
                        'id': atom_id,
                        'text': clean_part,
                        'start_offset': paragraph_start_offset + atom_start,
                        'end_offset': paragraph_start_offset + atom_end,
                        'type': 'citation'
                    })
                    atom_id += 1
            else:
                # otherwise, tokenize as regular sentence
                sentences = nltk.sent_tokenize(part)
                sentence_offset = 0
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue

                    # Find where this sentence starts in the part
                    sentence_start = part.find(sentence, sentence_offset)
                    if sentence_start == -1:
                        sentence_start = sentence_offset
                    
                    sentence_offset = sentence_start + len(sentence)
                    
                    if ':' not in sentence:
                        atoms.append({
                            'id': atom_id,
                            'text': sentence,
                            'start_offset': paragraph_start_offset + part_start + sentence_start,
                            'end_offset': paragraph_start_offset + part_start + sentence_start + len(sentence),
                            'type': 'sentence'
                        })
                        atom_id += 1
                        continue
                    
                    # If a sentence contains a colon, we might want to split it.
                    # However, we should not split if the colon is inside parentheses,
                    # as this is common in citations or asides.
                    paren_level = 0
                    colon_index = -1
                    for i, char in enumerate(sentence):
                        if char == '(':
                            paren_level += 1
                        elif char == ')':
                            paren_level = max(0, paren_level - 1) # handle malformed
                        elif char == ':' and paren_level == 0:
                            # Found a colon outside of parentheses, split here
                            colon_index = i
                            break
                    
                    if colon_index != -1:
                        # Split the sentence at the first valid colon
                        sub_parts = [sentence[:colon_index].strip(), sentence[colon_index+1:].strip()]
                        sub_offset = 0
                        for sub_part in sub_parts:
                            if sub_part:
                                sub_start = sentence.find(sub_part, sub_offset)
                                if sub_start == -1:
                                    sub_start = sub_offset
                                sub_offset = sub_start + len(sub_part)
                                
                                atoms.append({
                                    'id': atom_id,
                                    'text': sub_part,
                                    'start_offset': paragraph_start_offset + part_start + sentence_start + sub_start,
                                    'end_offset': paragraph_start_offset + part_start + sentence_start + sub_start + len(sub_part),
                                    'type': 'sentence'
                                })
                                atom_id += 1
                    else:
                        # All colons are inside parentheses, so don't split
                        atoms.append({
                            'id': atom_id,
                            'text': sentence,
                            'start_offset': paragraph_start_offset + part_start + sentence_start,
                            'end_offset': paragraph_start_offset + part_start + sentence_start + len(sentence),
                            'type': 'sentence'
                        })
                        atom_id += 1
                        
            current_offset = part_start + len(part)

        return atoms
    
    def parse(self, chapters_with_text: list[dict] = None) -> dict:
        if chapters_with_text:
            return self.parse_from_pre_chunked_chapters(chapters_with_text)
        else:
            return self.parse_with_regex_fallback()

    def parse_from_pre_chunked_chapters(self, chapters_with_text: list[dict]) -> dict:
        # Reconstruct the full text for context-dependent parsing (notes, bibliography)
        # and create an offset map to translate chapter-local offsets to global offsets.
        full_text = ""
        offset = 0
        text_map = []
        for chapter in chapters_with_text:
            chapter_text = chapter.get('text', '')
            text_map.append({'title': chapter['title'], 'start_offset': offset})
            full_text += chapter_text + "\n\n" # Add separators for context
            offset = len(full_text)
        
        # We need a temporary parser instance for the full reconstructed text
        # to find elements that span across chapters, like notes and bibliography.
        context_parser = Parser(full_text)

        # 1. Identify Structure (Chapters are pre-defined)
        title = None # Title is not available at this level
        
        chapters = []
        for i, item in enumerate(text_map):
            start_offset = item['start_offset']
            end_offset = text_map[i+1]['start_offset'] if i + 1 < len(text_map) else len(full_text)
            chapters.append({
                'title': item['title'],
                'start_offset': start_offset,
                'end_offset': end_offset,
                'header_end_offset': start_offset # No distinct header in this case
            })

        chapter_subsections = context_parser.find_chapter_subsections(chapters)

        # 2. Extract Content (Paragraphs)
        main_content = context_parser.find_paragraphs([], chapters, chapter_subsections)

        # 3. Handle End Sections & Bibliography (use context parser)
        end_sections = context_parser.find_end_sections()
        bibliography_section = None
        other_end_sections = []
        for section in end_sections:
            if section['title'].lower() == 'bibliography':
                bibliography_section = section
            else:
                section['paragraphs'] = context_parser.find_paragraphs_in_block(
                    content_text=section.get('text', ''),
                    content_start_offset=section.get('content_start', 0)
                )
                other_end_sections.append(section)

        # 4. Handle Annotations (use context parser)
        notes_map = context_parser.find_notes()
        note_references = context_parser.find_note_references()
        linked_notes_map = context_parser.link_notes_to_text(chapters, notes_map, note_references)
        footnotes = context_parser.find_footnotes()
        
        # 5. Handle Citations
        all_paragraphs = []
        for chapter in main_content.get('chapters', {}).values():
            all_paragraphs.extend(chapter.get('paragraphs', []))
            for subsection in chapter.get('subsections', []):
                all_paragraphs.extend(subsection.get('paragraphs', []))
        
        bibliography_data = context_parser.link_citations_to_bibliography(bibliography_section, all_paragraphs)
        
        # 6. Assemble Document
        doc = {
            "title": title,
            "introductions": [],
            "chapters": main_content.get('chapters', {}),
            "end_sections": other_end_sections,
            "notes": notes_map,
            "linked_notes": linked_notes_map,
            "footnotes": footnotes,
            "bibliography": bibliography_data
        }
        return doc

    def parse_with_regex_fallback(self) -> dict:
        # 1. Identify Structure
        title = self.find_title()
        intro_sections = self.find_intro_sections()
        end_sections = self.find_end_sections()
        chapters = self.find_chapters(intro_sections, end_sections)
        chapter_subsections = self.find_chapter_subsections(chapters)

        # 2. Extract Content (Paragraphs)
        main_content = self.find_paragraphs(intro_sections, chapters, chapter_subsections)

        # 3. Handle End Sections & Bibliography
        bibliography_section = None
        other_end_sections = []
        for section in end_sections:
            if section['title'].lower() == 'bibliography':
                bibliography_section = section
            else:
                # Add paragraph data to other end sections
                section['paragraphs'] = self.find_paragraphs_in_block(
                    content_text=section.get('text', ''),
                    content_start_offset=section.get('content_start', 0)
                )
                other_end_sections.append(section)

        # 4. Handle Annotations
        notes_map = self.find_notes()
        note_references = self.find_note_references()
        linked_notes_map = self.link_notes_to_text(chapters, notes_map, note_references)
        footnotes = self.find_footnotes()

        # 5. Handle Citations
        all_paragraphs = []
        for intro in main_content.get('introductions', []):
            all_paragraphs.extend(intro.get('paragraphs', []))
        for chapter in main_content.get('chapters', {}).values():
            all_paragraphs.extend(chapter.get('paragraphs', []))
            for subsection in chapter.get('subsections', []):
                all_paragraphs.extend(subsection.get('paragraphs', []))
        
        bibliography_data = self.link_citations_to_bibliography(bibliography_section, all_paragraphs)

        # 6. Assemble Document
        doc = {
            "title": title,
            "introductions": main_content.get('introductions', []),
            "chapters": main_content.get('chapters', {}),
            "end_sections": other_end_sections,
            "notes": notes_map,
            "linked_notes": linked_notes_map,
            "footnotes": footnotes,
            "bibliography": bibliography_data
        }
        return doc
