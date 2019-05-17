#!/usr/bin/env python
"""
pypager: A pure Python pager application.
"""
from __future__ import unicode_literals
from prompt_toolkit.lexers import PygmentsLexer
from pypager.pager import Pager
from pypager.source import FileSource
from prompt_toolkit.utils import is_windows
from prompt_toolkit import __version__ as ptk_version

import argparse
import os
import sys

PTK3 = ptk_version.startswith('3.')

if not PTK3:
    from prompt_toolkit.eventloop.defaults import set_event_loop

__all__ = (
    'run',
)


def run():
    if not PTK3:
        if is_windows():
            from prompt_toolkit.eventloop.win32 import Win32EventLoop
            loop = Win32EventLoop()
        else:
            from prompt_toolkit.eventloop.posix import PosixEventLoop
            from prompt_toolkit.eventloop.select import SelectSelector
            loop = PosixEventLoop(selector=SelectSelector)
        set_event_loop(loop)

    if not sys.stdin.isatty():
        pager = Pager.from_pipe()
        pager.run()
    else:
        parser = argparse.ArgumentParser(description='Browse through a text file.')
        parser.add_argument('filename', metavar='filename', nargs='+',
                            help='The file to be displayed.')
        parser.add_argument('--vi', help='Prefer Vi key bindings.', action='store_true')
        parser.add_argument('--emacs', help='Prefer Emacs key bindings.', action='store_true')

        args = parser.parse_args()

        # Determine input mode.
        vi_mode = 'vi' in os.environ.get('EDITOR', '').lower()
        if args.vi: vi_mode = True
        if args.emacs: vi_mode = False

        pager = Pager(vi_mode=vi_mode)

        # Open files.
        for filename in args.filename:
            # When a filename is given, take a lexer from that filename.
            lexer = PygmentsLexer.from_filename(filename, sync_from_start=False)

            pager.add_source(FileSource(filename, lexer=lexer))

        # Run UI.
        pager.run()


if __name__ == '__main__':
    run()
