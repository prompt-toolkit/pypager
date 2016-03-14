#!/usr/bin/env python
"""
pypager: A pure Python pager application.
"""
from __future__ import unicode_literals
from prompt_toolkit.layout.lexers import PygmentsLexer
from pypager.pager import Pager
from pypager.source import PipeSource
import sys
import argparse
import codecs

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
        args = parser.parse_args()

        with codecs.open(args.filename, 'rb', encoding='utf-8', errors='ignore') as f:
            # When a filename is given, take a lexer from that filename.
            lexer = PygmentsLexer.from_filename(args.filename, sync_from_start=False)

            pager = Pager(PipeSource(fileno=f.fileno()), lexer=lexer)
            pager.run()


if __name__ == '__main__':
    run()
