import logging
import setuptools
from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


def _is_outdated_setuptools():
    """
    Return True if setuptool is older than 20.5 which introduced environment
    markers for requirements:
        https://www.python.org/dev/peps/pep-0508/#environment-markers
    """
    major, minor = setuptools.__version__.split('.')[:2]
    return (int(major), int(minor)) < (20, 5)


def requirements():
    req = []
    setuptools_is_outdated = _is_outdated_setuptools()
    with open('requirements.txt') as fd:
        for line in fd:
            line.strip()
            if setuptools_is_outdated:
                if ';' in line:
                    # Remove the environment marker
                    logging.warning(
                        "Your setuptools is too old(<20.5) to support "
                        "environment marker, removing the environment marker "
                        "as workaround but it could be buggy")
                    line = line.split(';')[0]
            if not line.startswith('#'):
                req.append(line)
    return req


def get_version():
    with open('VERSION') as f:
        version = f.read().strip()
    return version


setup(
    name='nmstate',
    version=get_version(),
    description='Declarative network manager API',
    author="Edward Haas",
    author_email="ehaas@redhat.com",
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://nmstate.github.io/',
    license='GPLv2+',
    packages=find_packages(),
    install_requires=requirements(),
    entry_points={
        'console_scripts': ['nmstatectl = nmstatectl.nmstatectl:main'],
    },
    package_data={
        'libnmstate': ['schemas/operational-state.yaml']
    },
)
