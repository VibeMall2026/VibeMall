"""Inbound product sources. Add a new channel by subclassing ``ProductSource``."""

from .base import IncomingMedia, IncomingProduct, ProductSource

__all__ = ['IncomingMedia', 'IncomingProduct', 'ProductSource']
