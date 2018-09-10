# We are nmstate!
A declarative network manager API for hosts.

[![Build Status](https://travis-ci.org/nmstate/nmstate.png?branch=master)](https://travis-ci.org/nmstate/nmstate)
[![Coverage Status](https://coveralls.io/repos/github/nmstate/nmstate/badge.svg?branch=master)](https://coveralls.io/github/nmstate/nmstate?branch=master)

## What is it?
NMState is a library with an accompanying command line tool that manages
host networking settings in a declarative manner.
The networking state is described by a pre-defined schema.
Reporting of current state and changes to it (desired state) both conform to
the schema.

NMState is aimed to satisfy enterprise needs to manage host networking through
a northbound declarative API and multi provider support on the southbound.
NetworkManager acts as the main (and currently the only) provider supported.

## Development Environment

Install:
```shell
pip install tox pbr
```

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
