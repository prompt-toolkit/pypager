"""
A pager implementation in Python.
"""
__version__ = "3.0.0"

from .pager import Pager
from .source import GeneratorSource

__all__ = ["Pager", "GeneratorSource"]
