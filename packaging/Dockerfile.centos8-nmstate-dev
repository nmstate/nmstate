# This Dockerfile is based on the recommendations provided in the
# Fedora official repository
# (https://hub.docker.com/r/fedora/systemd-systemd/).
# It enables systemd to be operational.
FROM centos:8
ENV container docker
COPY docker_enable_systemd.sh docker_sys_config.sh ./

RUN bash ./docker_enable_systemd.sh && rm ./docker_enable_systemd.sh

RUN dnf -y install dnf-plugins-core && \
    dnf config-manager --set-enabled PowerTools

RUN dnf copr enable nmstate/ovs-el8 -y && \
    dnf copr enable networkmanager/NetworkManager-1.20 -y

RUN dnf -y install --setopt=install_weak_deps=False \
                   NetworkManager \
                   NetworkManager-ovs \
                   NetworkManager-config-server \
                   openvswitch2.11 \
                   systemd-udev \
                   python3-dbus \
                   python3-gobject-base \
                   python3-jsonschema \
                   python3-pyyaml \
                   python3-setuptools \
                   python36 \
                   dnsmasq \
                   git \
                   iproute \
                   rpm-build \
                   # Below package for pip (used by tox) to build dbus-python
                   # Bug https://bugzilla.redhat.com/show_bug.cgi?id=1654774
                   make \
                   python3-devel \
                   cairo-devel \
                   cairo-gobject-devel \
                   glib2-devel \
                   gobject-introspection-devel \
                   dbus-devel && \
    dnf -y group install "Development Tools" && \
    pip3 install pytest==4.6.6 pytest-cov==2.8.1 \
        python-coveralls tox --user && \
    alternatives --set python /usr/bin/python3 && \
    ln -s /root/.local/bin/pytest /usr/bin/pytest && \
    ln -s /root/.local/bin/tox /usr/bin/tox && \
    dnf clean all && \
    bash ./docker_sys_config.sh && rm ./docker_sys_config.sh

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
