.. SPDX-FileCopyrightText: Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
..
.. SPDX-License-Identifier: GPL-3.0-or-later

.. _gridtk.install:

==============
 Installation
==============

We support two installation modes, through pip_, or mamba_ (conda).


.. tab:: pip

   Stable, from PyPI:

   .. code:: sh

      pip install gridtk

   Latest beta, from GitLab package registry:

   .. code:: sh

      pip install --pre --index-url https://gitlab.idiap.ch/api/v4/groups/bob/-/packages/pypi/simple --extra-index-url https://pypi.org/simple gridtk

   .. tip::

      To avoid long command-lines you may configure pip to define the indexes and
      package search priorities as you like.


.. tab:: mamba/conda

   .. code-block:: sh

      # stable:
      $ mamba install -c https://www.idiap.ch/software/bob/conda -c conda-forge gridtk

      # latest beta:
      $ mamba install -c https://www.idiap.ch/software/bob/conda/label/beta -c conda-forge gridtk


Setup
-----

A configuration file may be useful to setup global options that should be often
reused.  The location of the configuration file depends on the value of the
environment variable ``$XDG_CONFIG_HOME``, but defaults to
``~/.config/gridtk.toml``.  You may edit this file using your preferred editor.

Here is an example configuration file that may be useful to many (replace
``<projectname>`` by the name of the project to charge):

.. code:: toml

   # selects project to submit jobs
   sge-extra-args-prepend = "-P <projectname>"


.. tip::

   To get a list of valid project names, execute:

   .. code:: sh

      qconf -sprjl


.. include:: links.rst
