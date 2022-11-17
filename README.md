# We are Nmstate!

<img src="logo/fullcolor.png" alias="project logo" />

A declarative network management API for hosts.

![CI](https://github.com/nmstate/nmstate/workflows/CI/badge.svg?branch=base)
[![crates.io](https://img.shields.io/crates/v/nmstate.svg)
[![docs.rs](https://img.shields.io/docsrs/nmstate)
[![Fedora Rawhide version](https://img.shields.io/badge/dynamic/json.svg?label=Fedora%20Rawhide&url=https%3A%2F%2Fapps.fedoraproject.org%2Fmdapi%2Frawhide%2Fpkg%2Fnmstate&query=%24.version&colorB=blue)](https://src.fedoraproject.org/rpms/nmstate)

Copr build status, all repos are built for Fedora Linux and RHEL/CentOS Stream/EPEL 8+:

* Latest release: [![Latest release Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate/package/nmstate/)
* Git base: [![Git base Copr build status](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git/package/nmstate/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-git/package/nmstate/)

Nmstate is a library with an accompanying command line tool that manages
host networking settings in a declarative manner.
The networking state is described by a pre-defined schema.
Reporting of current state and changes to it (desired state) both conform to
the schema.

Nmstate is aimed to satisfy enterprise needs to manage host networking through
a northbound declarative API and multi provider support on the southbound.
NetworkManager acts as the main (and currently the only) provider supported.

Nmstate provides:
 * Rust crate -- [nmstate][https://crates.io/crates/nmstate]
 * Command line tools -- `cargo install nmstatectl`
 * Python library -- `libnmstate`
 * Go binding
 * C binding

More document could be found at [nmstate.io](https://nmstate.io)

## State example:

Desired/Current state example (YAML):
```yaml
---
dns:
  config:
    server:
      - 192.0.2.1
    search:
      - example.org
routes:
  config:
    - destination: 0.0.0.0/0
      next-hop-interface: eth1
      next-hop-address: 192.0.2.1
interfaces:
  - name: eth1
    type: ethernet
    description: Main-NIC
    state: up
    ipv4:
      enabled: true
      dhcp: false
      address:
        - ip: 192.0.2.9
          prefix-length: 24
    ipv6:
      enabled: false
```

## Contact

*Nmstate* [GitHub Issues pages][github_issue_url] for discussion.

You may find us in `#nmstate` on [Libera IRC](https://libera.chat/) also.

## Contributing

Yay! We are happy to accept new contributors to the Nmstate project. Please
follow these [instructions](CONTRIBUTING.md) to contribute.

## Installation

For Fedora 29+, `sudo dnf install nmstate`.

For other distribution, please see the [install guide](https://nmstate.io/user/install.html).

## Documentation

* [libnmstate API](https://nmstate.github.io/devel/api.html)
* [Code examples](https://nmstate.github.io/devel/py_example.html)
* [State examples](https://nmstate.github.io/examples.html)
* [nmstatectl user guide](https://nmstate.github.io/cli_guide.html)
* nmstatectl man page: `man nmstatectl`

## Changelog

Please refer to [CHANGELOG](CHANGELOG)

[mailing_list]: https://lists.fedorahosted.org/admin/lists/nmstate-devel.lists.fedorahosted.org
[github_issue_url]: https://github.com/nmstate/nmstate/issues
