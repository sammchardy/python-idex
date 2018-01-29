#!/usr/bin/env python
from setuptools import setup

setup(
    name='python-idex',
    version='0.2.6',
    packages=['idex'],
    description='IDEX REST API python implementation',
    url='https://github.com/sammchardy/python-idex',
    author='Sam McHardy',
    license='MIT',
    author_email='',
    install_requires=['requests', 'ethereum'],
    keywords='idex exchange rest api ethereum eth eos',
    classifiers=[
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
