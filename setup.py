import sys

from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


def requirements():
    req = []
    with open('requirements.txt') as f:
        for l in f:
            l.strip()
            # workaround for old setuptools in CentOS/RHEL 7
            if l == 'ipaddress;python_version<"3.3"':
                if sys.version_info < (3, 3):
                    req.append('ipaddress')
                    continue
            if not l.startswith('#'):
                req.append(l)
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
