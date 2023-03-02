.. SPDX-FileCopyrightText: Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
..
.. SPDX-License-Identifier: GPL-3.0-or-later

.. _gridtk.install:

==============
 Installation
==============

We support two installation modes, through pip_, or mamba_ (conda).


.. tab:: pip/stable

   .. code:: sh

      pip install gridtk


.. tab:: pip/beta

   .. code:: sh

      pip install git+https://gitlab.idiap.ch/software/gridtk


.. tab:: conda/stable

   .. code:: sh

      mamba install -c conda-forge gridtk


.. tab:: conda/beta

   .. code:: sh

      mamba install -c https://www.idiap.ch/software/biosignal/conda/label/beta -c conda-forge gridtk


.. _gridtk.config:

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
