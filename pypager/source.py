"""
Input source for a pager.
(pipe or generator.)
"""
from __future__ import unicode_literals
from prompt_toolkit.token import Token
from prompt_toolkit.eventloop.posix_utils import PosixStdinReader
from prompt_toolkit.layout.utils import explode_tokens
import types

__all__ = (
    'Source',
    'PipeSource',
    'GeneratorSource',
)


class Source(object):
    def get_fd(self):
        " Wait until this fd is ready. Returns None if we should'nt wait. "

    def eof(self):
        " Return True when we reached the end of the input. "

    def read_chunk(self):
        " Read data from input. Return a list of token/text tuples. "


class PipeSource(Source):
    """
    When input is read from another process that is chained to use through a
    unix pipe.
    """
    def __init__(self, fileno):
        self.fileno = fileno

        self._line_tokens = []
        self._eof = False

        # Start input parser.
        self._parser = self._parse_corot()
        next(self._parser)
        self._stdin_reader = PosixStdinReader(fileno)

    def get_fd(self):
        return self.fileno

    def eof(self):
        return self._eof

    def read_chunk(self):
        # Content is ready for reading on stdin.
        data = self._stdin_reader.read()

        if not data:
            self._eof = True

        # Send input data to the parser.
        for c in data:
            self._parser.send(c)

        tokens = self._line_tokens[:]
        del self._line_tokens[:]
        return tokens

    def _parse_corot(self):
        """
        Coroutine that parses the pager input.
        A \b with any character before should make the next character standout.
        A \b with an underscore before should make the next character emphasized.
        """
        token = Token
        line_tokens = self._line_tokens

        while True:
            c = yield

            if c == '\b':
                if line_tokens:
                    _, last_char = line_tokens[-1]
                    line_tokens.pop()
                    if last_char == '_':
                        token = Token.Standout2
                    else:
                        token = Token.Standout
            else:
                line_tokens.append((token, c))
                if token != Token:
                    token = Token


class GeneratorSource(Source):
    """
    When the input is coming from a Python generator.
    """
    def __init__(self, generator):
        assert isinstance(generator, types.GeneratorType)
        self._eof = False
        self.generator = generator

    def get_fd(self):
        return None

    def eof(self):
        return self._eof

    def read_chunk(self):
        " Read data from input. Return a list of token/text tuples. "
        try:
            return explode_tokens(next(self.generator))
        except StopIteration:
            self._eof = True
            return []
