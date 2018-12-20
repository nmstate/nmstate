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

# Enable EPEL and centos-release-openstack-rocky repo for new version of pytest.
RUN yum -y install epel-release centos-release-openstack-rocky

# Enable nmstate test repo for new version of pytest-cov and NetworkManager bug
# fix of https://bugzilla.redhat.com/show_bug.cgi?id=1642625
RUN yum-config-manager --add-repo https://copr.fedorainfracloud.org/coprs/nmstate/nmstate-test-env-el/repo/epel-7/nmstate-nmstate-test-env-el-epel-7.repo && \
    yum-config-manager --enable nmstate-nmstate-test-env-el

# libibverbs is a dependency for openvswitch that is missing as a dependency in the RPM
RUN yum -y upgrade && \
    yum -y install iproute python2-pytest python2-pytest-cov NetworkManager \
                   rpm-build git python2-devel python2-six \
                   python2-pyyaml python-jsonschema python-setuptools \
                   NetworkManager-ovs openvswitch libibverbs \
                   python-gobject-base dnsmasq && \
    yum clean all && \
    install -o root -g root -d /etc/sysconfig/network-scripts && \
    echo -e "[logging]\nlevel=TRACE\ndomains=ALL\n" > /etc/NetworkManager/conf.d/97-docker-build.conf && \
    echo -e "[device]\nmatch-device=*\nmanaged=0\n" >> /etc/NetworkManager/conf.d/97-docker-build.conf && \
    sed -i 's/#RateLimitInterval=30s/RateLimitInterval=0/ ; s/#RateLimitBurst=1000/RateLimitBurst=0/' /etc/systemd/journald.conf && \
    systemctl enable openvswitch.service

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
