"""
Source abstraction
==================

Every inbound channel — Telegram today, WhatsApp / CSV / Excel / supplier APIs
later — normalises its payload into :class:`IncomingProduct` and hands it to
:func:`Hub.automation.ingest.ingest`.

Adding a channel therefore means writing one subclass and a management command
that drives it. Nothing downstream (parsing, AI, images, publishing) changes.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator


@dataclass(slots=True)
class IncomingMedia:
    """One image attached to an inbound product message."""

    data: bytes
    filename: str
    #: Provider-side identifier, kept so we can detect re-delivery of the same file.
    source_file_id: str = ''
    #: Optional caption / label the provider attached to this specific file.
    caption: str = ''

    def __post_init__(self) -> None:
        if not self.filename:
            self.filename = f"{self.source_file_id or 'image'}.jpg"


@dataclass(slots=True)
class IncomingProduct:
    """A normalised inbound product submission, independent of channel."""

    source: str
    message_id: str
    text: str = ''
    media: list[IncomingMedia] = field(default_factory=list)
    chat_id: str = ''
    #: Groups several provider messages into one logical product
    #: (Telegram ``media_group_id``, a WhatsApp album, a CSV row id...).
    group_id: str = ''
    author: str = ''
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_content(self) -> bool:
        return bool(self.text.strip() or self.media)


class ProductSource(abc.ABC):
    """Base class for an inbound product channel."""

    #: Value stored in ``ProductDraft.source``; must match a SOURCE_* choice.
    name: str = ''

    @abc.abstractmethod
    def poll(self) -> Iterable[IncomingProduct]:
        """
        Yield any products available right now.

        Implementations should be non-blocking or short-blocking (a long-poll of
        a few seconds is fine) and must not raise on transient network errors —
        log and return an empty iterable so the driver loop keeps running.
        """

    def run_forever(self) -> Iterator[IncomingProduct]:
        """Convenience driver: poll in a loop, yielding everything it sees."""
        while True:
            yield from self.poll()
