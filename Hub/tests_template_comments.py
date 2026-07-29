import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TemplateCommentSyntaxTests(SimpleTestCase):
    """
    Django's {# #} comment is single-line only. Spread it over two lines and it
    stops being a comment: the text is rendered to the page as ordinary copy.
    This has now shipped to a live page three times - on the checkout, on the
    mobile footer and on the order tracking timeline - so it gets a guard.

    {% comment %}...{% endcomment %} is the multi-line form and is unaffected.
    """

    #: {# with no closing #} before the end of the line
    OPENER = re.compile(r'\{#(?![^\n]*#\})')

    def _templates(self):
        root = Path(settings.BASE_DIR)
        skip = {'node_modules', '.venv', 'venv', 'staticfiles', '.git'}
        for path in root.rglob('*.html'):
            if skip.isdisjoint(path.parts):
                yield path

    def test_no_multiline_hash_comments(self):
        offenders = []
        root = Path(settings.BASE_DIR)
        for path in self._templates():
            text = path.read_text(encoding='utf-8', errors='replace')
            for match in self.OPENER.finditer(text):
                line = text.count('\n', 0, match.start()) + 1
                offenders.append(f'{path.relative_to(root)}:{line}')

        self.assertEqual(
            offenders, [],
            'Multi-line {# #} is not a comment and renders as page text. '
            'Use {% comment %}...{% endcomment %} instead. Found at: '
            + ', '.join(offenders),
        )

    def test_the_detector_catches_a_known_bad_pattern(self):
        """A guard that cannot fail is not a guard."""
        bad = '{# this comment\n   spans two lines #}'
        good = '{# single line #}'
        multiline_tag = '{% comment %}\nspans lines\n{% endcomment %}'
        self.assertTrue(self.OPENER.search(bad))
        self.assertFalse(self.OPENER.search(good))
        self.assertFalse(self.OPENER.search(multiline_tag))
