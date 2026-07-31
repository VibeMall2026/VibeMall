"""
SQLite settings for a database with several writers.

Four processes write to this file: the web app, the Telegram listener, the
draft worker and the trading bot. Under SQLite's default ``delete`` journal a
writer takes an exclusive lock on the whole database, so the listener was
losing inbound products to "database is locked" — and because it had already
told Telegram the batch was handled, those messages were gone for good.

Applied through the ``connection_created`` signal rather than
``DATABASES['OPTIONS']`` because the ``init_command`` and ``transaction_mode``
options need Django 5.1+, and this project runs 4.2 locally against 5.2 on the
server. The signal works identically on both.
"""

from __future__ import annotations

import logging

from django.db.backends.signals import connection_created
from django.dispatch import receiver

logger = logging.getLogger(__name__)

#: ``journal_mode`` is stored in the database file, so it only really changes
#: once; the rest are per-connection and must be set every time.
PRAGMAS = (
    # Readers no longer block the writer and the writer no longer blocks
    # readers. This is the setting that fixes the lost products.
    ('journal_mode', 'WAL'),
    # The usual companion to WAL: still durable across a process crash, and
    # only at risk from sudden power loss. Full fsync on every commit costs
    # more than it buys for this workload.
    ('synchronous', 'NORMAL'),
    # Wait rather than fail the moment another writer holds the lock.
    ('busy_timeout', '30000'),
    # Let the WAL grow to ~64MB of pages before checkpointing, so a burst of
    # writes does not stall on a checkpoint mid-transaction.
    ('wal_autocheckpoint', '1000'),
    # Foreign keys are not enforced by default in SQLite.
    ('foreign_keys', 'ON'),
)


@receiver(connection_created)
def apply_sqlite_pragmas(sender, connection, **kwargs):
    """Configure each new SQLite connection for concurrent use."""
    if connection.vendor != 'sqlite':
        return

    # An in-memory test database has no concurrency to manage, and asking for
    # WAL on one is an error.
    name = str(connection.settings_dict.get('NAME') or '')
    if ':memory:' in name or 'mode=memory' in name:
        return

    try:
        with connection.cursor() as cursor:
            for pragma, value in PRAGMAS:
                cursor.execute(f'PRAGMA {pragma}={value};')
    except Exception as exc:  # pragma: no cover - never block a connection
        logger.warning('[db] Could not apply SQLite pragmas: %s', exc)
