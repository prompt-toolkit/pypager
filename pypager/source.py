"""
Input source for a pager.
(pipe or generator.)
"""
import os
from abc import ABCMeta, abstractmethod
from codecs import getincrementaldecoder
from typing import Dict, Generator, Optional, Sequence, Union

from prompt_toolkit.formatted_text import (
    AnyFormattedText,
    StyleAndTextTuples,
    to_formatted_text,
)
from prompt_toolkit.layout.utils import explode_text_fragments
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.output.vt100 import BG_ANSI_COLORS, FG_ANSI_COLORS
from prompt_toolkit.output.vt100 import _256_colors as _256_colors_table
from prompt_toolkit.styles import Attrs

__all__ = [
    "Source",
    "DummySource",
    "PipeSource",
    "GeneratorSource",
    "StringSource",
    "FormattedTextSource",
]


class Source(metaclass=ABCMeta):
    #: The lexer to be used in the layout.
    lexer: Optional[Lexer] = None

    @abstractmethod
    def get_name(self) -> str:
        "Return the filename or name for this input."

    @abstractmethod
    def eof(self) -> bool:
        "Return True when we reached the end of the input."

    @abstractmethod
    def read_chunk(self) -> StyleAndTextTuples:
        """
        Read data from input. Return a list of token/text tuples.

        This can be blocking and will be called in another thread.
        """

    def close(self) -> None:
        pass


class DummySource(Source):
    """
    Empty source.
    """

    def get_name(self) -> str:
        return ""

    def eof(self) -> bool:
        return True

    def read_chunk(self) -> StyleAndTextTuples:
        return []


class PipeSource(Source):
    """
    When input is read from another process that is chained to use through a
    unix pipe.
    """

    def __init__(
        self,
        fileno: int,
        lexer: Optional[Lexer] = None,
        name: str = "<stdin>",
        encoding: str = "utf-8",
    ) -> None:
        self.fileno = fileno
        self.lexer = lexer
        self.name = name

        self._line_tokens: StyleAndTextTuples = []
        self._eof = False

        # Default style attributes.
        self._attrs = Attrs(
            color=None,
            bgcolor=None,
            bold=False,
            underline=False,
            strike=False,
            italic=False,
            blink=False,
            reverse=False,
            hidden=False,
        )

        # Start input parser.
        self._parser = self._parse_corot()
        next(self._parser)

        # Create incremental decoder for decoding stdin.
        # We can not just do `os.read(stdin.fileno(), 1024).decode('utf-8')`,
        # because it could be that we are in the middle of a utf-8 byte
        # sequence.
        self._stdin_decoder_cls = getincrementaldecoder(encoding)
        self._stdin_decoder = self._stdin_decoder_cls(errors="ignore")

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._eof

    def _get_data(self) -> str:
        data = os.read(self.fileno, 1024)

        # Nothing more to read, stream is closed.
        if data == b"":
            self._eof = True
            return ""

        return self._stdin_decoder.decode(data)

    def read_chunk(self) -> StyleAndTextTuples:
        # Content is ready for reading on stdin.
        data = self._get_data()

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

    def _parse_corot(self) -> Generator[None, str, None]:
        """
        Coroutine that parses the pager input.
        A \b with any character before should make the next character standout.
        A \b with an underscore before should make the next character emphasized.
        """
        backspace_style = ""  # Style created by backspace characters.
        line_tokens = self._line_tokens
        replace_one_token = False

        while True:
            csi = False
            c = yield

            if c == "\b":
                # Handle \b escape codes from man pages.
                if line_tokens:
                    last_char = line_tokens[-1][1]
                    line_tokens.pop()
                    replace_one_token = True
                    if last_char == "_":
                        backspace_style = "class:standout2"
                    else:
                        backspace_style = "class:standout"
                continue

            elif c == "\x1b":
                # Start of color escape sequence.
                square_bracket = yield
                if square_bracket == "[":
                    csi = True
                else:
                    continue
            elif c == "\x9b":
                csi = True

            if csi:
                # Got a CSI sequence. Color codes are following.
                current = ""
                params = []
                while True:
                    char = yield
                    if char.isdigit():
                        current += char
                    else:
                        params.append(min(int(current or 0), 9999))
                        if char == ";":
                            current = ""
                        elif char == "m":
                            # Set attributes and token.
                            self._select_graphic_rendition(
                                params
                            )  ### TODO: use inline style.
                            #### token = ('C', ) + self._attrs
                            break
                        else:
                            # Ignore unspported sequence.
                            break
            else:
                line_tokens.append((self._get_attrs_style() + " " + backspace_style, c))
                if replace_one_token:
                    backspace_style = ""

    def _select_graphic_rendition(self, attrs: Sequence[int]) -> None:
        """
        Taken a list of graphics attributes and apply changes to Attrs.
        """
        # NOTE: This function is almost literally taken from Pymux.
        #       if something is wrong, please report there as well!
        #       https://github.com/jonathanslenders/pymux
        replace: Dict[str, Union[bool, str, None]] = {}

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
                    color=None,
                    bgcolor=None,
                    bold=False,
                    underline=False,
                    strike=False,
                    italic=False,
                    blink=False,
                    reverse=False,
                    hidden=False,
                )

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
                        color_str = "%02x%02x%02x" % (
                            attrs.pop(),
                            attrs.pop(),
                            attrs.pop(),
                        )
                    except IndexError:
                        pass
                    else:
                        if attr == 38:
                            replace["color"] = color_str
                        elif attr == 48:
                            replace["bgcolor"] = color_str

        self._attrs = self._attrs._replace(**replace)  # type: ignore

    def _get_attrs_style(self) -> str:
        result = []
        attrs = self._attrs

        if attrs.color:
            result.append(" fg:{} ".format(attrs.color))
        if attrs.bgcolor:
            result.append(" bg:{} ".format(attrs.bgcolor))
        if attrs.bold:
            result.append(" bold ")
        if attrs.italic:
            result.append(" italic ")
        if attrs.underline:
            result.append(" underline ")
        if attrs.blink:
            result.append(" blink ")
        if attrs.reverse:
            result.append(" reverse ")

        # Recent versions of Groff (used for man pages) use bold and underline
        # escape sequences rather then backslash-style escape sequences. Apply
        # the standout/standout2 styles anyway so that we get colored output.
        # This way, people don't have to set GROFF_NO_SGR=1.
        if attrs.bold and not attrs.color:
            result.append(" class:standout ")
        if attrs.underline and not attrs.color:
            result.append(" class:standout2 ")

        return "".join(result)


