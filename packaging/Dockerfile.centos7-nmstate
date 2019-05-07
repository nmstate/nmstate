FROM nmstate/centos7-nmstate-base

ARG SOURCE_COMMIT

# dbus-python is special and does not provide egg files, therefore it is not
# used by pip and needs to be compiled from PyPi. For this the build
# dependencies are needed.
# https://bugzilla.redhat.com/show_bug.cgi?id=1654774
RUN yum -y install \
        python2-pip \
        git \
    && \
    yum-builddep -y dbus-python && \
    yum clean all

RUN pip install git+https://github.com/nmstate/nmstate@${SOURCE_COMMIT:-master}

VOLUME [ "/sys/fs/cgroup" ]

CMD ["/usr/sbin/init"]
