#!/usr/bin/env python
"""
pypager: A pure Python pager application.
"""
from __future__ import unicode_literals
from prompt_toolkit.layout.lexers import PygmentsLexer
from pypager.pager import Pager
from pypager.source import PipeSource

import argparse
import codecs
import os
import sys

__all__ = (
    'run',
)


def run():
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

        try:
            # Open files.
            fds = []
            sources = []
            for filename in args.filename:
                f = codecs.open(filename, 'rb', encoding='utf-8', errors='ignore')
                fds.append(f)

                # When a filename is given, take a lexer from that filename.
                lexer = PygmentsLexer.from_filename(filename, sync_from_start=False)

                sources.append(PipeSource(fileno=f.fileno(), lexer=lexer))

            # Run UI.
            pager = Pager(sources, vi_mode=vi_mode)
            pager.run()
        finally:
            for f in fds:
                f.close()


if __name__ == '__main__':
    run()
