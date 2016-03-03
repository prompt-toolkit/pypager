"""
Pager implementation in Python.
"""
from __future__ import unicode_literals
import sys
import re

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.input import StdinInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.token import Token
from prompt_toolkit.eventloop.posix_utils import PosixStdinReader
from prompt_toolkit.utils import Callback

from .layout import Layout
from .key_bindings import create_key_bindings
from .style import create_style

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
    def __init__(self, fileno):
        self.fileno = fileno
        self.eof = False  # End of file.

        # List of lines. (Each line is a list of (token, text) tuples itself.)
        self.line_tokens = [[]]

        # Start input parser.
        self._parser = self._parse_corot()
        next(self._parser)
        self._stdin_reader = PosixStdinReader(fileno)

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
        return cls(fileno=sys.stdin.fileno())

    def _parse_corot(self):
        """
        Coroutine that parses the pager input.
        A \b with any character before should make the next character standout.
        A \b with an underscore before should make the next character emphasized.
        """
        token = Token
        line_tokens = self.line_tokens

        while True:
            c = yield

            if c == '\b':
                last_token, last_char = line_tokens[-1][-1]
                line_tokens[-1].pop()
                if last_char == '_':
                    token = Token.Standout2
                else:
                    token = Token.Standout
            elif c == '\n':
                line_tokens.append([])
            else:
                line_tokens[-1].append((token, c))
                if token != Token:
                    token = Token

    def _on_render(self, cli):
        """
        Each time when the rendering is done, we should see whether we need to
        read more data from the input pipe.
        """
        # When the bottom is visible, read more input.
        # Try at least `info.window_height`, if this amount of data is
        # available.
        info = self.layout.buffer_window.render_info
        b = self.buffers[DEFAULT_BUFFER]

        if not self._waiting_for_input_stream and not self.eof and info and info.bottom_visible:
            self._waiting_for_input_stream = True

            # Make sure to load at least 2x the amount of lines on a page.
            lines = [info.window_height * 2]  # nonlocal

            def content_received():
                # Content is ready for reading on stdin.
                data = self._stdin_reader.read()

                if not data:
                    self.eof = True

                # Send input data to the parser.
                for c in data:
                    self._parser.send(c)

                # Add data to the buffer document.
                data = re.sub('.\b', '', data)

                document = Document(b.text + data, b.cursor_position)
                b.set_document(document, bypass_readonly=True)

                # Decrease line count.
                lines[0] -= data.count('\n')

                # Remove the reader when we received another whole page.
                # or when there is nothing more to read.
                if lines[0] <= 0 or self.eof:
                    self.eventloop.remove_reader(self.fileno)
                    self._waiting_for_input_stream = False

                # Redraw.
                if data:
                    self.cli.invalidate()

            # Add reader for stdin.
            self.eventloop.add_reader(self.fileno, content_received)

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
