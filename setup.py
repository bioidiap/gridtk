from setuptools import setup, find_packages

import sys

version = open("version.txt").read().rstrip()
requirements = [k.strip() for k in open("requirements.txt").read().split()]

setup(
    name='gridtk',
    version=version,
    description='Parallel Job Manager',
    long_description=open('README.rst').read(),
    url='https://gitlab.idiap.ch/bob/gridtk',
    license='GPLv3',

    author='Manuel Guenther,Andre Anjos',
    author_email='manuel.guenther@idiap.ch,andre.anjos@idiap.ch',

    packages=find_packages(),
    include_package_data=True,

    install_requires=requirements,

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
