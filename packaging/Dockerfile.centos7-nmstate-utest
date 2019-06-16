# This image definition is defining
# a container image on which unit and lint tests
# can be run locally through `tox`.

FROM centos:7

RUN yum -y upgrade \
    && \
    yum -y install \
        NetworkManager \
        NetworkManager-libnm \
    && \
    yum -y install epel-release \
    && \
    yum -y install \
        python36 \
        python2-pip \
        python36-pip \
        make \
    && \
    yum-builddep -y \
        python-gobject \
        dbus-python \
    && \
    yum clean all \
    && \
    pip install tox
