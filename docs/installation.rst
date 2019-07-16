.. highlight:: shell

============
Installation
============

Environment
-----------

Some of the requirements to run the SEAMM framework cannot be automatically installed using e.g. pip. A couple
require a conda environment, so at the moment you will need to install either the `Anaconda`_ or `conda`_ Python
environment from Continuum IO. The first dependency to install manually is RDKit. You can follow the `RDKit
documentation`_ to install Anaconda, etc. but if you already have Anaconda/Conda installed you can simply do the
following

.. code-block:: console

   $ conda create -c rdkit -n <env_name> python=3.6.1 rdkit

where you need to replace '<env_name>' with an environment name that you remember, like 'molssi'. Once you have
installed RDKit, activate the environment:

.. code-block:: console

   $ source activate <env_name>

You also need to install Open Babel. Please consulte the `Open Babel documentation`_ for how to install on your operating
system. The easiest way is to use conda:

.. code-block:: console

   $ conda install -c openbabel openbabel


.. _Anaconda: https://docs.anaconda.com/anaconda/install/
.. _conda: https://conda.io/miniconda.html   
.. _RDkit documentation: http://rdkit.org/docs/Install.html#how-to-install-rdkit-with-conda
.. _Open Babel documentation: http://openbabel.org/wiki/Category:Installation


Stable release
--------------

To install SEAMM, run this command in your terminal:

.. code-block:: console

    $ pip install seamm

This is the preferred method to install SEAMM, as it will always install the most recent stable release. 

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for SEAMM can be downloaded from the `Github repo`_.

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
