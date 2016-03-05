"""
Pager implementation in Python.
"""
from __future__ import unicode_literals
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.input import StdinInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.utils import Callback

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

    :param
    """
    def __init__(self, source):
        assert isinstance(source, Source)

        self.source = source

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.line_tokens = [[]]

        # Create prompt_toolkit stuff.
        self.buffers = {
            DEFAULT_BUFFER: Buffer(is_multiline=True, read_only=True),
        }

        self.layout = Layout(self)

        manager = create_key_bindings()
        self.application = Application(
            layout=self.layout.container,
            buffers=self.buffers,
            key_bindings_registry=manager.registry,
            style=create_style(),
            mouse_support=True,
            on_render=Callback(self._on_render),
            use_alternate_screen=True)

        self.cli = None
        self.eventloop = None
        self._waiting_for_input_stream = False

    @classmethod
    def from_pipe(cls):
        """
        Create a pager from another process that pipes in our stdin.
        """
        assert not sys.stdin.isatty()
        return cls(PipeSource(fileno=sys.stdin.fileno()))

    def _on_render(self, cli):
        """
        Each time when the rendering is done, we should see whether we need to
        read more data from the input pipe.
        """
        # When the bottom is visible, read more input.
        # Try at least `info.window_height`, if this amount of data is
        # available.
        info = self.layout.buffer_window.render_info

        if not self._waiting_for_input_stream and not self.source.eof() and info:
            lines_below_bottom = info.ui_content.line_count - info.last_visible_line()

            # Make sure to preload at least 2x the amount of lines on a page.
            if lines_below_bottom < info.window_height * 2:
                # Make sure to load at least 2x the amount of lines on a page.
                lines = [info.window_height * 2 - lines_below_bottom]  # nonlocal

                fd = self.source.get_fd()
                b = self.buffers[DEFAULT_BUFFER]

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

                def receive_content_from_fd():
                    # Read data from the source.
                    tokens = self.source.read_chunk()
                    data = handle_content(tokens)

                    # Set document.
                    document = Document(b.text + ''.join(data), b.cursor_position)
                    b.set_document(document, bypass_readonly=True)

                    # Remove the reader when we received another whole page.
                    # or when there is nothing more to read.
                    if lines[0] <= 0 or self.source.eof():
                        if fd is not None:
                            self.eventloop.remove_reader(fd)
                        self._waiting_for_input_stream = False

                    # Redraw.
                    if data:
                        self.cli.invalidate()

                def receive_content_from_generator():
                    # Call `read_chunk` as long as we need more lines.
                    data = []
                    while lines[0] > 0 and not self.source.eof():
                        tokens = self.source.read_chunk()
                        data.extend(handle_content(tokens))

                    # Set document.
                    document = Document(b.text + ''.join(data), b.cursor_position)
                    b.set_document(document, bypass_readonly=True)

                    # Redraw.
                    if data:
                        self.cli.invalidate()

                # Add reader for stdin.
                if fd is not None:
                    self._waiting_for_input_stream = True
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
