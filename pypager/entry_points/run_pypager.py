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
        parser.add_argument('filename', metavar='filename', #args='+',
                            help='The file to be displayed.')
        parser.add_argument('--vi', help='Prefer Vi key bindings.', action='store_true')
        parser.add_argument('--emacs', help='Prefer Emacs key bindings.', action='store_true')

        args = parser.parse_args()

        # Determine input mode.
        vi_mode = 'vi' in os.environ.get('EDITOR', '').lower()
        if args.vi: vi_mode = True
        if args.emacs: vi_mode = False

        with codecs.open(args.filename, 'rb', encoding='utf-8', errors='ignore') as f:
            # When a filename is given, take a lexer from that filename.
            lexer = PygmentsLexer.from_filename(args.filename, sync_from_start=False)

            pager = Pager(PipeSource(fileno=f.fileno()), lexer=lexer, vi_mode=vi_mode)
            pager.run()


if __name__ == '__main__':
    run()
