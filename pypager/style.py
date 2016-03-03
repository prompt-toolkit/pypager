from __future__ import unicode_literals
from prompt_toolkit.styles.from_dict import style_from_dict
from prompt_toolkit.token import Token

__all__ = (
    'create_style',
)

def create_style():
    return style_from_dict({
        Token.Standout: 'bold #44aaff',
        Token.Standout2: 'underline #888888',
        Token.Titlebar: 'reverse',
    })
