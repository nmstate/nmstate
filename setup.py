from setuptools import setup, find_packages
from datetime import date


def readme():
    with open("README.md") as f:
        return f.read()


def requirements():
    req = []
    with open("requirements.txt") as fd:
        for line in fd:
            line.strip()
            if not line.startswith("#"):
                req.append(line)
    return req


def get_version():
    with open("libnmstate/VERSION") as f:
        version = f.read().strip()
    return version


def gen_manpage():
    nmstatectl_manpage = ""
    autoconf_manpage = ""
    with open("doc/nmstatectl.8.in") as f:
        nmstatectl_manpage = f.read()
    with open("doc/nmstate-autoconf.8.in") as f:
        autoconf_manpage = f.read()
    nmstatectl_manpage = nmstatectl_manpage.replace(
        "@DATE@", date.today().strftime("%B %d, %Y")
    )
    nmstatectl_manpage = nmstatectl_manpage.replace("@VERSION@", get_version())
    autoconf_manpage = autoconf_manpage.replace(
        "@DATE@", date.today().strftime("%B %d, %Y")
    )
    autoconf_manpage = autoconf_manpage.replace("@VERSION@", get_version())

    with open("doc/nmstatectl.8", "w") as f:
        f.write(nmstatectl_manpage)
    with open("doc/nmstate-autoconf.8", "w") as f:
        f.write(autoconf_manpage)
    return [("share/man/man8", ["doc/nmstatectl.8", "doc/nmstate-autoconf.8"])]


setup(
    name="nmstate",
    version=get_version(),
    description="Declarative network manager API",
    author="Edward Haas",
    author_email="ehaas@redhat.com",
    long_description=readme(),
    long_description_content_type="text/markdown",
    url="https://nmstate.github.io/",
    license="LGPL2.1+",
    packages=find_packages(),
    install_requires=requirements(),
    entry_points={
        "console_scripts": {
            "nmstatectl = nmstatectl.nmstatectl:main",
            "nmstate-autoconf = nmstatectl.nmstate_autoconf:main",
        }
    },
    package_data={
        "libnmstate": ["VERSION"],
    },
    data_files=gen_manpage(),
)
