#!/usr/bin/env python
import os
from setuptools import setup, find_packages

long_description = open(
    os.path.join(
        os.path.dirname(__file__),
        'README.rst'
    )
).read()

install_requires = [
    'prompt_toolkit>=1.0.0,<1.1.0',
    'pygments',
]

# Argparse became part of the standard library in Python 2.7
# Include for older versions.
try:
    import argparse
except ImportError:
    install_requires += ['argparse']

setup(
    name='pypager',
    author='Jonathan Slenders',
    version='0.2',
    license='LICENSE',
    url='https://github.com/jonathanslenders/pypager',
    description='Pure Python pager (like "more" and "less").',
    long_description=long_description,
    packages=find_packages('.'),
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'pypager = pypager.entry_points.run_pypager:run',
        ]
    },
)
