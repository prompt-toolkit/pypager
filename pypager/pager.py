"""
Pager implementation in Python.
"""
from __future__ import unicode_literals
import sys
import weakref
from collections import defaultdict
from pygments.lexers.markup import RstLexer

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer, AcceptAction
from prompt_toolkit.buffer_mapping import BufferMapping
from prompt_toolkit.contrib.completers import PathCompleter
from prompt_toolkit.document import Document
from prompt_toolkit.input import StdinInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.key_binding.vi_state import ViState
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.styles import Style
from prompt_toolkit.utils import Callback

from .help import HELP
from .key_bindings import create_key_bindings
from .layout import Layout
from .source import FileSource, PipeSource, Source
from .source import StringSource
from .style import create_style

__all__ = (
    'Pager',
)

class _SourceInfo(object):
    """
    For each opened source, we keep this list of pager data.
    """
    _buffer_counter = 0  # Counter to generate unique buffer names.

    def __init__(self):
        self.buffer = Buffer(is_multiline=True, read_only=True)
        self.buffer_name = self._generate_buffer_name()

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.line_tokens = [[]]

        # Marks. (Mapping from mark name to (cursor position, scroll_offset).)
        self.marks = {}

    @classmethod
    def _generate_buffer_name(cls):
        " Generate a new buffer name. "
        cls._buffer_counter += 1
        return 'source_%i' % cls._buffer_counter


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
    """
    def __init__(self, vi_mode=False, style=None):
        assert isinstance(vi_mode, bool)
        assert style is None or isinstance(style, Style)

        self.sources = []
        self.current_source = 0  # Index in `self.sources`.
        self.vi_mode = vi_mode
        self.vi_state = ViState()
        self.highlight_search = True
        self.in_colon_mode = False
        self.message = None
        self.displaying_help = False

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

        # Status information for all sources. Source -> _SourceInfo.
        # (Remember this info as long as the Source object exists.)
        self.source_info = weakref.WeakKeyDictionary()

        # Create prompt_toolkit stuff.
        self.buffers = BufferMapping({})

        def open_file(cli, buff):
            # Open file.
            self.open_file(buff.text)

            # Focus main buffer again.
            self.buffers.focus(cli, self.source_info[self.source].buffer_name)
            buff.reset()

        self.buffers['EXAMINE'] = Buffer(
            # Buffer for the 'Examine:' input.
            completer=PathCompleter(expanduser=True),
            accept_action=AcceptAction(open_file))

        self.layout = Layout(self)

        manager = create_key_bindings(self)
        self.application = Application(
            layout=self.layout.container,
            buffers=self.buffers,
            key_bindings_registry=manager.registry,
            style=style or create_style(),
            mouse_support=True,
            on_render=Callback(self._on_render),
            use_alternate_screen=True)

        self.cli = None
        self.eventloop = None
        self._waiting_for_input_stream = defaultdict(bool)  # Source -> bool

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
    def source(self):
        " The current `Source`. "
        return self.sources[self.current_source]

    @property
    def line_tokens(self):
        return self.source_info[self.source].line_tokens

    @property
    def marks(self):
        return self.source_info[self.source].marks

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

        source_info = _SourceInfo()
        self.source_info[source] = source_info

        self.buffers[source_info.buffer_name] = source_info.buffer
        self.sources.append(source)

        # Focus
        self.current_source = len(self.sources) - 1
        self.buffers.focus(None, source_info.buffer_name)

    def remove_current_source(self):
        """
        Remove the current source from the pager.
        (If >1 source is left.)
        """
        if len(self.sources) > 1:
            current_source = self.source

            # Focus the previous source.
            self.focus_previous_source()

            # Remove the last source.
            buffer_name = self.source_info[current_source].buffer_name
            self.sources.remove(current_source)
            del self.buffers[buffer_name]
        else:
            self.message = "Can't remove the last buffer."

    def focus_previous_source(self):
        self.current_source = (self.current_source - 1) % len(self.sources)
        self.buffers.focus(None, self.source_info[self.source].buffer_name)
        self.in_colon_mode = False

    def focus_next_source(self):
        self.current_source = (self.current_source + 1) % len(self.sources)
        self.buffers.focus(None, self.source_info[self.source].buffer_name)
        self.in_colon_mode = False

    def display_help(self):
        """
        Display help text.
        """
        if not self.displaying_help:
            source = StringSource(HELP, lexer=PygmentsLexer(RstLexer))
            self.add_source(source)
            self.displaying_help = True

    def quit_help(self):
        """
        Hide the help text.
        """
        if self.displaying_help:
            self.remove_current_source()
            self.displaying_help = False

    def _on_render(self, cli):
        """
        Each time when the rendering is done, we should see whether we need to
        read more data from the input pipe.
        """
        # When the bottom is visible, read more input.
        # Try at least `info.window_height`, if this amount of data is
        # available.
        info = self.layout.dynamic_body.get_render_info()
        source = self.source
        b = self.source_info[source].buffer

        if not self._waiting_for_input_stream[source] and not source.eof() and info:
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
                            self.line_tokens.append([])

                            # Decrease line count.
                            lines[0] -= 1
                        else:
                            self.line_tokens[-1].append(token_char)
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
                            self.eventloop.remove_reader(fd)
                        self._waiting_for_input_stream[source] = False

                    # Redraw.
                    if data:
                        self.cli.invalidate()

                def receive_content_from_generator():
                    # Call `read_chunk` as long as we need more lines.
                    data = []
                    while lines[0] > 0 and not source.eof():
                        tokens = source.read_chunk()
                        data.extend(handle_content(tokens))

                    # Set document.
                    insert_text(data)

                    # Redraw.
                    if data:
                        self.cli.invalidate()

                # Add reader for stdin.
                if fd is not None:
                    self._waiting_for_input_stream[source] = True
                    self.eventloop.add_reader(fd, receive_content_from_fd)
                else:
                    receive_content_from_generator()

    def run(self):
        """
        Create an event loop for the application and run it.
        """
        self.eventloop = create_eventloop()

        try:
            self.cli = CommandLineInterface(
                application=self.application,
                eventloop=self.eventloop,
                input=StdinInput(sys.stdout))

            # Hide message when a key is pressed.
            def key_pressed():
                self.message = None
            self.cli.input_processor.beforeKeyPress += key_pressed

            self.cli.run(reset_current_buffer=False)
        finally:
            # Close eventloop.
            self.eventloop.close()
            self.eventloop = None

            # XXX: Close all sources which are opened by the pager itself.
