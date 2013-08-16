from setuptools import setup, find_packages

import sys

# If Python < 2.7 or 3.0 <= Python < 3.2, require some more stuff
ARGPARSE = []
if sys.version_info[:2] < (2, 7) or ((3,0) <= sys.version_info[:2] < (3,2)):
  ARGPARSE.append('argparse')

setup(
    name='gridtk',
    version='1.0.0.a0',
    description='SGE Grid Submission and Monitoring Tools for Idiap',

    url='https://github.com/idiap/gridtk',
    license='LICENSE.txt',

    author='Andre Anjos',
    author_email='andre.anjos@idiap.ch',

    packages=find_packages(),

    entry_points={
      'console_scripts': [
        'jman = gridtk.script.jman:main',
        'grid = gridtk.script.grid:main',

        # program replacements
        'qstat.py = gridtk.script.grid:main',
        'qdel.py = gridtk.script.grid:main',
        'qsub.py = gridtk.script.grid:main',
        'man.py = gridtk.script.grid:main',
      ],

      'bob.test' : [
        'gridtk = gridtk.tests:GridTKTest',
      ],

    },

    long_description=open('README.rst').read(),

    install_requires=ARGPARSE,

    classifiers = [
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Natural Language :: English',
      'Programming Language :: Python',
      'Topic :: System :: Clustering',
      ]
)
