#!/usr/bin/env python
import os

from setuptools import find_packages, setup

import pypager

with open(os.path.join(os.path.dirname(__file__), "README.rst")) as f:
    long_description = f.read()

install_requires = [
    "prompt_toolkit>=3.0.0,<3.1.0",
    "pygments",
]

setup(
    name="pypager",
    author="Jonathan Slenders",
    version=pypager.__version__,
    license="LICENSE",
    url="https://github.com/jonathanslenders/pypager",
    description='Pure Python pager (like "more" and "less").',
    long_description=long_description,
    packages=find_packages("."),
    python_requires=">=3.6",
    install_requires=install_requires,
    entry_points={
        "console_scripts": ["pypager = pypager.entry_points.run_pypager:run",]
    },
)
