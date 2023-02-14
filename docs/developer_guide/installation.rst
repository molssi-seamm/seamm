.. highlight:: shell

============
Installation
============


Stable release
--------------

To install the SEAMM module, run this command in your terminal:

.. code-block:: console

    $ conda install -c conda-forge seamm

This is the preferred method to install SEAMM, as it will always install the most recent
stable release, and also installs other dependencies, including those that are compile
code, not Python.

It can also be installed using `pip`_; however, pip cannot install all the dependencies,
so this will not work unless they are installed in another way.

.. code-block:: console

    $ pip install seamm

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

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
