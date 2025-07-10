import unittest
import os
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


if __name__ == '__main__':
    unittest.main() 