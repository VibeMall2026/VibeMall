"""Deterministic, rule-based extraction. Runs before the AI and as its fallback."""

from .rules import RuleExtraction, extract_rules

__all__ = ['RuleExtraction', 'extract_rules']
