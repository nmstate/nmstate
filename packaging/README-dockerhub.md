## Docker Hub

The images are automatically rebuilt on new GIT tags or pushes to the base branch:

`Dockerfile.fedora-nmstate-dev` by https://cloud.docker.com/u/nmstate/repository/docker/nmstate/fedora-nmstate-dev

The base image contains a common base that is used both for the development
image and for the distributed image.

Configuration (here for `fedora-nmstate-dev`, the other build just specifies
a different container spec (Dockerfile location):

Source repo: nmstate/nmstate
Autotest: Off
Repository Links: Off
Build rules:
Branch:
Source:base
Docker Tag:latest
Dockerfile location:Dockerfile.fedora-nmstate-dev
Build Context:/packaging
Autobuild:on
Build Caching:off

Tag:
Source: /^v[0-9.]+$/
Docker Tag:{sourceref}
Dockerfile location:Dockerfile.fedora-nmstate-dev
Build Context:/packaging
Autobuild:on
Build Caching:off

## Manual Building

The Nmstate user image builds the base branch by default. To specify a
different commit or tag, specify the `SOURCE_COMMIT` build argument:

```shell
./build-container.sh --extra-args "--build-arg SOURCE_COMMIT=v0.0.6" nmstate/fedora-nmstate-dev

```
