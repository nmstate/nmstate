FROM nmstate/centos7-nmstate-base

RUN yum -y install \
        python2-pip \
        rpm-build \
        git \
        python2-devel \
        dnsmasq \
        iproute \
        radvd \
    && \
    pip install -U pip pytest==4.2.1 pytest-cov==2.6.1 python-coveralls && \
    yum clean all

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
