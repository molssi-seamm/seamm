.. highlight:: shell

============
Installation
============


Stable release
--------------

To install the SEAMM module, run this command in your terminal:

.. code-block:: console

    $ pip install seamm

This installs the most recent stable release and every dependency, including the
compiled ones (RDKit and Open Babel, via molsystem), from their PyPI wheels. The one
thing pip cannot supply is the Python interpreter itself with ``tkinter``, which the
graphical editor needs; use a Python from python.org, uv, or conda-forge. A
conda-forge ``seamm`` package also exists but lags the PyPI release, and the two
should not be mixed in one environment.

For a complete SEAMM installation, with all the plug-ins and the external codes they
drive, use the `SEAMM installer`_ rather than installing packages by hand.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _SEAMM installer: https://molssi-seamm.github.io/installation/index.html
.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for the SEAMM module can be downloaded
from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/molssi-seamm/seamm

Or download the `tarball`_:

.. code-block:: console

    $ curl  -OL https://github.com/molssi-seamm/seamm/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ python setup.py install


.. _Github repo: https://github.com/molssi-seamm/seamm
.. _tarball: https://github.com/molssi-seamm/seamm/tarball/master
