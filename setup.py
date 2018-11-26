from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


def requirements():
    req = []
    with open('requirements.txt') as f:
        for l in f:
            l.strip()
            if not l.startswith('#'):
                req.append(l)
    return req


setup(
    name='nmstate',
    version='0.0.2',
    description='Declarative network manager API',
    author="Edward Haas",
    author_email="ehaas@redhat.com",
    long_description=readme(),
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
