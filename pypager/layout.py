import weakref
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.application import get_app
from prompt_toolkit.enums import SYSTEM_BUFFER
from prompt_toolkit.filters import Condition, HasArg, HasSearch, has_focus
from prompt_toolkit.formatted_text import HTML, AnyFormattedText, StyleAndTextTuples
from prompt_toolkit.layout.containers import (
    ConditionalContainer,
    Container,
    Float,
    FloatContainer,
    HSplit,
    VSplit,
    Window,
    WindowAlign,
    WindowRenderInfo,
)
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.menus import MultiColumnCompletionsMenu
from prompt_toolkit.layout.processors import (
    BeforeInput,
    ConditionalProcessor,
    HighlightIncrementalSearchProcessor,
    HighlightMatchingBracketProcessor,
    HighlightSearchProcessor,
    HighlightSelectionProcessor,
    Processor,
    TabsProcessor,
    Transformation,
    TransformationInput,
)
from prompt_toolkit.lexers import SimpleLexer
from prompt_toolkit.widgets.toolbars import (
    FormattedTextToolbar,
    SearchToolbar,
    SystemToolbar,
)

from .filters import HasColon

if TYPE_CHECKING:
    from .pager import Pager, SourceInfo

__all__ = [
    "PagerLayout",
]


class _EscapeProcessor(Processor):
    """
    Interpret escape sequences like less/more/most do.
    """

    def __init__(self, source_info: "SourceInfo") -> None:
        self.source_info = source_info

    def apply_transformation(self, ti: TransformationInput) -> Transformation:
        tokens = self.source_info.line_tokens[ti.lineno]
        return Transformation(tokens[:])


class _Arg(ConditionalContainer):
    def __init__(self) -> None:
        def get_text() -> str:
            app = get_app()
            if app.key_processor.arg is not None:
                return " %s " % app.key_processor.arg
            else:
                return ""

        super().__init__(
            Window(
                FormattedTextControl(get_text),
                style="class:arg",
                align=WindowAlign.RIGHT,
            ),
            filter=HasArg(),
        )


class Titlebar(FormattedTextToolbar):
    """
    Displayed at the top.
    """

    def __init__(self, pager: "Pager") -> None:
        def get_tokens() -> AnyFormattedText:
            return pager.titlebar_tokens

        super().__init__(get_tokens)


class MessageToolbarBar(FormattedTextToolbar):
    """
    Pop-up (at the bottom) for showing error/status messages.
    """

    def __init__(self, pager: "Pager") -> None:
        def get_tokens():
            return [("class:message", pager.message)] if pager.message else []

        super().__init__(get_tokens)


class _DynamicBody(Container):
    def __init__(self, pager: "Pager") -> None:
        self.pager = pager
        self._bodies: weakref.WeakKeyDictionary[
            str, Window
        ] = weakref.WeakKeyDictionary()  # Map buffer_name to Window.

    def get_buffer_window(self) -> Window:
        "Return the Container object according to which Buffer/Source is visible."
        return self.pager.current_source_info.window

    def reset(self) -> None:
        for body in self._bodies.values():
            body.reset()

    def get_render_info(self) -> Optional[WindowRenderInfo]:
        return self.get_buffer_window().render_info

    def preferred_width(self, *a, **kw):
        return self.get_buffer_window().preferred_width(*a, **kw)

    def preferred_height(self, *a, **kw):
        return self.get_buffer_window().preferred_height(*a, **kw)

    def write_to_screen(self, *a, **kw):
        return self.get_buffer_window().write_to_screen(*a, **kw)

    def get_children(self):
        return [self.get_buffer_window()]


