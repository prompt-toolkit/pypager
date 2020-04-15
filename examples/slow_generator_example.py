#!/usr/bin/env python
"""
Example of a generator as source that is slow reading the input.
The UI should stay responsive while displaying the output of the generator.
"""
import time

from pypager.pager import Pager
from pypager.source import GeneratorSource


def generate_a_lot_of_content():
    counter = 0
    while True:
        yield [("", "line: %i\n" % counter)]
        counter += 1
        time.sleep(1)


if __name__ == "__main__":
    p = Pager()
    p.add_source(GeneratorSource(generate_a_lot_of_content()))
    p.run()
