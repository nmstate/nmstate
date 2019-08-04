# Nmstate Installation

## User Installation

### Install pre-requirements
Despite the pure python dependencies (see requirements.txt),
Nmstate also needs NetworkManager to be running on the local system
in order to configure the local network state.
To access NetworkManager, Nmstate needs libnm and the corresponding
introspection data (`NM-1.0.typelib`, provided by `python-gobject-base`).

To manage OvS, Nmstate needs the packages `NetworkManager-ovs` and `openvswitch`.

#### Package installation (CentOS 7)

```shell
yum -y install epel-release
yum -y install \
    dbus-python \
    NetworkManager \
    NetworkManager-libnm \
    NetworkManager-ovs \
    openvswitch \
    python-gobject-base \
    python-ipaddress \
    python-jsonschema \
    python-setuptools \
    python2-pyyaml \
    python2-six
yum-builddep -y dbus-python
```

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

### Install nmstate from PyPi (Python 2)
```shell
yum -y install python2-pip
pip uninstall -y nmstate; pip install nmstate
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

### Container Image

Nmstate also provides a container image based on CentOS 7 to try it:

```shell
CONTAINER_ID=$(sudo docker run --privileged -d -v /sys/fs/cgroup:/sys/fs/cgroup:ro nmstate/centos7-nmstate)
sudo docker exec -ti "${CONTAINER_ID}" /bin/bash
# now play with nmstatectl in the container
nmstatectl show
# remove the container at the end
sudo docker stop "${CONTAINER_ID}"
sudo docker rm "${CONTAINER_ID}"
```


## Development Environment

Nmstate uses `tox` to run unit tests and linters. Since Nmstate uses the binary
module PyGObject it also requires the build dependencies for it.

### RHEL 7.6

Recommended minimum installation:
```shell
yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm  # install EPEL for python-pip
subscription-manager repos --enable "rhel-*-optional-rpms" --enable "rhel-*-extras-rpms"  # recommended for EPEL
yum install git python-pip
yum-builddep python-gobject  # install build dependencies for PyGObject
pip install tox  # python-tox in EPEL seems to be too old
```

### CentOS 7.6

Recommended minimum installation:
```shell
yum -y install epel-release
yum -y install \
    NetworkManager \
    NetworkManager-libnm \
    git \
    python-pip
yum-builddep python-gobject  # install build dependencies for PyGObject
pip install tox  # python-tox in EPEL seems to be too old
```

Note: This will not run the unit tests for Python 3.6 because this Python version is not available there.

### Unit tests
Run Unit Tests:
```shell
tox
```
