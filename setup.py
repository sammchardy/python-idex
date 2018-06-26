#!/usr/bin/env python
import sys
from setuptools import setup

def install_requires():

    requires = ['requests', 'coincurve>=7.0.0', 'py_ecc', 'pycryptodome>=3.5.1,<4']
    if sys.version_info < (3, 3):
        requires.extend(['rlp==0.4.7'])
    else:
        requires.extend(['rlp>=1.0.0,<2.0.0', 'websockets>=4.0.0', 'aiohttp>=2.3.0'])


setup(
    name='python-idex',
    version='0.2.7',
    packages=['idex'],
    description='IDEX REST API python implementation',
    url='https://github.com/sammchardy/python-idex',
    author='Sam McHardy',
    license='MIT',
    author_email='',
    install_requires=install_requires(),
    keywords='idex exchange rest api ethereum eth eos',
    classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
