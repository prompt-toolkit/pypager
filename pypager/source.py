"""
Input source for a pager.
(pipe or generator.)
"""
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod
from six import with_metaclass
from prompt_toolkit.token import Token
from prompt_toolkit.eventloop.posix_utils import PosixStdinReader
from prompt_toolkit.layout.utils import explode_tokens
from prompt_toolkit.styles import Attrs
from prompt_toolkit.terminal.vt100_output import FG_ANSI_COLORS, BG_ANSI_COLORS
from prompt_toolkit.terminal.vt100_output import _256_colors as _256_colors_table
from prompt_toolkit.layout.lexers import Lexer
import types
import six
import codecs
import os

__all__ = (
    'Source',
    'PipeSource',
    'GeneratorSource',
    'StringSource',
)


class Source(with_metaclass(ABCMeta, object)):
    #: The lexer to be used in the layout.
    lexer = None

    @abstractmethod
    def get_fd(self):
        " Wait until this fd is ready. Returns None if we should'nt wait. "

    @abstractmethod
    def get_name(self):
        " Return the filename or name for this input. "

    @abstractmethod
    def eof(self):
        " Return True when we reached the end of the input. "

    @abstractmethod
    def read_chunk(self):
        " Read data from input. Return a list of token/text tuples. "

    def close(self):
        pass


class PipeSource(Source):
    """
    When input is read from another process that is chained to use through a
    unix pipe.
    """
    def __init__(self, fileno, lexer=None, name='<stdin>'):
        assert isinstance(fileno, int)
        assert lexer is None or isinstance(lexer, Lexer)
        assert isinstance(name, six.text_type)

        self.fileno = fileno
        self.lexer = lexer
        self.name = name

        self._line_tokens = []
        self._eof = False

        # Default style attributes.
        self._attrs = Attrs(
            color=None, bgcolor=None, bold=False, underline=False,
            italic=False, blink=False, reverse=False)

        # Start input parser.
        self._parser = self._parse_corot()
        next(self._parser)
        self._stdin_reader = PosixStdinReader(fileno)

    def get_name(self):
        return self.name

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

        # Return the tokens from the parser.
        # (Don't return the last token yet, because the parser should
        # be able to pop if the input starts with \b).
        if self._eof:
            tokens = self._line_tokens[:]
            del self._line_tokens[:]
        else:
            tokens = self._line_tokens[:-1]
            del self._line_tokens[:-1]

        return tokens

    def _parse_corot(self):
        """
        Coroutine that parses the pager input.
        A \b with any character before should make the next character standout.
        A \b with an underscore before should make the next character emphasized.
        """
        token = Token
        line_tokens = self._line_tokens
        replace_one_token = False

        while True:
            csi = False
            c = yield

            if c == '\b':
                # Handle \b escape codes from man pages.
                if line_tokens:
                    _, last_char = line_tokens[-1]
                    line_tokens.pop()
                    replace_one_token = True
                    if last_char == '_':
                        token = Token.Standout2
                    else:
                        token = Token.Standout
                continue

            elif c == '\x1b':
                # Start of color escape sequence.
                square_bracket = yield
                if square_bracket == '[':
                    csi = True
                else:
                    continue
            elif c == '\x9b':
                csi = True

            if csi:
                # Got a CSI sequence. Color codes are following.
                current = ''
                params = []
                while True:
                    char = yield
                    if char.isdigit():
                        current += char
                    else:
                        params.append(min(int(current or 0), 9999))
                        if char == ';':
                            current = ''
                        elif char == 'm':
                            # Set attributes and token.
                            self._select_graphic_rendition(params)
                            token = ('C', ) + self._attrs
                            break
                        else:
                            # Ignore unspported sequence.
                            break
            else:
                line_tokens.append((token, c))
                if replace_one_token:
                    token = Token

    def _select_graphic_rendition(self, attrs):
        """
        Taken a list of graphics attributes and apply changes to Attrs.
        """
        # NOTE: This function is almost literally taken from Pymux.
        #       if something is wrong, please report there as well!
        #       https://github.com/jonathanslenders/pymux
        replace = {}

        if not attrs:
            attrs = [0]
        else:
            attrs = list(attrs[::-1])

        while attrs:
            attr = attrs.pop()

            if attr in _fg_colors:
                replace["color"] = _fg_colors[attr]
            elif attr in _bg_colors:
                replace["bgcolor"] = _bg_colors[attr]
            elif attr == 1:
                replace["bold"] = True
            elif attr == 3:
                replace["italic"] = True
            elif attr == 4:
                replace["underline"] = True
            elif attr == 5:
                replace["blink"] = True
            elif attr == 6:
                replace["blink"] = True  # Fast blink.
            elif attr == 7:
                replace["reverse"] = True
            elif attr == 22:
                replace["bold"] = False
            elif attr == 23:
                replace["italic"] = False
            elif attr == 24:
                replace["underline"] = False
            elif attr == 25:
                replace["blink"] = False
            elif attr == 27:
                replace["reverse"] = False
            elif not attr:
                replace = {}
                self._attrs = Attrs(
                    color=None, bgcolor=None, bold=False, underline=False,
                    italic=False, blink=False, reverse=False)

            elif attr in (38, 48):
                n = attrs.pop()

                # 256 colors.
                if n == 5:
                    if attr == 38:
                        m = attrs.pop()
                        replace["color"] = _256_colors.get(1024 + m)
                    elif attr == 48:
                        m = attrs.pop()
                        replace["bgcolor"] = _256_colors.get(1024 + m)

                # True colors.
                if n == 2:
                    try:
                        color_str = '%02x%02x%02x' % (attrs.pop(), attrs.pop(), attrs.pop())
                    except IndexError:
                        pass
                    else:
                        if attr == 38:
                            replace["color"] = color_str
                        elif attr == 48:
                            replace["bgcolor"] = color_str

        self._attrs = self._attrs._replace(**replace)


