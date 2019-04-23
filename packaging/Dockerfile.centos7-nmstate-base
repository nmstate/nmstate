# This Dockerfile is based on the recommendations provided in the
# Centos official repository (https://hub.docker.com/_/centos/).
# It enables systemd to be operational.
FROM centos:7.5.1804

ENV container docker

COPY docker_enable_systemd.sh docker_sys_config.sh ./

RUN bash ./docker_enable_systemd.sh && rm ./docker_enable_systemd.sh -f

RUN yum -y upgrade && \
    yum -y install \
        NetworkManager \
        NetworkManager-libnm \
        NetworkManager-ovs \
        openvswitch \
    && \
    yum -y install epel-release && \
    yum -y install \
        dbus-python \
        python2-pyyaml \
        python2-six \
        python-gobject-base \
        python-jsonschema \
        python-setuptools \
        python-ipaddress \
    && \
    yum clean all && \
    bash ./docker_sys_config.sh && rm ./docker_sys_config -f
