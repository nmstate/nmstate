FROM nmstate/centos7-nmstate-base

RUN yum -y install \
        dnsmasq \
        git \
        iproute \
        python2-devel \
        python2-pip \
        python36-pip \
        radvd \
        rpm-build \
    && yum clean all

RUN pip install --upgrade pip pytest==4.2.1 pytest-cov==2.6.1

RUN pip3 install --user python-coveralls

RUN echo 'PATH="${HOME}/.local/bin:${PATH}"' >> /root/.bashrc

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
