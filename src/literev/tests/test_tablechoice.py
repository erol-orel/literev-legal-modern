
from django.test import TestCase

from literev.libs.table_choice import highlight_words


class HighligthKeywords(TestCase):
    def test_highlight_words(self) -> None:
        sample = """The U.S. highlight national government is a presidential 
            federal republic and liberal democracy.
            random tags: <b class="highlight">Senate</b>, Liberal,"""
        expected = """The U.S. <span class="red-highlight">highlight</span> national government is a presidential 
            federal republic and <span class="red-highlight">liberal</span> democracy.
            random tags: <b class="highlight">Senate</b>, <span class="red-highlight">Liberal</span>,"""

        words_to_highlight = ["liberal", "senate", "highlight"]
        style_class = "red-highlight"
        
        result = highlight_words(sample, words_to_highlight, style_class)
        
        self.assertEqual(expected, result)
