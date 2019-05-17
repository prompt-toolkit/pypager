"""
Pager implementation in Python.
"""
from __future__ import unicode_literals
import sys
import threading
import weakref

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import Style
from prompt_toolkit import __version__ as ptk_version

from .help import HELP
from .key_bindings import create_key_bindings
from .layout import PagerLayout, create_buffer_window
from .source import DummySource, FileSource, PipeSource, FormattedTextSource, Source
from .style import ui_style

PTK3 = ptk_version.startswith('3.')

if PTK3:
    from asyncio import get_event_loop
else:
    from prompt_toolkit.eventloop import get_event_loop

__all__ = (
    'Pager',
)

class _SourceInfo(object):
    """
    For each opened source, we keep this list of pager data.
    """
    _buffer_counter = 0  # Counter to generate unique buffer names.

    def __init__(self, pager, source):
        assert isinstance(pager, Pager)
        assert isinstance(source, Source)

        self.pager = pager
        self.source = source

        self.buffer = Buffer(read_only=True)

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.line_tokens = [[]]

        # Marks. (Mapping from mark name to (cursor position, scroll_offset).)
        self.marks = {}

        # `Pager` sets this flag when he starts reading the generator of this
        # source in a coroutine.
        self.waiting_for_input_stream = False

        self.window = create_buffer_window(self)


