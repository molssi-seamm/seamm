#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'pillow',
    'Pmw',
    'argparse',
    'bitmath',
    'datetime',
    'seamm_util',
    'numpy',
    'pandas',
    'pint',
    'pprint',
    'pyuca',
    'stevedore',
]

setup_requirements = [
    'pytest-runner',
    # TODO(paulsaxe): put setup requirements (distutils extensions, etc.) here
]

test_requirements = [
    'pytest',
    # TODO: put package test requirements here
]

setup(
    name='seamm',
    version='0.1.0',
    description="Simulation Environment for Atomistic and Molecular Modeling ",
    long_description=readme + '\n\n' + history,
    author="Paul Saxe",
    author_email='psaxe@molssi.org',
    url='https://github.com/molssi-seamm/seamm',
    packages=find_packages(include=['seamm']),
    entry_points={
        'console_scripts': [
            'seamm=seamm.__main__:flowchart',
            'run_flowchart=seamm.run_flowchart:run'
        ],
        'org.molssi.seamm': [
            'Split = seamm:SplitStep',
        ],
        'org.molssi.seamm.tk': [
            'Split = seamm:SplitStep',
        ],
        'org.molssi.seamm': [
            'Join = seamm:JoinStep',
        ],
        'org.molssi.seamm.tk': [
            'Join = seamm:JoinStep',
        ],
    },
    include_package_data=True,
    install_requires=requirements,
    license="GNU Lesser General Public License v3",
    zip_safe=False,
    keywords='seamm',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
)
