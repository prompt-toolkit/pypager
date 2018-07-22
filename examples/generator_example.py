#!/usr/bin/env python
from __future__ import unicode_literals
from pypager.source import GeneratorSource
from pypager.pager import Pager


def generate_a_lot_of_content():
    counter = 0
    while True:
        yield [('', 'line: %i\n' % counter)]
        counter += 1


if __name__ == '__main__':
    p = Pager()
    p.add_source(GeneratorSource(generate_a_lot_of_content()))
    p.run()
