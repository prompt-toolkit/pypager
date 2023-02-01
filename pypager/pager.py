"""
Pager implementation in Python.
"""
import asyncio
import sys
import threading
import weakref
from typing import Any, Dict, List, Optional, Sequence, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import AnyFormattedText, StyleAndTextTuples
from prompt_toolkit.input import Input
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.lexers import Lexer, PygmentsLexer
from prompt_toolkit.output import Output
from prompt_toolkit.styles import Style

from .help import HELP
from .key_bindings import create_key_bindings
from .layout import PagerLayout, create_buffer_window
from .source import DummySource, FileSource, FormattedTextSource, PipeSource, Source
from .style import ui_style

__all__ = [
    "Pager",
    "SourceInfo",
]


class SourceInfo:
    """
    For each opened source, we keep this list of pager data.
    """

    _buffer_counter = 0  # Counter to generate unique buffer names.

    def __init__(self, pager: "Pager", source: Source) -> None:
        self.pager = pager
        self.source = source

        self.buffer = Buffer(read_only=True)

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.line_tokens: List[StyleAndTextTuples] = [[]]

        # Marks. (Mapping from mark name to (cursor position, scroll_offset).)
        self.marks: Dict[str, Tuple[int, int]] = {}

        # `Pager` sets this flag when he starts reading the generator of this
        # source in a coroutine.
        self.waiting_for_input_stream = False

        # Enable/disable line wrapping.
        self.wrap_lines = False

        self.window = create_buffer_window(self)


