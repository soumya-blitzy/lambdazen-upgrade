from setuptools import setup

setup(name='lambdazen',
      version='0.1.7',
      description='Syntax changes for python lambdas.',
      url='http://github.com/brthornbury/lambdazen',
      author='Bryan Thornbury',
      author_email='author@example.com',
      license='MIT',
      packages=['lambdazen'],
      zip_safe=False,

      # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
            # Python 3.6+ compatibility - updated for lambdazen upgrade
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
            'Programming Language :: Python :: 3.11',
            'Programming Language :: Python :: 3.12',
            'Programming Language :: Python :: 3.13',
      ])