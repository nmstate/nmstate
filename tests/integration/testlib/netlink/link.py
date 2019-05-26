# Copyright 2014-2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

from __future__ import absolute_import
from __future__ import division
from contextlib import contextmanager
from functools import partial
from socket import AF_UNSPEC
import errno

from . import _cache_manager
from . import _pool
from . import libnl


def get_link(name):
    """Returns the information dictionary of the name specified link."""
    with _pool.socket() as sock:
        with _get_link(name=name, sock=sock) as link:
            if not link:
                raise IOError(errno.ENODEV, '%s is not present in the system' %
                              name)
            link_info = _link_info(link)
        return link_info


def iter_links():
    """Generator that yields an information dictionary for each link of the
    system."""
    with _pool.socket() as sock:
        with _nl_link_cache(sock) as cache:
            link = libnl.nl_cache_get_first(cache)
            while link:
                yield _link_info(link, cache=cache)
                link = libnl.nl_cache_get_next(link)


def is_link_up(link_flags, check_oper_status):
    """
    Check link status based on device status flags.
    :param link_flags: Status flags.
    :param check_oper_status: If set, the operational status of the link is
    checked in addition to the administrative status.
    :return:
    """
    iface_up = link_flags & libnl.IfaceStatus.IFF_UP
    if check_oper_status:
        iface_up = iface_up and (link_flags & libnl.IfaceStatus.IFF_RUNNING)
    return bool(iface_up)


def _link_info(link, cache=None):
    """Returns a dictionary with the information of the link object."""
    info = {}
    address = libnl.rtnl_link_get_addr(link)
    info['address'] = libnl.nl_addr2str(address) if address else None
    info['flags'] = libnl.rtnl_link_get_flags(link)
    info['index'] = libnl.rtnl_link_get_ifindex(link)
    info['mtu'] = libnl.rtnl_link_get_mtu(link)
    info['name'] = libnl.rtnl_link_get_name(link)
    info['qdisc'] = libnl.rtnl_link_get_qdisc(link)
    info['state'] = _link_state(link)

    link_type = libnl.rtnl_link_get_type(link)
    if link_type is not None:
        info['type'] = link_type

    underlying_device_index = libnl.rtnl_link_get_link(link)
    if underlying_device_index:
        info['device_index'] = underlying_device_index
        try:
            info['device'] = _link_index_to_name(underlying_device_index,
                                                 cache=cache)
        except IOError as err:
            if err.errno != errno.ENODEV:
                raise

    master_index = libnl.rtnl_link_get_master(link)
    if master_index:
        info['master_index'] = master_index
        try:
            info['master'] = _link_index_to_name(master_index, cache=cache)
        except IOError as err:
            if err.errno != errno.ENODEV:
                raise

    if libnl.rtnl_link_is_vlan(link):
        info['vlanid'] = libnl.rtnl_link_vlan_get_id(link)

    return info


def _link_index_to_name(link_index, cache=None):
    """Returns the textual name of the link with index equal to link_index."""
    if cache is None:
        with _get_link(index=link_index) as link:
            if link is None:
                raise IOError(errno.ENODEV, 'Dev with index %s is not present '
                                            'in the system' % link_index)
            name = libnl.rtnl_link_get_name(link)
        return name
    else:
        return libnl.rtnl_link_i2name(cache, link_index)


def _link_state(link):
    """Returns the textual representation of the link's operstate."""
    state = libnl.rtnl_link_get_operstate(link)
    return libnl.rtnl_link_operstate2str(state)


@contextmanager
def _get_link(name=None, index=0, sock=None):
    """ If defined both name and index, index is primary """
    # libnl/incluede/netlink/errno.h
    NLE_NODEV = 31

    if name is None and index == 0:
        raise ValueError('Must specify either a name or an index')

    try:
        if sock is None:
            with _pool.socket() as sock:
                link = libnl.rtnl_link_get_kernel(sock, index, name)
        else:
            link = libnl.rtnl_link_get_kernel(sock, index, name)
    except IOError as ioe:
        if ioe.errno == NLE_NODEV:
            link = None
        else:
            raise

    try:
        yield link
    finally:
        if link is not None:
            libnl.rtnl_link_put(link)


def _rtnl_link_alloc_cache(socket):
    return libnl.rtnl_link_alloc_cache(socket, AF_UNSPEC)


_nl_link_cache = partial(_cache_manager, _rtnl_link_alloc_cache)
