# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos:7.5.1804
ENV container docker
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == \
     systemd-tmpfiles-setup.service ] || rm -f $i; done); \
    rm -f /lib/systemd/system/multi-user.target.wants/*;\
    rm -f /etc/systemd/system/*.wants/*;\
    rm -f /lib/systemd/system/local-fs.target.wants/*; \
    rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
    rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
    rm -f /lib/systemd/system/basic.target.wants/*;\
    rm -f /lib/systemd/system/anaconda.target.wants/*;

# libibverbs is a dependency for openvswitch that is missing as a dependency in the RPM
RUN yum -y upgrade && \
    yum -y install epel-release && \
    yum -y install python2-pip iproute NetworkManager \
                   rpm-build git python2-devel python2-six \
                   python2-pyyaml python-jsonschema python-setuptools \
                   NetworkManager-ovs openvswitch libibverbs \
                   python-gobject-base dnsmasq && \
    pip install -U pip pytest==4.1.0 pytest-cov==2.6.1 python-coveralls && \
    yum clean all && \
    install -o root -g root -d /etc/sysconfig/network-scripts && \
    echo -e "[logging]\nlevel=TRACE\ndomains=ALL\n" > /etc/NetworkManager/conf.d/97-docker-build.conf && \
    echo -e "[device]\nmatch-device=*\nmanaged=0\n" >> /etc/NetworkManager/conf.d/97-docker-build.conf && \
    sed -i 's/#RateLimitInterval=30s/RateLimitInterval=0/ ; s/#RateLimitBurst=1000/RateLimitBurst=0/' /etc/systemd/journald.conf && \
    systemctl enable openvswitch.service

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