class FileSource(PipeSource):
    def __init__(self, filename, lexer=None):
        self.fp =  codecs.open(
            os.path.expanduser(filename),
            'rb', encoding='utf-8', errors='ignore')

        super(FileSource, self).__init__(
            self.fp.fileno(), lexer=lexer, name=filename)

    def close(self):
        self.fp.close()


# Mapping of the ANSI color codes to their names.
_fg_colors = dict((v, k) for k, v in FG_ANSI_COLORS.items())
_bg_colors = dict((v, k) for k, v in BG_ANSI_COLORS.items())

# Mapping of the escape codes for 256colors to their 'ffffff' value.
_256_colors = {}

for i, (r, g, b) in enumerate(_256_colors_table.colors):
    _256_colors[1024 + i] = '%02x%02x%02x' % (r, g, b)


class GeneratorSource(Source):
    """
    When the input is coming from a Python generator.
    """
    def __init__(self, generator, lexer=None, name=''):
        assert isinstance(generator, types.GeneratorType)
        assert lexer is None or isinstance(lexer, Lexer)
        assert isinstance(name, six.text_type)

        self._eof = False
        self.generator = generator
        self.lexer = lexer
        self.name = name

    def get_name(self):
        return self.name

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


class StringSource(Source):
    """
    Take a Python string is input for the pager.
    """
    def __init__(self, text, lexer, name=''):
        assert isinstance(text, six.text_type)
        assert lexer is None or isinstance(lexer, Lexer)

        self.text = text
        self.lexer = lexer
        self.name = name
        self._read = False

    def get_name(self):
        return self.name

    def get_fd(self):
        return None

    def eof(self):
        return self._read

    def read_chunk(self):
        if self._read:
            return []
        else:
            self._read = True
            return explode_tokens([(Token, self.text)])
