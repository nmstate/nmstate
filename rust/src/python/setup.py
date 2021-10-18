import setuptools

setuptools.setup(
    name="libnmstate",
    version="2.0.0",
    author="Gris Ge",
    author_email="fge@redhat.com",
    description="Python binding of nmstate",
    long_description="Python binding of nmstate",
    url="https://github.com/nmstate/nmstate/",
    packages=setuptools.find_packages(),
    license="ASL2.0+",
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: Linux",
    ],
)
