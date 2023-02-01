from typing import TYPE_CHECKING

from prompt_toolkit.filters import Filter

if TYPE_CHECKING:
    from .pager import Pager

__all__ = [
    "HasColon",
    "DisplayingHelp",
]


class _PagerFilter(Filter):
    def __init__(self, pager: "Pager") -> None:
        super().__init__()
        self.pager = pager


class HasColon(_PagerFilter):
    """
    The user typed a ':'.
    """

    def __call__(self) -> bool:
        return self.pager.in_colon_mode


class DisplayingHelp(_PagerFilter):
    def __call__(self) -> bool:
        return self.pager.displaying_help
