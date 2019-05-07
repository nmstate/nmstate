# This Dockerfile is based on the recommendations provided in the
# Fedora official repository
# (https://hub.docker.com/r/fedora/systemd-systemd/).
# It enables systemd to be operational.
FROM fedora:29
ENV container docker
COPY docker_enable_systemd.sh docker_sys_config.sh ./

RUN bash ./docker_enable_systemd.sh && rm ./docker_enable_systemd.sh

RUN dnf -y install --setopt=install_weak_deps=False \
                   NetworkManager \
                   NetworkManager-ovs \
                   openvswitch \
                   systemd-udev \
                   \
                   python2-dbus \
                   python2-ipaddress \
                   python3-dbus \
                   python3-gobject-base \
                   python3-jsonschema \
                   python3-pyyaml \
                   python3-setuptools \
                   \
                   python2 \
                   python36 \
                   \
                   dnsmasq \
                   git \
                   iproute \
                   python3-coveralls \
                   python3-pytest \
                   python3-pytest-cov \
                   python3-tox \
                   radvd \
                   rpm-build \
                   \
                   # Below packages for pip (used by tox) to build
                   # python-gobject
                   cairo-devel \
                   cairo-gobject-devel \
                   glib2-devel \
                   gobject-introspection-devel \
                   python2-devel \
                   python3-devel \
                   \
                   # Below package for pip (used by tox) to build dbus-python
                   dbus-devel && \
    alternatives --install /usr/bin/python python /usr/bin/python3 1 && \
    ln -s /usr/bin/pytest-3 /usr/bin/pytest && \
    dnf clean all && \
    bash ./docker_sys_config.sh && rm ./docker_sys_config.sh

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
