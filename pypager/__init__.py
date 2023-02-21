"""
A pager implementation in Python.
"""
__version__ = "3.0.1"

from .pager import Pager
from .source import FormattedTextSource, GeneratorSource, PipeSource, StringSource

__all__ = [
    "FormattedTextSource",
    "GeneratorSource",
    "Pager",
    "PipeSource",
    "StringSource",
]
