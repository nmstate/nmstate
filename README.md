# We are Nmstate!

<img src="logo/fullcolor.png" alias="project logo" />

A declarative network manager API for hosts.

![CI](https://github.com/nmstate/nmstate/workflows/CI/badge.svg?branch=base)
[![Coverage Status](https://coveralls.io/repos/github/nmstate/nmstate/badge.svg?branch=base)](https://coveralls.io/github/nmstate/nmstate?branch=base)
[![PyPI version](https://badge.fury.io/py/nmstate.svg)](https://badge.fury.io/py/nmstate)
[![Fedora Rawhide version](https://img.shields.io/badge/dynamic/json.svg?label=Fedora%20Rawhide&url=https%3A%2F%2Fapps.fedoraproject.org%2Fmdapi%2Frawhide%2Fpkg%2Fnmstate&query=%24.version&colorB=blue)](https://src.fedoraproject.org/rpms/nmstate)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/python/black)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/nmstate/nmstate.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/nmstate/nmstate/context:python)

Copr build status, all repos are built for Fedora Linux and RHEL/CentOS Stream/EPEL 8+:

* Latest release: [![Latest release Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate/package/nmstate/)
* Git base: [![Git base Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git/package/nmstate/)

## What is it?
Nmstate is a library with an accompanying command line tool that manages
host networking settings in a declarative manner.
The networking state is described by a pre-defined schema.
Reporting of the current state and changes to it (desired state) both conform to
the schema.

Nmstate is aimed to satisfy enterprise needs to manage host networking through
a northbound declarative API and multi-provider support on the southbound.
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

Change to the desired state (python/shell):

```python
import libnmstate

# Specify a Linux bridge (created if it does not exist).
state = {'interfaces': [{'name': 'br0', 'type': 'linux-bridge', 'state': 'up'}]}
libnmstate.apply(state)
```

```shell
# use YAML or JSON formats
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
# open the current state in a text editor, change it and save to apply
nmstatectl edit eth3
```

## Contact

*Nmstate* uses the [nmstate-devel@lists.fedorahosted.org][mailing_list] for
discussions. To subscribe you can send an email with 'subscribe' in the subject
to <nmstate-devel-join@lists.fedorahosted.org> or visit the
[mailing list page][mailing_list].

Sprint tracking happens in 
([GitHub projects](https://github.com/nmstate/nmstate/projects)).

There is also `#nmstate` on
[Libera IRC](https://libera.chat/).

## Contributing

Yay! We are happy to accept new contributors to the Nmstate project. Please follow
these [instructions](CONTRIBUTING.md) to contribute.

## Installation

For Fedora 29+, `sudo dnf install nmstate`. 

For other distribution, please see the [install guide](https://nmstate.io/user/install.html).

## Documentation

* [libnmstate API](https://nmstate.github.io/devel/api.html)
* [Code examples](https://nmstate.github.io/devel/py_example.html)
* [State examples](https://nmstate.github.io/examples.html)
* [nmstatectl user guide](https://nmstate.github.io/cli_guide.html)
* nmstatectl man page: `man nmstatectl`

## Limitations

* The maximum supported number of interfaces in a single desire state is 1000.

## Changelog

Please refer to [CHANGELOG](CHANGELOG)


[mailing_list]: https://lists.fedorahosted.org/admin/lists/nmstate-devel.lists.fedorahosted.org
