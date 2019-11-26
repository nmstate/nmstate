# Nmstate Installation

## User Installation

### Install pre-requirements
Despite the pure python dependencies (see requirements.txt),
Nmstate also needs NetworkManager to be running on the local system
in order to configure the local network state.
To access NetworkManager, Nmstate needs libnm and the corresponding
introspection data (`NM-1.0.typelib`, provided by `python-gobject-base`).

To manage OvS, Nmstate needs the packages `NetworkManager-ovs` and `openvswitch`.

#### Post Package installation

NetworkManager requires special configuration snippets to overcome some
existing limitations.

```
echo -e "[device]\nmatch-device=*\nmanaged=0\n" >> \
    /etc/NetworkManager/conf.d/97-nmstate.conf
echo -e "[main]\nno-auto-default=*\n" >> \
    /etc/NetworkManager/conf.d/97-nmstate.conf
```

NetworkManager needs to be restarted in order to use the new configuration
parameters (`conf.d/97-nmstate.conf`) and the OvS plugin.
The openvswitch service also needs to be started.

```
systemctl restart NetworkManager
systemctl restart openvswitch
# To keep NetworkManager and openvswitch running after reboot:
systemctl enable --now NetworkManager openvswitch
```

### Install nmstate from PyPi (on RHEL 8)

Minimal Nmstate installation:
``` shell
# install binary dependencies; The development packages are needed to build
# python-dbus which is improperly packaged on RHEL 8:
# https://bugzilla.redhat.com/show_bug.cgi?id=1654774
yum install -y dbus-devel gcc glib2-devel make python3-devel python3-gobject-base
yum install -y python3-pip
pip3 uninstall -y nmstate; pip3 install nmstate
```

For all features, extra workarounds and other packages might be necessary, see
the pre-requirements section for details.

### Install nmstate from source

Install just for the local user:

```shell
pip install --user --upgrade .
```

Make sure that `~/.local/bin` is in your PATH when installing as a local user.
The `export` command can be used to add it for the current session:

```shell
export PATH="${HOME}/.local/bin:${PATH}"
```

Alternatively, install Nmstate system-wide:
```shell
pip uninstall -y nmstate; pip install .
```

## Development Environment

Nmstate uses `tox` to run unit tests and linters. Since Nmstate uses the binary
module PyGObject it also requires the build dependencies for it.

### Unit tests
Run Unit Tests:
```shell
tox
```
