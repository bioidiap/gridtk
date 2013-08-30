from setuptools import setup, find_packages

import sys

# If Python < 2.7 or 3.0 <= Python < 3.2, require some more stuff
DEPS = ['six']
if sys.version_info[:2] < (2, 7) or ((3,0) <= sys.version_info[:2] < (3,2)):
  DEPS.append('argparse')

setup(
    name='gridtk',
    version='1.0.0',
    description='SGE Grid and Local Submission and Monitoring Tools for Idiap',

    url='https://github.com/idiap/gridtk',
    license='LICENSE.txt',

    author='Manuel Guenther',
    author_email='manuel.guenther@idiap.ch',

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

    install_requires=DEPS,

    classifiers = [
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Natural Language :: English',
      'Programming Language :: Python',
      'Programming Language :: Python :: 3',
      'Topic :: System :: Clustering',
      ]
)
