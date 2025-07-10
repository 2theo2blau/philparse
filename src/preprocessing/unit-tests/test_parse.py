import unittest
import os
from src.preprocessing.parse import Parser

class TestParser(unittest.TestCase):
    def test_find_footnotes(self):
        # Construct the absolute path to the test file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
        file_path = os.path.join(project_root, 'texts', 'txt', 'unit-tests', 'footnotes.txt')

        with open(file_path, 'r') as f:
            text = f.read()

        parser = Parser(text)
        footnotes = parser.find_footnotes()
        
        print("Detected footnotes:", footnotes)
        for footnote in footnotes:
            print(text[footnote[0]:footnote[1]])

        # Example assertion: Check if any footnotes were found
        self.assertTrue(len(footnotes) > 0)

if __name__ == '__main__':
    unittest.main() 