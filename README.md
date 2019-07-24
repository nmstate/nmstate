# We are Nmstate!
A declarative network manager API for hosts.

[![Unit Test Status](https://travis-ci.org/nmstate/nmstate.png?branch=master)](https://travis-ci.org/nmstate/nmstate)
[![Coverage Status](https://coveralls.io/repos/github/nmstate/nmstate/badge.svg?branch=master)](https://coveralls.io/github/nmstate/nmstate?branch=master)
[![PyPI version](https://badge.fury.io/py/nmstate.svg)](https://badge.fury.io/py/nmstate)
[![Fedora Rawhide version](https://img.shields.io/badge/dynamic/json.svg?label=Fedora%20Rawhide&url=https%3A%2F%2Fapps.fedoraproject.org%2Fmdapi%2Frawhide%2Fpkg%2Fnmstate&query=%24.version&colorB=blue)](https://apps.fedoraproject.org/packages/nmstate)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)

Copr build status:
* EPEL 7 GIT master: [![EPEL7 GIT master Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-el7/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-el7/package/nmstate/)
* Fedora GIT master: [![Fedora GIT master Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-fedora/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git-fedora/package/nmstate/)

## What is it?
Nmstate is a library with an accompanying command line tool that manages
host networking settings in a declarative manner.
The networking state is described by a pre-defined schema.
Reporting of current state and changes to it (desired state) both conform to
the schema.

Nmstate is aimed to satisfy enterprise needs to manage host networking through
a northbound declarative API and multi provider support on the southbound.
NetworkManager acts as the main (and currently the only) provider supported.

## State example:

Desired/Current state example (YAML):
```yaml
interfaces:
- name: eth1
  type: ethernet
  state: up
  ipv4:
    enabled: true
    address:
    - ip: 192.0.2.10
      prefix-length: 24
    dhcp: false
  ipv6:
    enabled: true
    address:
    - ip: 2001:db8:1::a
      prefix-length: 64
    autoconf: false
    dhcp: false
dns-resolver:
  config:
    search:
    - example.com
    - example.org
    server:
    - 2001:4860:4860::8888
    - 8.8.8.8
routes:
  config:
  - destination: 0.0.0.0/0
    next-hop-address: 192.0.2.1
    next-hop-interface: eth1
  - destination: ::/0
    next-hop-address: 2001:db8:1::1
    next-hop-interface: eth1
```

## Basic Operations

Show eth0 current state (python/shell):

```python
import libnmstate

state = libnmstate.show()
eth0_state = next(ifstate for ifstate in state['interfaces'] if ifstate['name'] == 'eth0')

# Here is the MAC address
eth0_mac = eth0_state['mac-address']
```

```shell
nmstatectl show eth0
```

Change to desired state (python/shell):

```python
import libnmstate

# Specify a Linux bridge (created if it does not exist).
state = {'interfaces': [{'name': 'br0', 'type': 'linux-bridge', 'state': 'up'}]}
libnmstate.apply(state)
```

```shell
# use yaml or json formats
nmstatectl set desired-state.yml
nmstatectl set desired-state.json
```

Edit the current state(python/shell):
```python
import libnmstate

state = libnmstate.show()
eth0_state = next(ifstate for ifstate in state['interfaces'] if ifstate['name'] == 'eth0')

# take eth0 down
eth0_state['state'] = 'down'
libnmstate.apply(state)
```

```shell
# open current state in a text editor, change and save to apply
nmstatectl edit eth3
```

## Contact

*Nmstate* uses the [NetworkManager mailing
list](https://mail.gnome.org/mailman/listinfo/networkmanager-list)
([Archives](https://mail.gnome.org/archives/networkmanager-list/)) for
discussions. Emails about nmstate should be tagged with `[nmstate]` in the
subject header to ease filtering.

Development planning (sprints and progress reporting) happens in
([Jira](https://nmstate.atlassian.net)). Access requires login.

There is also `#nmstate` on
[Freenode IRC](https://freenode.net/kb/answer/chat).

## Installation

For Fedora 29+, `sudo dnf install nmstate`.

For others distribution, please see the [install](README.install.md)
instructions.

## Changelog

Please refer to [CHANGELOG](CHANGELOG)
