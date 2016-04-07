from __future__ import unicode_literals
from prompt_toolkit.enums import SYSTEM_BUFFER
from prompt_toolkit.filters import HasArg, Condition, HasSearch, HasFocus
from prompt_toolkit.layout.containers import HSplit, VSplit, Window, ConditionalContainer, Float, FloatContainer, Container
from prompt_toolkit.layout.controls import BufferControl, TokenListControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import Processor, HighlightSelectionProcessor, HighlightSearchProcessor, HighlightMatchingBracketProcessor, TabsProcessor, Transformation, ConditionalProcessor, BeforeInput
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.lexers import SimpleLexer
from prompt_toolkit.layout.toolbars import SearchToolbar, SystemToolbar, TokenListToolbar
from prompt_toolkit.token import Token

from .filters import HasColon

import weakref

__all__ = (
    'Layout',
)


class _EscapeProcessor(Processor):
    """
    Interpret escape sequences like less/more/most do.
    """
    def __init__(self, pager):
        self.pager = pager

    def apply_transformation(self, cli, document, lineno, source_to_display, tokens):
        tokens = self.pager.line_tokens[lineno]
        return Transformation(tokens[:])


class _Arg(ConditionalContainer):
    def __init__(self):
        def get_tokens(cli):
            if cli.input_processor.arg is not None:
                return [(Token.Arg, ' %i ' % cli.input_processor.arg)]
            else:
                return []

        super(_Arg, self).__init__(
                Window(TokenListControl(get_tokens, align_right=True)),
                filter=HasArg())


class MessageToolbarBar(ConditionalContainer):
    """
    Pop-up (at the bottom) for showing error/status messages.
    """
    def __init__(self, pager):
        def get_tokens(cli):
            if pager.message:
                return [(Token.Message, pager.message)]
            else:
                return []

        super(MessageToolbarBar, self).__init__(
            content=TokenListToolbar(
                get_tokens,
                filter=Condition(lambda cli: pager.message is not None)),
            filter=Condition(lambda cli: bool(pager.message)))


class _DynamicBody(Container):
    def __init__(self, pager):
        self.pager = pager
        self._bodies = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

    def get_buffer_window(self):
        " Return the Container object according to which Buffer/Source is visible. "
        source = self.pager.source

        if source not in self._bodies:
            input_processors = [
                ConditionalProcessor(
                    processor=_EscapeProcessor(self.pager),
                    filter=Condition(lambda cli: not bool(self.pager.source.lexer)),
                ),
                TabsProcessor(),
                HighlightSelectionProcessor(),
                ConditionalProcessor(
                    processor=HighlightSearchProcessor(preview_search=True),
                    filter=Condition(lambda cli: self.pager.highlight_search),
                ),
                HighlightMatchingBracketProcessor(),
            ]

            buffer_window = Window(
                always_hide_cursor=True,
                content=BufferControl(
                    buffer_name=self.pager.source_info[source].buffer_name,
                    lexer=source.lexer,
                    input_processors=input_processors))

            self._bodies[source] = buffer_window

        return self._bodies[source]

    def reset(self):
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self):
        return self.get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self.get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self.get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self.get_buffer_window().write_to_screen(*a, **kw)

    def walk(self, *a, **kw):
        # Required for prompt_toolkit.layout.utils.find_window_for_buffer_name.
        return self.get_buffer_window().walk(*a, **kw)


class Layout(object):
    def __init__(self, pager):
        self.pager = pager
        self.dynamic_body = _DynamicBody(pager)

        # Build an interface.
        has_colon = HasColon(pager)

        self.container = FloatContainer(
            content=HSplit([
                self.dynamic_body,
                SearchToolbar(vi_mode=True),
                SystemToolbar(),
                ConditionalContainer(
                    content=VSplit([
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
                    filter=~HasSearch() & ~HasFocus(SYSTEM_BUFFER) & ~has_colon & ~HasFocus('EXAMINE')),
                ConditionalContainer(
                    content=TokenListToolbar(
                        lambda cli: [(Token.Titlebar, ' :')],
                        default_char=Char(token=Token.Titlebar)),
                    filter=has_colon),
                ConditionalContainer(
                    content=Window(
                        BufferControl(
                            buffer_name='EXAMINE',
                            default_char=Char(token=Token.Toolbar.Examine),
                            lexer=SimpleLexer(default_token=Token.Toolbar.Examine.Text),
                            input_processors=[
                                BeforeInput(lambda cli: [(Token.Toolbar.Examine, ' Examine: ')]),
                            ]),
                        height=D.exact(1)),
                    filter=HasFocus('EXAMINE')),
            ]),
            floats=[
                Float(right=0, height=1, bottom=1,
                      content=_Arg()),
                Float(bottom=1, left=0, right=0, height=1,
                      content=MessageToolbarBar(pager)),
                Float(xcursor=True,
                      ycursor=True,
                      content=MultiColumnCompletionsMenu()),
            ]
        )

    @property
    def buffer_window(self):
        return self.dynamic_body.get_buffer_window()

    def _get_titlebar_left_tokens(self, cli):
        if self.pager.displaying_help:
            message = ' HELP -- Press q when done'
        else:
            message = ' (press h for help or q to quit)'
        return [(Token.Titlebar, message)]

    def _get_titlebar_right_tokens(self, cli):
        buffer = self.pager.source_info[self.pager.source].buffer
        document = buffer.document
        row = document.cursor_position_row + 1
        col = document.cursor_position_col + 1

        if self.pager.source.eof():
            percentage = int(100 * row / document.line_count)
            return [
                (Token.Titlebar.CursorPosition,
                 ' (%s,%s) %s%% ' % (row, col, percentage))]
        else:
            return [
                (Token.Titlebar.CursorPosition,
                 ' (%s,%s) ' % (row, col))]
