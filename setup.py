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
    'logging',
    'molssi_util',
    'numpy',
    'pandas',
    'pint',
    'pprint',
    'pyuca',
    'stevedore',
]
# 'PIL', --> pillow
# 'abc',
# 'collections.abc',
# 'copy',
# 'glob',
# 'grp',
# 'json',
# 'locale',
# 'math',
# 'os',
# 'os.path',
# 'pkg_resources',
# 'platform',
# 'pwd',
# 'shutil',
# 'stat',
# 'subprocess',
# 'sys',
# 'tempfile',
# 'time',
# 'uuid',
# 'weakref',

setup_requirements = [
    'pytest-runner',
    # TODO(paulsaxe): put setup requirements (distutils extensions, etc.) here
]

test_requirements = [
    'pytest',
    # TODO: put package test requirements here
]

setup(
    name='molssi_workflow',
    version='0.1.0',
    description="The MolSSI workflow for computational molecular and materials science (CMS)",
    long_description=readme + '\n\n' + history,
    author="Paul Saxe",
    author_email='psaxe@molssi.org',
    url='https://github.com/paulsaxe/molssi_workflow',
    packages=find_packages(include=['molssi_workflow']),
    entry_points={
        'console_scripts': [
            'molssi_workflow=molssi_workflow.__main__:flowchart',
            'run_workflow=molssi_workflow.run_workflow:run'
        ],
        'org.molssi.workflow': [
            'Split = molssi_workflow:SplitStep',
        ],
        'org.molssi.workflow.tk': [
            'Split = molssi_workflow:SplitStep',
        ],
        'org.molssi.workflow': [
            'Join = molssi_workflow:JoinStep',
        ],
        'org.molssi.workflow.tk': [
            'Join = molssi_workflow:JoinStep',
        ],
    },
    include_package_data=True,
    install_requires=requirements,
    license="GNU Lesser General Public License v3",
    zip_safe=False,
    keywords='molssi_workflow',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
)
