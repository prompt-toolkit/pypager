from __future__ import unicode_literals
from prompt_toolkit.styles.from_pygments import style_from_pygments
from prompt_toolkit.token import Token
from prompt_toolkit.styles import Attrs, Style

__all__ = (
    'create_style',
)


def create_style():
    return PypagerStyle()


ui_style = {
    # Standout is caused by man pages that insert a x\b in the output.
    Token.Standout: 'bold #44aaff',
    Token.Standout2: 'underline #aa8844',

    # UI style
    Token.Titlebar: 'bg:#333333 #aaaaaa',
    Token.Titlebar.CursorPosition: 'bold #ffffff',

    Token.Arg: 'reverse #ccaa00',

    Token.Toolbar.Search: 'bg:#333333 #ffffff',
    Token.Toolbar.Search.Text: '#ffffff',
    Token.Toolbar.System: 'bg:#333333 #ffffff',
    Token.Toolbar.System.Text: '#ffffff',

    Token.Toolbar.Examine: 'bg:#333333 #ffffff',
    Token.Toolbar.Examine.Text: 'bg:#aa88ff #000000',

    # Messages
    Token.Message:                'bg:#bbee88 #222222',
}


class PypagerStyle(Style):
    """
    The styling.

    Like for pymux, all tokens starting with a ('C',) are interpreted as tokens
    that describe their own style.
    """
    # NOTE: (Actually: this is taken literally from pymux.)
    def __init__(self):
        self.ui_style = style_from_pygments(style_dict=ui_style)

    def get_attrs_for_token(self, token):
        if token and token[0] == 'C':
            # Token starts with ('C',). Token describes its own style.
            c, fg, bg, bold, underline, italic, blink, reverse = token
            return Attrs(fg, bg, bold, underline, italic, blink, reverse)
        else:
            # Take styles from UI style.
            return self.ui_style.get_attrs_for_token(token)

    def invalidation_hash(self):
        return None
