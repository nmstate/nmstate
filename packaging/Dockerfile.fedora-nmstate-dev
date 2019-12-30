# This Dockerfile is based on the recommendations provided in the
# Fedora official repository
# (https://hub.docker.com/r/fedora/systemd-systemd/).
# It enables systemd to be operational.
FROM fedora:31
ENV container docker
COPY docker_enable_systemd.sh docker_sys_config.sh ./

RUN bash ./docker_enable_systemd.sh && rm ./docker_enable_systemd.sh

RUN dnf -y install --setopt=install_weak_deps=False \
                   NetworkManager \
                   NetworkManager-ovs \
                   NetworkManager-config-server \
                   dhcp-client \
                   openvswitch \
                   systemd-udev \
                   \
                   python3-dbus \
                   python3-gobject-base \
                   python3-jsonschema \
                   python3-pyyaml \
                   python3-setuptools \
                   python3-pip \
                   \
                   python36 \
                   \
                   python38 \
                   \
                   dnsmasq \
                   git \
                   iproute \
                   python3-coveralls \
                   python3-tox \
                   rpm-build \
                   \
                   # Below packages for pip (used by tox) to build
                   # python-gobject
                   cairo-devel \
                   cairo-gobject-devel \
                   glib2-devel \
                   gobject-introspection-devel \
                   python3-devel \
                   \
                   # Below package for pip (used by tox) to build dbus-python
                   make \
                   dbus-devel && \
    dnf clean all && \
    pip install pytest==4.6.6 pytest-cov==2.8.1 --user && \
    # Below line is workaround for
    #   https://src.fedoraproject.org/rpms/rootfiles/pull-request/1
    ln -s /root/.local/bin/pytest /usr/bin/pytest && \
    bash ./docker_sys_config.sh && rm ./docker_sys_config.sh

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
