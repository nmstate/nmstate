# Nmstate Installation

## User Installation

To install the latest version build from the master branch on Fedora,
CentOS/EPEL/RHEL 8, use the Nmstate Copr repository:

``` shell
yum copr enable nmstate/nmstate-git
yum install nmstate
```

### Special Requirements
Nmstate also needs NetworkManager to be running on the local system
in order to configure the local network state.
To access NetworkManager, Nmstate needs libnm and the corresponding
introspection data (`NM-1.0.typelib`, provided by `python-gobject-base`).

To manage OvS, Nmstate needs the packages `NetworkManager-ovs` and `openvswitch`.

#### Post Package installation

NetworkManager needs to be restarted in order to use the new configuration
parameters and the OvS plugin.
The openvswitch service also needs to be started.

```
systemctl restart NetworkManager
systemctl restart openvswitch
# To keep NetworkManager and openvswitch running after reboot:
systemctl enable --now NetworkManager openvswitch
```

### Install nmstate from PyPi

Minimal Nmstate installation:
``` shell
# install binary dependencies
yum install -y python3-gobject-base
yum install -y python3-pip
pip3 uninstall -y nmstate; pip3 install nmstate
```

For all features, extra workarounds and other packages might be necessary, see
the Special Requirements section for details.

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
### Install nmstate from tarball

Please, consider using the distributed version/Copr or PyPi instead of this
method.

Download the tarball and the signature file. Then, verify the signature:
```bash
curl --silent https://www.nmstate.io/nmstate.gpg | gpg2 --import
gpg2 --verify nmstate-<version>.tar.gz.asc nmstate-<version>.tar.gz
```

Extract the tarball and install nmstate.

```bash
tar xzvf nmstate-<version>.tar.gz
python3 nmstate-<version>/setup.py build
python3 nmstate-<version>/setup.py install
```

## Development Environment

Nmstate uses `tox` to run unit tests and linters. Since Nmstate uses the binary
module PyGObject it also requires the build dependencies for it.

### Unit tests
Run Unit Tests:
```shell
tox
```
