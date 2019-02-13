# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos:7.5.1804
ENV container docker
COPY docker_enable_systemd.sh docker_sys_config.sh ./
RUN bash ./docker_enable_systemd.sh && rm ./docker_enable_systemd.sh -f

# libibverbs is a dependency for openvswitch that is missing as a dependency in the RPM
RUN yum -y upgrade && \
    yum -y install epel-release && \
    yum -y install python2-pip iproute NetworkManager \
                   rpm-build git python2-devel python2-six \
                   python2-pyyaml python-jsonschema python-setuptools \
                   NetworkManager-ovs openvswitch libibverbs \
                   python-gobject-base dnsmasq && \
    pip install -U pip pytest==4.2.1 pytest-cov==2.6.1 python-coveralls && \
    yum clean all && \
    bash ./docker_sys_config.sh && rm ./docker_sys_config -f

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