class PagerLayout:
    def __init__(self, pager: "Pager") -> None:
        self.pager = pager
        self.dynamic_body = _DynamicBody(pager)

        # Build an interface.
        has_colon = HasColon(pager)

        self.examine_control: BufferControl = BufferControl(
            buffer=pager.examine_buffer,
            lexer=SimpleLexer(style="class:examine,examine-text"),
            input_processors=[BeforeInput(lambda: [("class:examine", " Examine: ")])],
        )

        self.search_toolbar = SearchToolbar(
            vi_mode=True, search_buffer=pager.search_buffer
        )

        self.container = FloatContainer(
            content=HSplit(
                [
                    ConditionalContainer(
                        content=Titlebar(pager),
                        filter=Condition(lambda: pager.display_titlebar),
                    ),
                    self.dynamic_body,
                    self.search_toolbar,
                    SystemToolbar(),
                    ConditionalContainer(
                        content=VSplit(
                            [
                                Window(
                                    height=1,
                                    content=FormattedTextControl(
                                        self._get_statusbar_left_tokens
                                    ),
                                    style="class:statusbar",
                                ),
                                Window(
                                    height=1,
                                    content=FormattedTextControl(
                                        self._get_statusbar_right_tokens
                                    ),
                                    style="class:statusbar.cursorposition",
                                    align=WindowAlign.RIGHT,
                                ),
                            ]
                        ),
                        filter=~HasSearch()
                        & ~has_focus(SYSTEM_BUFFER)
                        & ~has_colon
                        & ~has_focus("EXAMINE"),
                    ),
                    ConditionalContainer(
                        content=Window(
                            FormattedTextControl(" :"), height=1, style="class:examine"
                        ),
                        filter=has_colon,
                    ),
                    ConditionalContainer(
                        content=Window(
                            self.examine_control, height=1, style="class:examine"
                        ),
                        filter=has_focus(pager.examine_buffer),
                    ),
                ]
            ),
            floats=[
                Float(right=0, height=1, bottom=1, content=_Arg()),
                Float(
                    bottom=1,
                    left=0,
                    right=0,
                    height=1,
                    content=ConditionalContainer(
                        content=MessageToolbarBar(pager),
                        filter=Condition(lambda: bool(pager.message)),
                    ),
                ),
                Float(
                    right=0,
                    height=1,
                    bottom=1,
                    content=ConditionalContainer(
                        content=FormattedTextToolbar(
                            lambda: [("class:loading", " Loading... ")],
                        ),
                        filter=Condition(
                            lambda: pager.current_source_info.waiting_for_input_stream
                        ),
                    ),
                ),
                Float(xcursor=True, ycursor=True, content=MultiColumnCompletionsMenu()),
            ],
        )

    def _get_statusbar_left_tokens(self) -> HTML:
        """
        Displayed at the bottom left.
        """
        if self.pager.displaying_help:
            return HTML(" HELP -- Press <key>[q]</key> when done")
        else:
            return HTML(" (press <key>[h]</key> for help or <key>[q]</key> to quit)")

    def _get_statusbar_right_tokens(self) -> StyleAndTextTuples:
        """
        Displayed at the bottom right.
        """
        source_info = self.pager.source_info[self.pager.current_source]
        buffer = source_info.buffer
        document = buffer.document
        row = document.cursor_position_row + 1
        col = str(document.cursor_position_col + 1)

        if source_info.wrap_lines:
            col = "WRAP"

        if self.pager.current_source.eof():
            percentage = int(100 * row / document.line_count)
            return [
                (
                    "class:statusbar,cursor-position",
                    " (%s,%s) %s%% " % (row, col, percentage),
                )
            ]
        else:
            return [("class:statusbar,cursor-position", " (%s,%s) " % (row, col))]


def create_buffer_window(source_info: "SourceInfo") -> Window:
    """
    Window for the main content.
    """
    pager = source_info.pager

    input_processors = [
        ConditionalProcessor(
            processor=_EscapeProcessor(source_info),
            filter=Condition(lambda: not bool(source_info.source.lexer)),
        ),
        TabsProcessor(),
        ConditionalProcessor(
            processor=HighlightSearchProcessor(),
            filter=Condition(lambda: pager.highlight_search),
        ),
        ConditionalProcessor(
            processor=HighlightIncrementalSearchProcessor(),
            filter=Condition(lambda: pager.highlight_search),
        ),
        HighlightSelectionProcessor(),
        HighlightMatchingBracketProcessor(),
    ]

    @Condition
    def wrap_lines() -> bool:
        return source_info.wrap_lines

    return Window(
        always_hide_cursor=True,
        wrap_lines=wrap_lines,
        content=BufferControl(
            buffer=source_info.buffer,
            lexer=source_info.source.lexer,
            input_processors=input_processors,
            include_default_input_processors=False,
            preview_search=True,
            search_buffer_control=pager.layout.search_toolbar.control,
        ),
    )
