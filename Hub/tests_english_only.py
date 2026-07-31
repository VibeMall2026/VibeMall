"""
The interface is English.

Chunks of the admin panel were written in romanised Gujarati — "ahiya je
products tame add karso, homepage par ej products show thase". It reads fine
to whoever wrote it and is unusable to everyone else, including any staff
member or developer who joins later.

This test fails on the words rather than on a whitelist of files, so a new
template written the same way is caught on the first run.

    python manage.py test Hub.tests_english_only
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase

#: Gujarati and Devanagari blocks.
INDIC_SCRIPT = re.compile(r'[઀-૿ऀ-ॿ]')

#: Romanised Gujarati/Hindi words with no English meaning, so a single one is
#: enough to fail. "mate" and "kari" are excluded despite being common in the
#: original text: they collide with English words and with real names.
ROMANISED = re.compile(
    r'\b('
    r'ahiya|shako|chho|karso|karse|thase|thashe|lakho|aavse|karva|karine|'
    r'mathi|ekaj|nathi|joie|jovu|badha|tamara|aapo|banavo|rakho|pachi|'
    r'kari\s+shako|manage\s+karo|click\s+karo|upload\s+karo|set\s+kari|'
    r'open\s+karo|avoid\s+karo|fill\s+karo|add\s+karo|jem\s+ke'
    r')\b',
    re.IGNORECASE,
)

#: Third-party bundles and generated files are not ours to rewrite.
SKIP = (
    'node_modules', '/vendor/', '.min.js', '.min.css', 'highlight.js',
    'staticfiles/', '/migrations/',
)

#: Legitimate exceptions.
#:
#: * The supplier-message parser matches Hindi words on purpose, because
#:   suppliers write them. That is input handling, not interface text.
#: * This file, which necessarily contains the words it searches for.
ALLOWED = {
    'Hub/automation/parsing/rules.py',
    'Hub/tests_english_only.py',
}


def source_files():
    root = Path(settings.BASE_DIR) / 'Hub'
    for path in root.rglob('*'):
        if path.suffix not in {'.html', '.py', '.js'}:
            continue
        posix = path.as_posix()
        if any(skip in posix for skip in SKIP):
            continue
        if any(posix.endswith(allowed) for allowed in ALLOWED):
            continue
        yield path


class EnglishOnlyTests(TestCase):
    def _offenders(self, pattern):
        found = []
        for path in source_files():
            try:
                text = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    rel = path.relative_to(settings.BASE_DIR).as_posix()
                    found.append(f'{rel}:{number}  {line.strip()[:100]}')
        return found

    def test_no_gujarati_or_devanagari_script(self):
        offenders = self._offenders(INDIC_SCRIPT)
        self.assertEqual(
            offenders, [],
            'Interface text must be English. Found Indic script at:\n  '
            + '\n  '.join(offenders),
        )

    def test_no_romanised_gujarati(self):
        offenders = self._offenders(ROMANISED)
        self.assertEqual(
            offenders, [],
            'Interface text must be English — romanised Gujarati counts.\n  '
            + '\n  '.join(offenders),
        )

    def test_the_scanner_would_actually_catch_something(self):
        """A guard that never fires is worse than no guard."""
        self.assertTrue(ROMANISED.search('ahiya je products tame add karso'))
        self.assertTrue(INDIC_SCRIPT.search('અહીં'))
        self.assertTrue(INDIC_SCRIPT.search('अवेलेबल'))

    def test_ordinary_english_is_not_flagged(self):
        for line in (
            'Manage Top Deals, Top Selling and Recommended for You.',
            'Set the colour and role for each existing image here.',
            'Care Guide',
            'Separate values with a comma',
            'Kari Traders Pvt Ltd',
        ):
            self.assertIsNone(ROMANISED.search(line), f'false positive on {line!r}')
