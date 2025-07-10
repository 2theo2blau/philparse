import re
import os

class Cleaner:
    def __init__(self, text):
        self.text = text

    def consolidate_whitespace(self):
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', self.text) # remove newlines that are not preceded or followed by another newline
        text = re.sub(r'[\t]+', ' ', text) # collapse multiple tabs/spaces

        return text
    
    def dehyphenate(self):
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', self.text) # remove newlines between words

        return text
    
    def remove_markdown_images(self):
        text = re.sub(r'!\[(img-\d+\.[a-zA-Z0-9]+)\]\(\1\)', self.text) # remove markdown images

        return text