"""
Telegram delivery must not lose products.

A product sent to the bot vanished: the listener fetched it, advanced the
Telegram offset, then failed to write the draft with "database is locked".
Telegram had been told the batch was handled, so it never sent it again — and
the sender saw nothing wrong.

The offset is now held until the caller confirms the batch is stored.

    python manage.py test Hub.tests_telegram_delivery
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from Hub.automation.sources.telegram_bot import TelegramBotSource


def update(update_id: int, text: str = 'Kurti 899') -> dict:
    return {
        'update_id': update_id,
        'message': {
            'message_id': update_id,
            'chat': {'id': 555, 'type': 'private'},
            'from': {'username': 'supplier'},
            'text': text,
            'date': 0,
        },
    }


@override_settings(TELEGRAM_BOT_TOKEN='123:TEST')
class OffsetAcknowledgementTests(TestCase):
    def setUp(self):
        self.offset_file = Path(tempfile.mkdtemp()) / 'offset.json'
        self.source = TelegramBotSource(offset_path=self.offset_file)

    def saved_offset(self):
        if not self.offset_file.exists():
            return None
        return json.loads(self.offset_file.read_text(encoding='utf-8'))['offset']

    def poll_with(self, *updates):
        with patch.object(self.source, '_api', return_value=list(updates)):
            return list(self.source.poll())

    def test_polling_alone_does_not_acknowledge(self):
        self.poll_with(update(101))
        self.assertIsNone(
            self.saved_offset(),
            'acknowledging before the draft is stored is what lost the product',
        )

    def test_commit_acknowledges(self):
        self.poll_with(update(101))
        self.source.commit()
        self.assertEqual(self.saved_offset(), 102)

    def test_an_uncommitted_batch_is_offered_again(self):
        first = self.poll_with(update(101))
        self.assertEqual(len(first), 1)

        # The caller blew up — no commit. Telegram still has the message.
        again = self.poll_with(update(101))
        self.assertEqual(len(again), 1, 'the batch must come back for another try')
        self.assertIsNone(self.saved_offset())

    def test_committing_twice_is_harmless(self):
        self.poll_with(update(101))
        self.source.commit()
        self.source.commit()
        self.assertEqual(self.saved_offset(), 102)

    def test_the_offset_never_moves_backwards(self):
        self.poll_with(update(300))
        self.source.commit()
        self.poll_with()  # an empty poll
        self.source.commit()
        self.assertEqual(self.saved_offset(), 301)

    def test_skip_batch_moves_past_a_poisonous_message(self):
        self.poll_with(update(101))
        self.source.skip_batch()
        self.assertEqual(
            self.saved_offset(), 102,
            'one message that always fails must not wedge the queue',
        )


class SourceContractTests(TestCase):
    """Every source gets the acknowledgement hooks, even if they do nothing."""

    def test_the_base_class_defines_them(self):
        from Hub.automation.sources.base import ProductSource

        self.assertTrue(hasattr(ProductSource, 'commit'))
        self.assertTrue(hasattr(ProductSource, 'skip_batch'))

    def test_they_are_safe_no_ops_by_default(self):
        from Hub.automation.sources.base import IncomingProduct, ProductSource

        class Simple(ProductSource):
            name = 'telegram'

            def poll(self):
                return [IncomingProduct(source='telegram', message_id='1', text='x')]

        source = Simple()
        source.commit()
        source.skip_batch()


class DatabaseConcurrencyTests(TestCase):
    """
    The failure underneath it all: several processes share one SQLite file.
    """

    def test_the_pragma_hook_is_registered(self):
        from django.db.backends.signals import connection_created

        from Hub.db_pragmas import apply_sqlite_pragmas

        registered = [ref() for _, ref in connection_created.receivers]
        self.assertIn(
            apply_sqlite_pragmas, registered,
            'without this hook SQLite stays in rollback-journal mode',
        )

    def test_wal_is_among_the_pragmas(self):
        from Hub.db_pragmas import PRAGMAS

        settings_applied = dict(PRAGMAS)
        self.assertEqual(
            settings_applied.get('journal_mode'), 'WAL',
            'under the default journal a writer locks out the Telegram listener',
        )
        self.assertGreaterEqual(int(settings_applied.get('busy_timeout', 0)), 30000)

    def test_an_in_memory_database_is_left_alone(self):
        """WAL on a memory database is an error, and there is nothing to fix."""
        from unittest.mock import MagicMock

        from Hub.db_pragmas import apply_sqlite_pragmas

        connection = MagicMock()
        connection.vendor = 'sqlite'
        connection.settings_dict = {'NAME': 'file:memorydb_default?mode=memory'}
        apply_sqlite_pragmas(sender=None, connection=connection)
        connection.cursor.assert_not_called()

    def test_a_non_sqlite_backend_is_left_alone(self):
        from unittest.mock import MagicMock

        from Hub.db_pragmas import apply_sqlite_pragmas

        connection = MagicMock()
        connection.vendor = 'postgresql'
        apply_sqlite_pragmas(sender=None, connection=connection)
        connection.cursor.assert_not_called()
