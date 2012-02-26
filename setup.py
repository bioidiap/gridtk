from setuptools import setup, find_packages

setup(
    name='gridtk',
    version='0.1',
    description='SGE Grid Submission and Monitoring Tools for Idiap',

    #url='http://pypi.python.org/pypi/TowelStuff/',
    license='LICENSE.txt',

    author='Andre Anjos',
    author_email='andre.anjos@idiap.ch',

    packages=find_packages(),

    entry_points={
      'console_scripts': [
        'jman = gridtk.scripts.jman:main',
        'grid = gridtk.scripts.grid:main',
        ]
      },

    long_description=open('docs/manual.rst').read(),

    install_requires=[
        "argparse", #any version will do
    ],
)