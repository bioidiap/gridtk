from setuptools import setup, find_packages

import sys

# If Python < 2.7 or 3.0 <= Python < 3.2, require some more stuff
DEPS = ['six']
if sys.version_info[:2] < (2, 7) or ((3,0) <= sys.version_info[:2] < (3,2)):
  DEPS.append('argparse')

version = open("version.txt").read().rstrip()

setup(
    name='gridtk',
    version=version,
    description='SGE Grid and Local Submission and Monitoring Tools for Idiap',

    url='http://github.com/idiap/gridtk',
    license='GPLv3',

    author='Manuel Guenther',
    author_email='manuel.guenther@idiap.ch',

    packages=find_packages(),
    include_package_data=True,

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