class FileSource(PipeSource):
    def __init__(self, filename: str, lexer: Optional[Lexer] = None) -> None:
        self.fp = open(filename, "rb")

        super().__init__(self.fp.fileno(), lexer=lexer, name=filename)

    def close(self) -> None:
        self.fp.close()


# Mapping of the ANSI color codes to their names.
_fg_colors = {v: k for k, v in FG_ANSI_COLORS.items()}
_bg_colors = {v: k for k, v in BG_ANSI_COLORS.items()}

# Mapping of the escape codes for 256colors to their 'ffffff' value.
_256_colors = {}

for i, (r, g, b) in enumerate(_256_colors_table.colors):
    _256_colors[1024 + i] = "%02x%02x%02x" % (r, g, b)


class GeneratorSource(Source):
    """
    When the input is coming from a Python generator.
    """

    def __init__(
        self,
        generator: Generator[StyleAndTextTuples, None, None],
        lexer: Optional[Lexer] = None,
        name: str = "",
    ) -> None:
        self._eof = False
        self.generator = generator
        self.lexer = lexer
        self.name = name

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._eof

    def read_chunk(self) -> StyleAndTextTuples:
        "Read data from input. Return a list of token/text tuples."
        try:
            return explode_text_fragments(next(self.generator))
        except StopIteration:
            self._eof = True
            return []


class StringSource(Source):
    """
    Take a Python string is input for the pager.
    """

    def __init__(
        self, text: str, lexer: Optional[Lexer] = None, name: str = ""
    ) -> None:
        self.text = text
        self.lexer = lexer
        self.name = name
        self._read = False

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._read

    def read_chunk(self) -> StyleAndTextTuples:
        if self._read:
            return []
        else:
            self._read = True
            return explode_text_fragments([("", self.text)])


class FormattedTextSource(Source):
    """
    Take any kind of prompt_toolkit formatted text as input for the pager.
    """

    def __init__(self, formatted_text: AnyFormattedText, name: str = "") -> None:
        self.formatted_text = to_formatted_text(formatted_text)
        self.name = name
        self._read = False

    def get_name(self) -> str:
        return self.name

    def eof(self) -> bool:
        return self._read

    def read_chunk(self) -> StyleAndTextTuples:
        if self._read:
            return []
        else:
            self._read = True
            return explode_text_fragments(self.formatted_text)
