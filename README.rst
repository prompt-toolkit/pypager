pypager
=======

*A PAGER in pure Python*

::

    pip install pypager

Pypager can be used as a stand-alone application, or as a library.


What is a pager?
----------------

A pager is a terminal program that can be used to view the content of a file,
or the output stream from another application.

For instance, when we run ``man vim``, the actual content is displayed in a
pager, according to the ``$PAGER`` environment variable.

Important for a pager is that the input can be streamed. For instance when we
have ``find / | pypager``; we don't want to wait for the whole file system to
be traversed, before displaying anything. Data is only read from the input
pipe, when it needs to be displayed.

Popular pager applications are ``more``, ``less`` and ``most``.


Features
--------

- Highlighting of text [0].
- Searching.
- Many key bindings from ``less`` are implemented.

[0] (It understands the output of man pages, ANSI escape codes and further, it
can use Pygments to highlight about any file.)


Usage
-----

.. code:: sh

    # Install it.
    pip install pypager

    # Tell the environment to use this pager. Put the following line in
    # ~/.bashrc if you like.
    export PAGER=pypager

    # Following commands, and many others should pick up the pager.
    man vim
    git diff

    # View a file, using this pager.
    pypager some_source_code.py


As a library
------------

.. code:: python

    from pypager.source import GeneratorSource
    from pypager.pager import Pager
    from prompt_toolkit.token import Token
    
    
    def generate_a_lot_of_content():
        """
        This is a function that generates content on the fly.
        It's called when the pager needs to display more content.
        """
        counter = 0
        while True:
            yield [(Token, 'line: %i\n' % counter)]
            counter += 1
    
    
    if __name__ == '__main__':
        source = GeneratorSource(generate_a_lot_of_content())
        p = Pager(source)
        p.run()

