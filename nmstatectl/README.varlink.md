# Varlink support for libnmstate
Varlink protocol ([Varlink.org](https://varlink.org/)) can used to communicate with libnmstate via stdin/out and varlink client implementation ([Existing Language binding](https://varlink.org/Language-Bindings#how-to-test-new-language-bindings)). Varlink protocol encodes all messages as JSON object and communicates over unix and tcp socket connections. Nmstate service is defined in io.nmstate interface address and libnmstate functions should called in as specified in varlink interface defination file `io.nmstate.varlink`. This implementation supports python3-varlink version 29.0.0 and unix socket connection only.


## Initiate nmstate varlink service
User can initate nmstate-varlink services using ```nmstatectl``` command-line tool by defining the unix socket address path. The current nmstate-varlink implementation limits only using unix sockets connection.

unix socket connection
```bash
$ nmstatectl varlink /run/nmstate.so &
```

After the `io.nmstate` interface is resolved using varlink resolver. Methods can be called directly via stdin/out without specifying the connection.
`varlink call io.nmstate.Show`

## Nmstate basic operations using varlink
The basic functions from libnmstate (show, apply, commit and rollback) are called via varlink interface. Passing inputs to the functions only support JSON format. Below are the examples for each basic functions using varlink stdin/out and varlink client.

Using libnmstate show function via varlink (query network state)

Required for varlink stdin/out operation

```bash
$ dnf install libvarlink-utils
```

Varlink stdin/out:
```bash
$ varlink call unix:/run/nmstate.so/io.nmstate.Show

# If interface is resolved using the varlink resolver

$ varlink call io.nmstate.Show
```

Varlink python client:
```python
import varlink

with varlink.Client("unix:/run/nmstate.so").open("io.nmstate") as nmstate:
    nmstate.Show()
```

JSON output: libnmstate current network is reported under "state" object.
```json
{
  "log": [
    {
      "level": "DEBUG",
      "message": "Async action: Retrieve applied config: foo started",
      "time": "2020-08-05 10:22:19"
    },
    {
      "level": "DEBUG",
      "message": "Async action: Retrieve applied config: foo finished",
      "time": "2020-08-05 10:22:19"
    }

  ],
  "state": {
    "dns-resolver": {
      "config": {
        "search": [],
        "server": []
      },
      "running": {}
    },
    "interfaces": [
      {
        "ipv4": {
          "enabled": false
        },
        "ipv6": {
          "enabled": false
        },
        "lldp": {
          "enabled": false
        },
        "mac-address": "36:66:98:1D:6A:C8",
        "mtu": 1500,
        "name": "eth0",
        "state": "down",
        "type": "ethernet"
      },
    ],
    "route-rules": {
      "config": []
    },
    "routes": {
      "config": [],
      "running": []
    }
  }
}
```

Using libnmstate apply function via varlink (query network state)

Varlink stdin/out:
state should be passed in json string format and varlink doesn't support passing json file.

```bash
$ varlink call unix:/run/nmstate.so/io.nmstate.Apply '{"arguments": {"desired_state": {"interfaces": [{"name": "foo", "type": "dummy", "state": "up", "ipv4": {"enabled": false}, "ipv6": {"enabled": false}}]} } }'

```
* When using the varlink client it is not requried specify the "argument" parameter.

Varlink python client:
```python
import varlink

state = {'desired_state': {'interfaces': [{'name': 'foo', 'type': 'dummy', 'state': 'up', 'ipv4': {'enabled': False}, 'ipv6': {'enabled': False}}]} }

with varlink.Client("unix:/run/nmstate.so").open("io.nmstate") as nmstate:
    nmstate.Apply(state)
```

## Error response
All error nmstate messages are encoded as JSON object format. Errors are identified with specified varlink interface description

* Example shows format of the error raised via varlink stdin/out and varlink client calling Commit method with null value.

Varlink stdin/out:
```bash
Call failed with error: NmstateValueError
{
  "error_message": "No checkpoint specified or found",
  "log": [
    {
      "level": "ERROR",
      "message": "No checkpoint specified or found",
      "name": "root",
      "time": "2020-07-31 15:16:22"
    }
  ]
}
```

Varlink python client:
```python
varlink.error.VarlinkError: {
    'error': 'NmstateValueError',
    'parameters': {
        'error_message': 'No checkpoint specified or found',
        'log': [
            {
                'time': '2020-07-31 15:18:06',
                'level': 'ERROR',
                'message': 'No checkpoint specified or found'
            }
        ]
    }
}
```