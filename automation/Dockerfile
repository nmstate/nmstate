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

RUN yum -y install iproute NetworkManager epel-release git cairo* && \
    yum -y install python2-pip gcc python-devel gobject-introspection-devel && \
    yum clean all && \
    pip install -U \
      pip \
      setuptools \
      pbr \
      tox \
      \
      pluggy==0.6 \
      PyGObject \
      pytest-cov \
      pytest==3.5.1 && \
    \
    install -o root -g root -d /etc/sysconfig/network-scripts && \
    echo -e "[logging]\nlevel=TRACE\ndomains=ALL\n" > /etc/NetworkManager/conf.d/97-docker-build.conf && \
    echo -e "[device]\nmatch-device=*\nmanaged=0\n" >> /etc/NetworkManager/conf.d/97-docker-build.conf && \
    sed -i 's/#RateLimitInterval=30s/RateLimitInterval=0/ ; s/#RateLimitBurst=1000/RateLimitBurst=0/' /etc/systemd/journald.conf

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
