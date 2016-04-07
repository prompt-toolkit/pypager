from __future__ import unicode_literals
from prompt_toolkit.filters import Filter

__all__ = (
    'HasColon',
)

class _PagerFilter(Filter):
    def __init__(self, pager):
        self.pager = pager


class HasColon(_PagerFilter):
    """
    The user typed a ':'.
    """
    def __call__(self, cli):
        return self.pager.in_colon_mode


class DisplayingHelp(_PagerFilter):
    def __call__(self, cli):
        return self.pager.displaying_help
