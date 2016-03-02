#!/usr/bin/env python
"""
Pager implementation in Python.

Example usage, type in your bash shell::

    export PAGER=./pypager.py
    man man
"""
import sys
import re

#from prompt_toolkit.keys import Keys
#from prompt_toolkit.layout.toolbars import TokenListToolbar
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.enums import DEFAULT_BUFFER
from prompt_toolkit.input import StdinInput
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, TokenListControl
from prompt_toolkit.layout.dimension import LayoutDimension as D
from prompt_toolkit.layout.processors import Processor, Transformation, HighlightSelectionProcessor, HighlightSearchProcessor, HighlightMatchingBracketProcessor, TabsProcessor, Transformation
from prompt_toolkit.layout.screen import Char
from prompt_toolkit.layout.toolbars import SystemToolbar, SearchToolbar
from prompt_toolkit.shortcuts import create_eventloop
from prompt_toolkit.styles.from_dict import style_from_dict
from prompt_toolkit.token import Token


def get_titlebar_tokens(cli):
    return [
        (Token.Titlebar, 'pypager')
    ]


class EscapeProcessor(Processor):
    def apply_transformation(self, cli, document, lineno, source_to_display, tokens):
        tokens = line_tokens[lineno]
        return Transformation(tokens[:])


input_processors = [
    EscapeProcessor(),
    TabsProcessor(),
    HighlightSelectionProcessor(),
    HighlightSearchProcessor(preview_search=True),
    HighlightMatchingBracketProcessor(),
]


# Build an interface.
layout = HSplit([
    Window(content=BufferControl(buffer_name=DEFAULT_BUFFER, input_processors=input_processors)),
    SystemToolbar(),
    SearchToolbar(vi_mode=True),
    Window(height=D.exact(1),
           content=TokenListControl(
               get_titlebar_tokens, align_center=True,
               default_char=Char(' ', Token.Titlebar))),
])

# Key bindings.
manager = KeyBindingManager(
    enable_vi_mode=False,#True,
    enable_search=True,
    enable_extra_page_navigation=True,
    enable_system_bindings=True)

@manager.registry.add_binding('q', eager=True)
def _(event):
    " Quit. "
    event.cli.set_return_value(None)


@manager.registry.add_binding(' ', eager=True)
def _(event):
    " Page down."
    scroll_page_down(event)


style = style_from_dict({
    Token.Standout: 'bold #44aaff',
    Token.Standout2: 'underline #888888',# #aaaaff',
    Token.Titlebar: 'reverse',
})


buffers = {
    DEFAULT_BUFFER: Buffer(is_multiline=True, read_only=True),
}


application = Application(
    layout=layout,
    buffers=buffers,
    key_bindings_registry=manager.registry,
    style=style,
    mouse_support=True,
    use_alternate_screen=True)


line_tokens = [[]]  # List of lines. (Each line is a list of (token, text) tuples itself.)
text = []


def run():
    eventloop = create_eventloop()

    def parse_corot():
        token = Token

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

    parser = parse_corot()
    next(parser)

    def content_received():
        """
        Content is ready on stdin.
        """
        b = buffers[DEFAULT_BUFFER]
        data = sys.stdin.read()

        for c in data:
            parser.send(c)

        data = re.sub('.\b', '', data)

        document = Document(b.text + data, b.cursor_position)
        b.set_document(document, bypass_readonly=True)
        cli.invalidate()

    def pre_run():
        # Add reader for stdin.
        eventloop.add_reader(sys.stdin.fileno(), content_received)

    try:
        # Create a `CommandLineInterface` instance. This is a wrapper around
        # `Application`, but includes all I/O: eventloops, terminal input and output.
        cli = CommandLineInterface(
            application=application,
            eventloop=eventloop,
            input=StdinInput(sys.stdout))

        # Run the interface. (This runs the event loop until Ctrl-Q is pressed.)
        cli.run(reset_current_buffer=False, pre_run=pre_run)
    finally:
        # Clean up. An eventloop creates a posix pipe. This is used internally
        # for scheduling callables, created in other threads into the main
        # eventloop. Calling `close` will close this pipe.
        eventloop.close()

if __name__ == '__main__':
    run()

