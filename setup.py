#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seamm
The core of the SEAMM environment and graphical interface.
"""

import sys
from setuptools import setup, find_packages
import versioneer

short_description = __doc__.split("\n")

# from https://github.com/pytest-dev/pytest-runner#conditional-requirement
needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

with open('requirements.txt') as fd:
    requirements = fd.read()

setup(
    name='seamm',
    author="Paul Saxe",
    author_email='psaxe@molssi.org',
    description=short_description[1],
    long_description=readme + '\n\n' + history,
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license="GNU Lesser General Public License v3",
    url='https://github.com/molssi-seamm/seamm',

    # Which Python importable modules should be included when your package is
    # installed, handled automatically by setuptools. Use 'exclude' to prevent
    # some specific subpackage(s) from being added, if needed
    packages=find_packages(include=['seamm']),

    # Optional include package data to ship with your package. Customize
    # MANIFEST.in if the general case does not suit your needs. Comment out
    # this line to prevent the files from being packaged with your software
    include_package_data=True,

    # Allows `setup.py test` to work correctly with pytest
    setup_requires=[] + pytest_runner,

    # Required packages, pulls from pip if needed; do not use for Conda
    # deployment
    install_requires=requirements,

    test_suite='tests',

    # Valid platforms your code works on, adjust to your flavor
    platforms=['Linux',
               'Mac OS-X',
               'Unix',
               'Windows'],

    # Manual control if final package is compressible or not, set False to
    # prevent the .egg from being made
    # zip_safe=False,

    keywords='seamm',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Chemistry',
        'Topic :: Scientific/Engineering :: Physics',
        ('License :: OSI Approved :: GNU Lesser General Public License v3 or '
         'later (LGPLv3+)'),
        'Natural Language :: English',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    entry_points={
        'console_scripts': [
            'seamm=seamm.__main__:flowchart',
            'run_flowchart=seamm.run_flowchart:run'
        ],
        'org.molssi.seamm': [
            'Join = seamm:JoinStep',
            'Split = seamm:SplitStep',
        ],
        'org.molssi.seamm.tk': [
            'Join = seamm:JoinStep',
            'Split = seamm:SplitStep',
        ],
    }
)
