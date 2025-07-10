import unittest
import os
import json
from src.preprocessing.parse import Parser
import re

class TestParser(unittest.TestCase):
    def test_find_footnotes(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'notes.txt')

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        footnotes = parser.find_footnotes()
        
        print("Detected footnotes:", footnotes)
        for note_num, note_text in footnotes.items():
            print(f"Note {note_num}: {note_text}")

        # Example assertion: Check if any footnotes were found
        self.assertTrue(len(footnotes) > 0)

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
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'chapters.txt')

        # Check if the file is empty, if so, skip the test
        if os.path.getsize(file_path) == 0:
            self.skipTest("chapters.txt is empty, skipping test")

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        chapters = parser.find_chapters()
        
        print("Detected chapters:", chapters)

        # Example assertion: Check if chapters are found
        self.assertIsInstance(chapters, list)

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
        chapters_with_notes = parser.link_notes_to_text()
        
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
        chapter_subsections = parser.find_chapter_subsections()
        
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
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'end-sections.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        end_sections = parser.find_end_sections()
        
        self.assertIsInstance(end_sections, list)
        self.assertTrue(len(end_sections) > 0)

        section_titles = [s['title'] for s in end_sections]
        self.assertIn('Bibliography', section_titles)
        self.assertIn('Index', section_titles)

    def test_find_paragraphs(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'chapters.txt')
        
        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        paragraphs_data = parser.find_paragraphs()
        
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
        output_path = os.path.join(project_root, 'test.json')
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


if __name__ == '__main__':
    unittest.main() 