import setuptools


def requirements():
    req = []
    with open("requirements.txt") as fd:
        for line in fd:
            line.strip()
            if not line.startswith("#"):
                req.append(line)
    return req


setuptools.setup(
    name="nmstate",
    version="2.1.5",
    author="Gris Ge",
    author_email="fge@redhat.com",
    description="Python binding of nmstate",
    long_description="Python binding of nmstate",
    url="https://github.com/nmstate/nmstate/",
    packages=setuptools.find_packages(),
    install_requires=requirements(),
    license="ASL2.0+",
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
)
