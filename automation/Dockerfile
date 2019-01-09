# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos:7.5.1804
ENV container docker
COPY docker_enable_systemd.sh docker_sys_config.sh ./
RUN bash ./docker_enable_systemd.sh

RUN yum -y install epel-release && \
    yum -y install python2-pip && \
    pip install -U pip pytest-cov pytest python-coveralls

# libibverbs is a dependency for openvswitch that is missing as a dependency in the RPM
RUN yum -y upgrade && \
    yum -y install iproute NetworkManager \
                   rpm-build git python2-devel python2-six \
                   python2-pyyaml python-jsonschema python-setuptools \
                   NetworkManager-ovs openvswitch libibverbs \
                   python-gobject-base dnsmasq && \
    yum clean all && \
    bash ./docker_sys_config.sh

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