class Pager(object):
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
    def __init__(self, vi_mode=False, style=None, search_text=None,
                 titlebar_tokens=None):
        assert isinstance(vi_mode, bool)
        assert style is None or isinstance(style, Style)

        self.sources = []
        self.current_source_index = 0  # Index in `self.sources`.
        self.highlight_search = True
        self.in_colon_mode = False
        self.message = None
        self.displaying_help = False
        self.search_text = search_text
        self.display_titlebar = bool(titlebar_tokens)
        self.titlebar_tokens = titlebar_tokens or []

        self._dummy_source = DummySource()

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

        # Status information for all sources. Source -> _SourceInfo.
        # (Remember this info as long as the Source object exists.)
        self.source_info = weakref.WeakKeyDictionary()

        # Create prompt_toolkit stuff.

        def open_file(buff):
            # Open file.
            self.open_file(buff.text)

            # Focus main buffer again.
            buff.reset()

        # Buffer for the 'Examine:' input.
        self.examine_buffer = Buffer(
            name='EXAMINE',
            completer=PathCompleter(expanduser=True),
            accept_handler=open_file,
            multiline=False)

        # Search buffer.
        self.search_buffer = Buffer(multiline=False)

        self.layout = PagerLayout(self)

        bindings = create_key_bindings(self)
        self.application = Application(
            input=create_input(sys.stdout),
            layout=Layout(container=self.layout.container),
            enable_page_navigation_bindings=True,
            key_bindings=bindings,
            style=style or Style.from_dict(ui_style),
            mouse_support=True,
            after_render=self._after_render,
            full_screen=True)

        # Hide message when a key is pressed.
        def key_pressed(_):
            self.message = None
        self.application.key_processor.before_key_press += key_pressed

        if vi_mode:
            self.application.editing_mode = EditingMode.VI

    @classmethod
    def from_pipe(cls, lexer=None):
        """
        Create a pager from another process that pipes in our stdin.
        """
        assert not sys.stdin.isatty()
        self = cls()
        self.add_source(PipeSource(fileno=sys.stdin.fileno(), lexer=lexer))
        return self

    @property
    def current_source(self):
        " The current `Source`. "
        try:
            return self.sources[self.current_source_index]
        except IndexError:
            return self._dummy_source

    @property
    def current_source_info(self):
        try:
            return self.source_info[self.current_source]
        except KeyError:
            return _SourceInfo(self, self.current_source)

    def open_file(self, filename):
        """
        Open this file.
        """
        lexer = PygmentsLexer.from_filename(filename, sync_from_start=False)

        try:
            source = FileSource(filename, lexer=lexer)
        except IOError as e:
            self.message = '{}'.format(e)
        else:
            self.add_source(source)

    def add_source(self, source):
        """
        Add a new :class:`.Source` instance.
        """
        assert isinstance(source, Source)

        source_info = _SourceInfo(self, source)
        self.source_info[source] = source_info

        self.sources.append(source)

        # Focus
        self.current_source_index = len(self.sources) - 1
        self.application.layout.focus(source_info.window)

    def remove_current_source(self):
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

    def focus_previous_source(self):
        self.current_source_index = (self.current_source_index - 1) % len(self.sources)
        self.application.layout.focus(self.current_source_info.window)
        self.in_colon_mode = False

    def focus_next_source(self):
        self.current_source_index = (self.current_source_index + 1) % len(self.sources)
        self.application.layout.focus(self.current_source_info.window)
        self.in_colon_mode = False

    def display_help(self):
        """
        Display help text.
        """
        if not self.displaying_help:
            source = FormattedTextSource(HELP, name='<help>')
            self.add_source(source)
            self.displaying_help = True

    def quit_help(self):
        """
        Hide the help text.
        """
        if self.displaying_help:
            self.remove_current_source()
            self.displaying_help = False

    def _after_render(self, app):
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

        if not source_info.waiting_for_input_stream and not source.eof() and info:
            lines_below_bottom = info.ui_content.line_count - info.last_visible_line()

            # Make sure to preload at least 2x the amount of lines on a page.
            if lines_below_bottom < info.window_height * 2 or self.forward_forever:
                # Lines to be loaded.
                lines = [info.window_height * 2 - lines_below_bottom]  # nonlocal

                fd = source.get_fd()

                def handle_content(tokens):
                    """ Handle tokens, update `line_tokens`, decrease
                    line count and return list of characters. """
                    data = []
                    for token_char in tokens:
                        char = token_char[1]
                        if char == '\n':
                            line_tokens.append([])

                            # Decrease line count.
                            lines[0] -= 1
                        else:
                            line_tokens[-1].append(token_char)
                        data.append(char)
                    return data

                def insert_text(list_of_fragments):
                    document = Document(b.text + ''.join(list_of_fragments), b.cursor_position)
                    b.set_document(document, bypass_readonly=True)

                    if self.forward_forever:
                        b.cursor_position = len(b.text)

                def receive_content_from_fd():
                    # Read data from the source.
                    tokens = source.read_chunk()
                    data = handle_content(tokens)

                    # Set document.
                    insert_text(data)

                    # Remove the reader when we received another whole page.
                    # or when there is nothing more to read.
                    if lines[0] <= 0 or source.eof():
                        if fd is not None:
                            get_event_loop().remove_reader(fd)
                        source_info.waiting_for_input_stream = False

                    # Redraw.
                    self.application.invalidate()

                def receive_content_from_generator():
                    " (in executor) Read data from generator. "
                    # Call `read_chunk` as long as we need more lines.
                    while lines[0] > 0 and not source.eof():
                        tokens = source.read_chunk()
                        data = handle_content(tokens)
                        insert_text(data)

                        # Schedule redraw.
                        self.application.invalidate()

                    source_info.waiting_for_input_stream = False

                # Set 'waiting_for_input_stream' and render.
                source_info.waiting_for_input_stream = True
                self.application.invalidate()

                # Add reader for stdin.
                if fd is not None:
                    get_event_loop().add_reader(fd, receive_content_from_fd)
                else:
                    # Execute receive_content_from_generator in thread.
                    # (Don't use 'run_in_executor', because we need a daemon.
                    t = threading.Thread(target=receive_content_from_generator)
                    t.daemon = True
                    t.start()

    def run(self):
        """
        Create an event loop for the application and run it.
        """
        try:
            # Set search highlighting.
            if self.search_text:
                self.application.search_state.text = self.search_text

            return self.application.run()
        finally:
            # XXX: Close all sources which are opened by the pager itself.
            pass
