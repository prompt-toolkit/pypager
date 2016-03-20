"""
Pager implementation in Python.
"""
from __future__ import unicode_literals
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.input import StdinInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.key_binding.vi_state import ViState
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.utils import Callback
from prompt_toolkit.buffer_mapping import BufferMapping
from collections import defaultdict
from .layout import Layout
from .key_bindings import create_key_bindings
from .style import create_style
from .source import PipeSource, Source

__all__ = (
    'Pager',
)


class Pager(object):
    """
    The Pager main application.

    Usage::
        p = Pager()
        p.run()

    :param source: :class:`.Source` instance.
    :param lexer: Prompt_toolkit `lexer` instance.
    :param vi_mode: Enable Vi key bindings.
    :param style: Prompt_toolkit `Style` instance.
    """
    _buffer_counter = 0  # Counter to generate unique buffer names.

    def __init__(self, sources, vi_mode=False, style=None):
        assert all(isinstance(s, Source) for s in sources)
        assert len(sources) > 0

        self.sources = sources
        self.current_source = 0  # Index in `self.sources`.
        self.vi_mode = vi_mode
        self.vi_state = ViState()
        self.highlight_search = True

        # When this is True, always make sure that the cursor goes to the
        # bottom of the visible content. This is similar to 'tail -f'.
        self.forward_forever = False

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.source_to_line_tokens = {s: [[]] for s in sources}

        # Marks. (Mapping from mark name to (cursor position, scroll_offset).)
        self.source_to_marks = {  # TODO: make weak.
            s: {}
            for s in sources
        }

        # Create a Buffer for each source.
        self.source_to_buffer = {  # TODO: make weak.
            s: Buffer(is_multiline=True, read_only=True)
            for s in sources
        }
        self.source_to_buffer_name = {
            s: self._generate_buffer_name()
            for s in sources
        }

        # Create prompt_toolkit stuff.
        self.buffers = BufferMapping({
            self.source_to_buffer_name[s]: self.source_to_buffer[s]
            for s in sources
        })
        self.buffers.focus(None, self.source_to_buffer_name[self.source])

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
        sources = [PipeSource(fileno=sys.stdin.fileno(), lexer=lexer)]
        return cls(sources)

    @classmethod
    def _generate_buffer_name(cls):
        " Generate a new buffer name. "
        cls._buffer_counter += 1
        return 'source_%i' % cls._buffer_counter

    @property
    def source(self):
        " The current `Source`. "
        return self.sources[self.current_source]

    @property
    def line_tokens(self):
        return self.source_to_line_tokens[self.source]

    @property
    def marks(self):
        return self.source_to_marks[self.source]

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
        b = self.source_to_buffer[source]

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

            self.cli.run(reset_current_buffer=False)
        finally:
            self.eventloop.close()
            self.eventloop = None
