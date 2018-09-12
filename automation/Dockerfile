# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos:7
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

RUN yum -y install NetworkManager epel-release git cairo* && \
    yum -y install python2-pip gcc python-devel gobject-introspection-devel && \
    yum clean all && \
    pip install -U pip setuptools pbr tox

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
