# We are nmstate!
A declarative network manager API for hosts.

[![Unit Test Status](https://travis-ci.org/nmstate/nmstate.png?branch=master)](https://travis-ci.org/nmstate/nmstate)
[![Coverage Status](https://coveralls.io/repos/github/nmstate/nmstate/badge.svg?branch=master)](https://coveralls.io/github/nmstate/nmstate?branch=master)
[![PyPI version](https://badge.fury.io/py/nmstate.svg)](https://badge.fury.io/py/nmstate)
[![Fedora Rawhide version](https://img.shields.io/badge/dynamic/json.svg?label=Fedora%20Rawhide&url=https%3A%2F%2Fapps.fedoraproject.org%2Fmdapi%2Frawhide%2Fpkg%2Fnmstate&query=%24.version&colorB=blue)](https://apps.fedoraproject.org/packages/nmstate)

Copr build status:
* EPEL 7 GIT master: [![EPEL7 GIT master Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-el7/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-el7/package/nmstate/)
* Fedora GIT master: [![Fedora GIT master Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-fedora/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-fedora/package/nmstate/)

## What is it?
NMState is a library with an accompanying command line tool that manages
host networking settings in a declarative manner.
The networking state is described by a pre-defined schema.
Reporting of current state and changes to it (desired state) both conform to
the schema.

NMState is aimed to satisfy enterprise needs to manage host networking through
a northbound declarative API and multi provider support on the southbound.
NetworkManager acts as the main (and currently the only) provider supported.

## Contact
*nmstate* uses the [NetworkManager mailing
list](https://mail.gnome.org/mailman/listinfo/networkmanager-list)
([Archives](https://mail.gnome.org/archives/networkmanager-list/)) for
discussions. Emails about nmstate should be tagged with `[nmstate]` in the
subject header to ease filtering.

Development planning (sprints and progress reporting) happens in
([Jira](https://nmstate.atlassian.net)). Access requires login.

There is also `#nmstate` on [Freenode
IRC](https://freenode.net/kb/answer/chat).

## Development Environment

nmstate uses `tox` to run unit tests and linters. Since nmstate uses the binary
module PyGObject it also requires the build dependencies for it.

### RHEL 7.6

Recommended minimum installation:
```shell
yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm  # install EPEL for python-pip
subscription-manager repos --enable "rhel-*-optional-rpms" --enable "rhel-*-extras-rpms"  # recommended for EPEL
yum install git python-pip
pip install tox  # python-tox in EPEL seems to be too old
yum-builddep python-gobject  # install build dependencies for PyGObject
```

Note: This will not run the unit tests for Python 3.6 because this Python version is not available there.

### Unit tests
Run Unit Tests:
```shell
tox
```

## Runtime Environment

Install (from sources) system-wide:
```shell
sudo pip install --upgrade .
```

Install just for the local user:

```shell
pip install --user --upgrade .
```

Make sure that `~/.local/bin` is in your PATH when installing as a local user.
The `export` command can be used to add it for the current session:

```shell
export PATH="${HOME}/.local/bin:${PATH}"
```


## Basic Operations

Show current state:
```shell
nmstatectl show
```

Change to desired state:
```shell
nmstatectl set desired-state.json
```

Edit current state of eth3 in a text editor:
```shell
nmstatectl edit --only eth3
```


`nmstatectl` will also read from stdin when no file is specified:


```shell
nmstatectl set < desired-state.json
```

Desired/Current state example:
```shell
{
    "interfaces": [
        {
            "description": "Production Network",
            "ethernet": {
                "auto-negotiation": true,
                "duplex": "full",
                "speed": 1000
            },
            "ipv4": {
                "address": [
                    {
                        "ip": "192.0.2.142",
                        "prefix-length": 24
                    }
                ],
                "enabled": true
            },
            "mtu": 1500,
            "name": "eth3",
            "state": "up",
            "type": "ethernet"
        }
    ]
}
```

The state is also supported as YAML, to get the current state in YAML format:

```shell
nmstatectl show --yaml
```

The `set` command accepts both YAML and JSON.

## Supported Interfaces:
- bond
- dummy
- ethernet
- ovs-bridge
