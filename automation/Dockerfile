FROM nmstate/centos7-nmstate-base

RUN yum -y install \
        python2-pip \
        rpm-build \
        git \
        python2-devel \
        dnsmasq \
        iproute \
        radvd \
        python36-pip \
    && yum clean all

RUN    pip install --upgrade pip pytest==4.2.1 pytest-cov==2.6.1

RUN    pip3 install --user python-coveralls

RUN echo 'PATH="${HOME}/.local/bin:${PATH}"' >> /root/.bashrc

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
