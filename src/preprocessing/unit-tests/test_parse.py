import unittest
import os
import json
from src.preprocessing.parse import Parser
import re

class TestParser(unittest.TestCase):
    def test_find_notes(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'notes.txt')

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        notes = parser.find_notes()
        
        print("Detected notes:", notes)
        for note_num, note_text in notes.items():
            print(f"Note {note_num}: {note_text}")

        # Example assertion: Check if any notes were found
        self.assertTrue(len(notes) > 0)

    def test_find_footnotes_from_file(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'footnotes.txt')

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        footnotes = parser.find_footnotes()
        
        print("Detected footnotes from footnotes.txt:", footnotes)
        
        # Test that we get the expected structure
        self.assertIsInstance(footnotes, dict)
        self.assertIn('references', footnotes)
        self.assertIn('definitions', footnotes)
        
        references = footnotes['references']
        definitions = footnotes['definitions']
        
        # Test that we found at least one reference and one definition
        self.assertTrue(len(references) > 0, "Should find at least one footnote reference")
        self.assertTrue(len(definitions) > 0, "Should find at least one footnote definition")
        
        # Test the specific footnote reference [^0]
        self.assertEqual(references[0]['identifier'], '0')
        self.assertEqual(references[0]['id'], 1)
        
        # Test the specific footnote definition [^0]: ...
        self.assertEqual(definitions[0]['identifier'], '0')
        self.assertEqual(definitions[0]['id'], 1)
        self.assertIn('This paper was published', definitions[0]['content'])
        self.assertIn('Williamson on the A Priori and the Analytic', definitions[0]['content'])
        
        print(f"Found {len(references)} references and {len(definitions)} definitions")
        for ref in references:
            print(f"Reference {ref['id']}: [^{ref['identifier']}] at offset {ref['start_offset']}")
        for defn in definitions:
            print(f"Definition {defn['id']}: [^{defn['identifier']}] - {defn['content'][:50]}...")

    def test_find_chapters(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'apriori.txt')

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        # Get intro and end sections first as required by the new method signature
        intro_sections = parser.find_intro_sections()
        end_sections = parser.find_end_sections()
        chapters = parser.find_chapters(intro_sections, end_sections)

        print(f"Found {len(chapters)} chapters in apriori.txt.")
        for i, chapter in enumerate(chapters):
            print(f"  {i+1}: {chapter[0]}")

        # Example assertion: Check if chapters are found
        self.assertIsInstance(chapters, list)
        self.assertEqual(len(chapters), 18, "Should find 18 chapters in apriori.txt")

    def test_find_intro_sections(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'apriori.txt')

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        intro_sections = parser.find_intro_sections()

        print(f"Found {len(intro_sections)} intro sections in apriori.txt.")
        intro_titles = [s['title'] for s in intro_sections]
        print("Intro section titles:", intro_titles)

        self.assertIsInstance(intro_sections, list)
        self.assertTrue(len(intro_sections) > 0, "Should find at least one intro section.")

        # Be flexible about which intro sections are present, but expect common ones
        # Check that we find some reasonable intro sections
        found_intro_types = set()
        for title in intro_titles:
            title_lower = title.lower()
            if 'content' in title_lower:
                found_intro_types.add('contents')
            elif 'preface' in title_lower:
                found_intro_types.add('preface')
            elif 'acknowledgement' in title_lower:
                found_intro_types.add('acknowledgements')
            elif 'introduction' in title_lower:
                found_intro_types.add('introduction')

        # Expect at least 2 types of intro sections to be found
        self.assertGreaterEqual(len(found_intro_types), 2, 
                               f"Should find at least 2 types of intro sections, found: {found_intro_types}")
        
        # Specifically check for common intro sections that should be in this document
        self.assertIn('contents', found_intro_types, "Should find Contents section")
        self.assertIn('preface', found_intro_types, "Should find Preface section")

    def test_find_note_references(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'chapters.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        references = parser.find_note_references()
        
        print(f"Found {len(references)} note references:")
        for note_id, offset in references:
            print(f"Note {note_id} at offset {offset}")

    def test_link_notes_to_text(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'chapters.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        # Get the required inputs in the correct sequential order
        intro_sections = parser.find_intro_sections()
        end_sections = parser.find_end_sections()
        chapters = parser.find_chapters(intro_sections, end_sections)
        notes_map = parser.find_notes()
        note_references = parser.find_note_references()
        chapters_with_notes = parser.link_notes_to_text(chapters, notes_map, note_references)
        
        print("Linked notes to chapters:", chapters_with_notes)
        
        # Print summary of notes per chapter
        for chapter, notes in chapters_with_notes.items():
            print(f"{chapter}: {len(notes)} notes")

    def test_find_chapter_subsections(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'chapters.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        # Get the required inputs in the correct order
        intro_sections = parser.find_intro_sections()
        end_sections = parser.find_end_sections()
        chapters = parser.find_chapters(intro_sections, end_sections)
        chapter_subsections = parser.find_chapter_subsections(chapters)
        
        print("Detected chapter subsections:", chapter_subsections)
        
        self.assertIsInstance(chapter_subsections, dict)
        self.assertTrue(len(chapter_subsections) > 0)

        # Check for specific subsections in Chapter 13
        chapter_13_title = next((title for title in chapter_subsections if 'Chapter 13' in title), None)
        self.assertIsNotNone(chapter_13_title)
        
        subsections = chapter_subsections.get(chapter_13_title, [])
        subsection_titles = [s['title'] for s in subsections]
        
        expected_subsections = [
            "Introduction",
            "Two Types of Understanding-Based Account: Constitutive vs Basis",
            "Competent Dissent",
            "Competent Dissent and Constitutive Accounts",
            "Competent Dissent and Basis Accounts",
            "Two Ways of Believing a Basis-Explicable A Priori Proposition",
            "A Role for Intuitions in Basis Accounts",
            "Synthetic A Priori Propositions: Normative Truths",
            "Interim Summary",
            "The Non-Uniformity of Sources of the A Priori",
            "Basic Skepticism about Intuitions: Phenomenology and Intellectual Seemings",
            "Justification by Inclinations to Judgment",
            "Conclusion"
        ]

        # We're checking the start of the list, so we don't need to match all of them
        for i, expected_title in enumerate(expected_subsections):
            self.assertIn(expected_title, subsection_titles[i])

    def test_find_end_sections(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'apriori.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        end_sections = parser.find_end_sections()
        
        self.assertIsInstance(end_sections, list)
        self.assertTrue(len(end_sections) > 0, "Should find at least one end section.")

        section_titles = [s['title'] for s in end_sections]
        print(f"Found {len(end_sections)} end sections in apriori.txt.")
        print("End section titles:", section_titles)

        # Be flexible about which end sections are present
        # Check that we find some reasonable end sections
        found_end_types = set()
        for title in section_titles:
            title_lower = title.lower()
            if 'bibliography' in title_lower:
                found_end_types.add('bibliography')
            elif 'index' in title_lower:
                found_end_types.add('index')
            elif 'notes' in title_lower:
                found_end_types.add('notes')
            elif 'reference' in title_lower:
                found_end_types.add('references')
            elif 'appendix' in title_lower or 'appendices' in title_lower:
                found_end_types.add('appendix')

        # Expect at least 1 type of end section to be found
        self.assertGreaterEqual(len(found_end_types), 1, 
                               f"Should find at least 1 type of end section, found: {found_end_types}")
        
        # Check for common end sections that should be in this academic document
        common_end_sections = {'bibliography', 'index'}
        found_common = found_end_types.intersection(common_end_sections)
        self.assertTrue(len(found_common) > 0, 
                       f"Should find at least one common end section (Bibliography or Index), found: {found_end_types}")

    def test_find_paragraphs(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'chapters.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        # Get the required inputs in the correct sequential order
        intro_sections = parser.find_intro_sections()
        end_sections = parser.find_end_sections()
        chapters = parser.find_chapters(intro_sections, end_sections)
        chapter_subsections = parser.find_chapter_subsections(chapters)
        paragraphs_data = parser.find_paragraphs(intro_sections, chapters, chapter_subsections)
        
        print("=== FIND_PARAGRAPHS TEST RESULTS ===")
        
        # Test that we get the expected structure
        self.assertIsInstance(paragraphs_data, dict)
        self.assertIn('introductions', paragraphs_data)
        self.assertIn('chapters', paragraphs_data)
        
        # Print introduction paragraphs
        if paragraphs_data['introductions']:
            print("\n--- INTRODUCTION SECTIONS ---")
            for intro in paragraphs_data['introductions']:
                print(f"Introduction: {intro['title']}")
                if 'paragraphs' in intro:
                    for para in intro['paragraphs']:
                        print(f"  Paragraph {para['id']}: offset {para['start_offset']}-{para['end_offset']}")
        
        # Print chapter paragraphs
        print("\n--- CHAPTERS ---")
        for chapter_title, chapter_data in paragraphs_data['chapters'].items():
            print(f"\nChapter: {chapter_title}")
            print(f"  Chapter offset: {chapter_data['start_offset']}-{chapter_data['end_offset']}")
            
            # Print direct chapter paragraphs (if no subsections)
            if chapter_data['paragraphs']:
                print("  Direct chapter paragraphs:")
                for para in chapter_data['paragraphs']:
                    print(f"    Paragraph {para['id']}: offset {para['start_offset']}-{para['end_offset']}")
            
            # Print subsection paragraphs
            if chapter_data['subsections']:
                print("  Subsections:")
                for subsection in chapter_data['subsections']:
                    print(f"    Subsection: {subsection['title']}")
                    print(f"      Subsection offset: {subsection['start_offset']}-{subsection['end_offset']}")
                    if 'paragraphs' in subsection:
                        for para in subsection['paragraphs']:
                            print(f"      Paragraph {para['id']}: offset {para['start_offset']}-{para['end_offset']}")
        
        # Basic assertions
        self.assertIsInstance(paragraphs_data['introductions'], list)
        self.assertIsInstance(paragraphs_data['chapters'], dict)
        
        # Check that at least some paragraphs were found
        total_paragraphs = 0
        for intro in paragraphs_data['introductions']:
            if 'paragraphs' in intro:
                total_paragraphs += len(intro['paragraphs'])
        
        for chapter_data in paragraphs_data['chapters'].values():
            if chapter_data['paragraphs']:
                total_paragraphs += len(chapter_data['paragraphs'])
            for subsection in chapter_data['subsections']:
                if 'paragraphs' in subsection:
                    total_paragraphs += len(subsection['paragraphs'])
        
        print(f"\nTotal paragraphs found: {total_paragraphs}")
        self.assertTrue(total_paragraphs > 0, "Should find at least some paragraphs")

    def test_parse_apriori(self):
        """Test the complete parse() method on apriori.txt and write output to test.json"""
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'apriori.txt')
        
        # Read the apriori.txt file
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Parse the text
        parser = Parser(text)
        parsed_document = parser.parse()
        
        # Write the result to test.json in the base directory
        output_path = os.path.join(project_root, 'test-lg.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(parsed_document, f, indent=2, ensure_ascii=False)
        
        print(f"=== PARSE APRIORI TEST RESULTS ===")
        print(f"Parsed document written to: {output_path}")
        
        # Basic structure assertions
        self.assertIsInstance(parsed_document, dict)
        self.assertIn('introductions', parsed_document)
        self.assertIn('chapters', parsed_document)
        self.assertIn('end_sections', parsed_document)
        self.assertIn('notes', parsed_document)
        self.assertIn('linked_notes', parsed_document)
        self.assertIn('footnotes', parsed_document)
        self.assertIn('bibliography', parsed_document)
        
        # Test bibliography structure
        bibliography = parsed_document['bibliography']
        self.assertIsInstance(bibliography, dict)
        self.assertIn('entries', bibliography)
        self.assertIn('unlinked_citations', bibliography)
        
        # Print summary statistics
        print(f"Found {len(parsed_document['introductions'])} introduction sections")
        print(f"Found {len(parsed_document['chapters'])} chapters")
        print(f"Found {len(parsed_document['end_sections'])} end sections")
        print(f"Found {len(parsed_document['notes'])} notes")
        print(f"Found {len(parsed_document['footnotes']['references'])} footnote references")
        print(f"Found {len(parsed_document['footnotes']['definitions'])} footnote definitions")
        
        # Print bibliography statistics
        bib_entries = bibliography['entries']
        unlinked_citations = bibliography['unlinked_citations']
        total_citations = sum(len(entry['citations']) for entry in bib_entries.values())
        
        print(f"Found {len(bib_entries)} bibliography entries")
        print(f"Found {total_citations} linked in-text citations")
        print(f"Found {len(unlinked_citations)} unlinked citations")
        
        # Print sample bibliography entries
        if bib_entries:
            print("\nSample bibliography entries:")
            for i, (key, entry) in enumerate(bib_entries.items()):
                if i >= 5:  # Show only first 5
                    break
                print(f"  - {key}: {entry['author']} ({entry['year']}) - {len(entry['citations'])} citations")
        
        # Print chapter titles
        if parsed_document['chapters']:
            print("\nChapter titles:")
            for chapter_title in parsed_document['chapters'].keys():
                print(f"  - {chapter_title}")
        
        # Print introduction section titles
        if parsed_document['introductions']:
            print("\nIntroduction section titles:")
            for intro in parsed_document['introductions']:
                print(f"  - {intro['title']}")
        
        # Print end section titles
        if parsed_document['end_sections']:
            print("\nEnd section titles:")
            for end_section in parsed_document['end_sections']:
                print(f"  - {end_section['title']}")
        
        # Count total paragraphs
        total_paragraphs = 0
        
        # Count paragraphs in introductions
        for intro in parsed_document['introductions']:
            if 'paragraphs' in intro:
                total_paragraphs += len(intro['paragraphs'])
        
        # Count paragraphs in chapters
        for chapter_data in parsed_document['chapters'].values():
            if chapter_data['paragraphs']:
                total_paragraphs += len(chapter_data['paragraphs'])
            for subsection in chapter_data['subsections']:
                if 'paragraphs' in subsection:
                    total_paragraphs += len(subsection['paragraphs'])
        
        # Count paragraphs in end sections
        for end_section in parsed_document['end_sections']:
            if 'paragraphs' in end_section:
                total_paragraphs += len(end_section['paragraphs'])
        
        print(f"\nTotal paragraphs found: {total_paragraphs}")
        
        # Verify the document has content
        self.assertTrue(total_paragraphs > 0, "Should find at least some paragraphs")
        
        # Verify bibliography functionality
        if bib_entries:
            print("\nBibliography validation:")
            # Check that bibliography entries have the required fields
            for key, entry in bib_entries.items():
                self.assertIn('key', entry)
                self.assertIn('author', entry)
                self.assertIn('year', entry)
                self.assertIn('full_text', entry)
                self.assertIn('citations', entry)
                self.assertIsInstance(entry['citations'], list)
            
            # Check that citations have the required fields
            for citation in unlinked_citations:
                self.assertIn('author', citation)
                self.assertIn('year', citation)
                self.assertIn('start_offset', citation)
                self.assertIn('page_info', citation)
                self.assertIn('full_text', citation)
            
            print(f"  - All bibliography entries have required fields")
            print(f"  - All citations have required fields")
        
        print(f"\nTest completed successfully. Output saved to {output_path}")

    def test_note_reference_preprocessing(self):
        # Test case where note reference is on same line as chapter heading
        text_with_inline_note = """
# Chapter 1

## Some Chapter Title ${ }^{1}$ More Text

This is a paragraph with some content.

## Another Section ${ }^{2,3}$

More content here.

# Notes

1. This is note 1
2. This is note 2  
3. This is note 3
"""
        
        parser = Parser(text_with_inline_note)
        
        # Check that original text is preserved
        self.assertEqual(parser.original_text, text_with_inline_note)
        
        # Check that note references are isolated in processed text
        processed_lines = parser.text.split('\n')
        
        # The note reference should now be on its own line, separated from the heading
        found_isolated_note_1 = False
        found_isolated_note_2 = False
        
        for i, line in enumerate(processed_lines):
            if line.strip() == '${ }^{1}$':
                found_isolated_note_1 = True
                # Check that it's surrounded by blank lines or separated from other content
                self.assertTrue(i > 0 and (processed_lines[i-1].strip() == '' or 'Some Chapter Title' in processed_lines[i-1]))
                self.assertTrue(i < len(processed_lines) - 1 and (processed_lines[i+1].strip() == '' or processed_lines[i+1].strip() == 'More Text'))
            elif line.strip() == '${ }^{2,3}$':
                found_isolated_note_2 = True
                # Should be isolated from "Another Section"
                self.assertTrue(i > 0 and (processed_lines[i-1].strip() == '' or 'Another Section' in processed_lines[i-1]))
        
        self.assertTrue(found_isolated_note_1, "Note reference 1 should be isolated")
        self.assertTrue(found_isolated_note_2, "Note reference 2,3 should be isolated")
        
        # Test that note references can still be found using original text
        note_refs = parser.find_note_references()
        self.assertEqual(len(note_refs), 3)  # Should find references to notes 1, 2, and 3
        
        note_ids = [ref[0] for ref in note_refs]
        self.assertIn('1', note_ids)
        self.assertIn('2', note_ids)
        self.assertIn('3', note_ids)
        
        print("Note reference preprocessing test passed!")

    def test_note_reference_integration_with_parsing(self):
        """Test that note references are properly isolated and don't interfere with parsing"""
        
        # Test case where note reference is on same line as chapter heading
        text_with_inline_note = """
# Chapter 1

## Some Chapter Title ${ }^{1}$ More Text

This is a paragraph with some content and a note reference ${ }^{2,3}$.

# Notes

1. This is note 1
2. This is note 2  
3. This is note 3
"""
        
        parser = Parser(text_with_inline_note)
        parsed_doc = parser.parse()
        
        # Verify that chapter titles are clean (no note references)
        for chapter_title, chapter_data in parsed_doc['chapters'].items():
            self.assertNotIn('${ }^{', chapter_title, f"Chapter title '{chapter_title}' should not contain note references")
        
        # Verify that we can still find the note references in the original text
        note_refs = parser.find_note_references()
        self.assertEqual(len(note_refs), 3)  # Should find references to notes 1, 2, and 3
        
        # Verify the notes are properly linked - need to get required inputs
        intro_sections = parser.find_intro_sections()
        end_sections = parser.find_end_sections()
        chapters = parser.find_chapters(intro_sections, end_sections)
        notes_map = parser.find_notes()
        note_references = parser.find_note_references()
        linked_notes = parser.link_notes_to_text(chapters, notes_map, note_references)
        
        chapter_titles = list(linked_notes.keys())
        # Should have at least one chapter with linked notes
        chapter_with_notes = [title for title in chapter_titles if title != 'Unlinked Notes' and linked_notes[title]]
        self.assertGreater(len(chapter_with_notes), 0, "At least one chapter should have linked notes")
        
        print("Note reference integration test passed!")


if __name__ == '__main__':
    unittest.main() 