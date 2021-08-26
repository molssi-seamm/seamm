.. highlight:: shell

============
Installation
============

Some of the requirements to run the SEAMM framework cannot be automatically installed
using e.g. pip but can be using Conda Forge. Please use the `SEAMM installer`_ to
install this module and the other core modules that comprise SEAMM.

.. _SEAMM installer: https://molssi-seamm.github.io/users/installation/index.html


From sources
------------

The sources for SEAMM can be downloaded from the `Github repo`_.

You can either clone the public repository::

    $ git clone git://github.com/molssi-seamm/seamm

Or download the `tarball`_::

    $ curl  -OL https://github.com/molssi-seamm/seamm/tarball/master

Once you have a copy of the source, you can install it with::

    $ python setup.py install

or more simply::

    $ make install

`make` or `make help` will provide a list of all the targets.::

    $ make
    make
    clean                remove all build, test, coverage and Python artifacts
    clean-build          remove build artifacts
    clean-pyc            remove Python file artifacts
    clean-test           remove test and coverage artifacts
    lint                 check style with black and flake8
    format               reformat with with yapf and isort
    typing               check typing
    test                 run tests quickly with the default Python
    test-all             run tests on every Python version with tox
    coverage             check code coverage quickly with the default Python
    docs                 generate Sphinx HTML documentation, including API docs
    servedocs            compile the docs watching for changes
    release              package and upload a release
    dist                 builds source and wheel package
    install              install the package to the active Python's site-packages
    uninstall            uninstall the package
    $

Typically it is a good
idea to check the formatting of your changes using `black` and `flake8` which is what the
`lint` target does, e.g.::

    $ make lint install

.. _Github repo: https://github.com/molssi-seamm/seamm
.. _tarball: https://github.com/molssi-seamm/seamm/tarball/master