class Pager:
    """
    The Pager main application.

    Usage::
        p = Pager()
        p.add_source(...)
        p.run()

    :param source: :class:`.Source` instance.
    :param lexer: Prompt_toolkit `lexer` instance.
    :param vi_mode: Enable Vi key bindings.
    :param style: Prompt_toolkit `Style` instance.
    :param search_text: `None` or the search string that is highlighted.
    """

    def __init__(
        self,
        *,
        vi_mode: bool = False,
        style: Optional[Style] = None,
        search_text: Optional[str] = None,
        titlebar_tokens: Optional[AnyFormattedText] = None,
        input: Optional[Input] = None,
        output: Optional[Output] = None,
    ) -> None:
        self.sources: List[Source] = []
        self.current_source_index = 0  # Index in `self.sources`.
        self.highlight_search = True
        self.in_colon_mode = False
        self.message: Optional[str] = None
        self.displaying_help = False
        self.search_text = search_text
        self.display_titlebar = bool(titlebar_tokens)
        self.titlebar_tokens = titlebar_tokens or []

        self._dummy_source = DummySource()

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

        # Status information for all sources. Source -> SourceInfo.
        # (Remember this info as long as the Source object exists.)
        self.source_info: weakref.WeakKeyDictionary[
            Source, SourceInfo
        ] = weakref.WeakKeyDictionary()

        # Create prompt_toolkit stuff.

        def open_file(buff: Buffer) -> bool:
            # Open file.
            self.open_file(buff.text)
            return False

        # Buffer for the 'Examine:' input.
        self.examine_buffer = Buffer(
            name="EXAMINE",
            completer=PathCompleter(expanduser=True),
            accept_handler=open_file,
            multiline=False,
        )

        # Search buffer.
        self.search_buffer = Buffer(multiline=False)

        self.layout = PagerLayout(self)

        # Input/output.
        if input is None:
            # By default, use the stdout device for input.
            # (This makes it possible to pipe data to stdin, but still read key
            # strokes from the TTY).
            input = create_input(sys.stdout)

        bindings = create_key_bindings(self)
        self.application: Application[None] = Application(
            input=input,
            output=output,
            layout=Layout(container=self.layout.container),
            enable_page_navigation_bindings=True,
            key_bindings=bindings,
            style=style or Style.from_dict(ui_style),
            mouse_support=True,
            after_render=self._after_render,
            full_screen=True,
        )

        # Hide message when a key is pressed.
        def key_pressed(_: object) -> None:
            self.message = None

        self.application.key_processor.before_key_press += key_pressed

        if vi_mode:
            self.application.editing_mode = EditingMode.VI

    @classmethod
    def from_pipe(cls, lexer: Optional[Lexer] = None) -> "Pager":
        """
        Create a pager from another process that pipes in our stdin.
        """
        assert not sys.stdin.isatty()
        self = cls()
        self.add_source(
            PipeSource(
                fileno=sys.stdin.fileno(), lexer=lexer, encoding=sys.stdin.encoding
            )
        )
        return self

    @property
    def current_source(self) -> Source:
        "The current `Source`."
        try:
            return self.sources[self.current_source_index]
        except IndexError:
            return self._dummy_source

    @property
    def current_source_info(self) -> SourceInfo:
        try:
            return self.source_info[self.current_source]
        except KeyError:
            return SourceInfo(self, self.current_source)

    def open_file(self, filename: str) -> None:
        """
        Open this file.
        """
        lexer = PygmentsLexer.from_filename(filename, sync_from_start=False)

        try:
            source = FileSource(filename, lexer=lexer)
        except IOError as e:
            self.message = "{}".format(e)
        else:
            self.add_source(source)

    def add_source(self, source: Source) -> SourceInfo:
        """
        Add a new :class:`.Source` instance.
        """
        source_info = SourceInfo(self, source)
        self.source_info[source] = source_info

        self.sources.append(source)

        # Focus
        self.current_source_index = len(self.sources) - 1
        self.application.layout.focus(source_info.window)

        return source_info

    def remove_current_source(self) -> None:
        """
        Remove the current source from the pager.
        (If >1 source is left.)
        """
        if len(self.sources) > 1:
            current_source_index = self.current_source

            # Focus the previous source.
            self.focus_previous_source()

            # Remove the last source.
            self.sources.remove(current_source_index)
        else:
            self.message = "Can't remove the last buffer."

    def focus_previous_source(self) -> None:
        self.current_source_index = (self.current_source_index - 1) % len(self.sources)
        self.application.layout.focus(self.current_source_info.window)
        self.in_colon_mode = False

    def focus_next_source(self) -> None:
        self.current_source_index = (self.current_source_index + 1) % len(self.sources)
        self.application.layout.focus(self.current_source_info.window)
        self.in_colon_mode = False

    def display_help(self) -> None:
        """
        Display help text.
        """
        if not self.displaying_help:
            source = FormattedTextSource(HELP, name="<help>")
            self.add_source(source)
            self.displaying_help = True

    def quit_help(self) -> None:
        """
        Hide the help text.
        """
        if self.displaying_help:
            self.remove_current_source()
            self.displaying_help = False

    def _after_render(self, app: Application[Any]) -> None:
        """
        Each time when the rendering is done, we should see whether we need to
        read more data from the input pipe.
        """
        # When the bottom is visible, read more input.
        # Try at least `info.window_height`, if this amount of data is
        # available.
        info = self.layout.dynamic_body.get_render_info()
        source = self.current_source
        source_info = self.source_info[source]
        b = source_info.buffer
        line_tokens = source_info.line_tokens
        loop = asyncio.get_event_loop()

        if not source_info.waiting_for_input_stream and not source.eof() and info:
            lines_below_bottom = info.ui_content.line_count - info.last_visible_line()

            # Make sure to preload at least 2x the amount of lines on a page.
            if lines_below_bottom < info.window_height * 2 or self.forward_forever:
                # Lines to be loaded.
                lines = [info.window_height * 2 - lines_below_bottom]  # nonlocal

                def handle_content(tokens: StyleAndTextTuples) -> List[str]:
                    """Handle tokens, update `line_tokens`, decrease
                    line count and return list of characters."""
                    data = []
                    for token_char in tokens:
                        char = token_char[1]
                        if char == "\n":
                            line_tokens.append([])

                            # Decrease line count.
                            lines[0] -= 1
                        else:
                            line_tokens[-1].append(token_char)
                        data.append(char)
                    return data

                def insert_text(list_of_fragments: Sequence[str]) -> None:
                    document = Document(
                        b.text + "".join(list_of_fragments), b.cursor_position
                    )
                    b.set_document(document, bypass_readonly=True)

                    if self.forward_forever:
                        b.cursor_position = len(b.text)

                    # Schedule redraw.
                    self.application.invalidate()

                    source_info.waiting_for_input_stream = False

                def receive_content_from_generator() -> None:
                    "(in executor) Read data from generator."
                    # Call `read_chunk` as long as we need more lines.
                    while lines[0] > 0 and not source.eof():
                        tokens = source.read_chunk()
                        data = handle_content(tokens)
                        loop.call_soon(insert_text, data)

                # Set 'waiting_for_input_stream' and render.
                source_info.waiting_for_input_stream = True
                self.application.invalidate()

                # Execute receive_content_from_generator in thread.
                # (Don't use 'run_in_executor', because we need a daemon.
                t = threading.Thread(target=receive_content_from_generator)
                t.daemon = True
                t.start()

    def _before_run(self) -> None:
        # Set search highlighting.
        if self.search_text:
            self.application.current_search_state.text = self.search_text

    def run(self) -> None:
        """
        Create an event loop for the application and run it.
        """
        try:
            self._before_run()
            return self.application.run()
        finally:
            # XXX: Close all sources which are opened by the pager itself.
            pass

    async def run_async(self) -> None:
        """
        Create an event loop for the application and run it.
        """
        try:
            self._before_run()
            return await self.application.run_async()
        finally:
            # XXX: Close all sources which are opened by the pager itself.
            pass
