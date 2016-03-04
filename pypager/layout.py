from __future__ import unicode_literals
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, TokenListControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.processors import Processor, HighlightSelectionProcessor, HighlightSearchProcessor, HighlightMatchingBracketProcessor, TabsProcessor, Transformation
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.toolbars import SearchToolbar
from prompt_toolkit.token import Token
from prompt_toolkit.enums import DEFAULT_BUFFER

__all__ = (
    'Layout',
)


class EscapeProcessor(Processor):
    """
    Interpret escape sequences like less/more/most do.
    """
    def __init__(self, pager):
        self.pager = pager

    def apply_transformation(self, cli, document, lineno, source_to_display, tokens):
        tokens = self.pager.line_tokens[lineno]
        return Transformation(tokens[:])


class Layout(object):
    def __init__(self, pager):
        self.pager = pager

        input_processors = [
            EscapeProcessor(pager),
            TabsProcessor(),
            HighlightSelectionProcessor(),
            HighlightSearchProcessor(preview_search=True),
            HighlightMatchingBracketProcessor(),
        ]

        self.buffer_window = Window(content=BufferControl(
            buffer_name=DEFAULT_BUFFER,
            input_processors=input_processors))

        # Build an interface.
        self.container = HSplit([
            self.buffer_window,
            SearchToolbar(vi_mode=True),
            VSplit([
                Window(height=D.exact(1),
                       content=TokenListControl(
                           self._get_titlebar_left_tokens,
                           default_char=Char(' ', Token.Titlebar))),
                Window(height=D.exact(1),
                       content=TokenListControl(
                           self._get_titlebar_right_tokens,
                           align_right=True,
                           default_char=Char(' ', Token.Titlebar))),
            ]),
        ])

    def _get_titlebar_left_tokens(self, cli):
        return [
            (Token.Titlebar, ' '),
            (Token.Titlebar.AppName, 'pypager'),
            (Token.Titlebar, ' (press h for help or q to quit)'),
        ]

    def _get_titlebar_right_tokens(self, cli):
        document = cli.buffers[DEFAULT_BUFFER].document
        row = document.cursor_position_row + 1
        col = document.cursor_position_col + 1

        if self.pager.eof:
            return [
                (Token.Titlebar.CursorPosition,
                 ' (%s/%s,%s) ' % (row, document.line_count, col))]
        else:
            return [
                (Token.Titlebar.CursorPosition,
                 ' (%s,%s) ' % (row, col))]
