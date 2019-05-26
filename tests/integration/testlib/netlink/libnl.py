# Copyright 2017-2019 Red Hat, Inc.
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

"""libnl and libnl-route bindings.

This module provides libnl functions bindings for Python. All ctypes imports
should be contained in this package, provided functions should be usable in
native Python manner.

- Functions have same names as their C counterparts.
- Text arguments are provided as native Python string (bytes in Python 2,
  unicode in Python 3).
- Returned text values are converted to native Python string.
- Values are returned only via 'return', never as a pointer argument.
- Errors are raised as exceptions, never as a return code.
"""

from __future__ import absolute_import
from __future__ import division

from ctypes import CDLL, CFUNCTYPE, sizeof, get_errno, byref
from ctypes import c_char, c_char_p, c_int, c_void_p, c_size_t, py_object

from .. import py2to3
from ..cache import memoized

LIBNL = CDLL('libnl-3.so.200', use_errno=True)
LIBNL_ROUTE = CDLL('libnl-route-3.so.200', use_errno=True)

CHARBUFFSIZE = 40  # Increased to fit IPv6 expanded representations
HWADDRSIZE = 60    # InfiniBand HW address needs 59+1 bytes

# include/linux-private/linux/netlink.h
NETLINK_ROUTE = 0  # Routing/device hook

# libnl/include/linux/rtnetlink.h
GROUPS = {
    'link': 1,             # RTNLGRP_LINK
    'notify': 2,           # RTNPGRP_NOTIFY
    'neigh': 3,            # RTNLGRP_NEIGH
    'tc': 4,               # RTNLGRP_TC
    'ipv4-ifaddr': 5,      # RTNLGRP_IPV4_IFADDR
    'ipv4-mroute': 6,      # RTNLGRP_IPV4_MROUTE
    'ipv4-route': 7,       # RTNLGRP_IPV4_ROUTE
    'ipv6-ifaddr': 9,      # RTNLGRP_IPV6_IFADDR
    'ipv6-mroute': 10,     # RTNLGRP_IPV6_MROUTE
    'ipv6-route': 11,      # RTNLGRP_IPV6_ROUTE
    'ipv6-ifinfo': 12,     # RTNLGRP_IPV6_IFINFO
    'decnet-ifaddr': 13,   # RTNLGRP_DECnet_IFADDR
    'decnet-route': 14,    # RTNLGRP_DECnet_ROUTE
    'ipv6-prefix': 16      # RTNLGRP_IPV6_PREFIX
}

# libnl/include/linux/rtnetlink.h
EVENTS = {
    16: 'new_link',            # RTM_NEWLINK
    17: 'del_link',            # RTM_DELLINK
    18: 'get_link',            # RTM_GETLINK
    19: 'set_link',            # RTM_SETLINK
    20: 'new_addr',            # RTM_NEWADDR
    21: 'del_addr',            # RTM_DELADDR
    22: 'get_addr',            # RTM_GETADDR
    24: 'new_route',           # RTM_NEWROUTE
    25: 'del_route',           # RTM_DELROUTE
    26: 'get_route',           # RTM_GETROUTE
    28: 'new_neigh',           # RTM_NEWNEIGH
    29: 'del_neigh',           # RTM_DELNEIGH
    30: 'get_neigh',           # RTM_GETNEIGH
    32: 'new_rule',            # RTM_NEWRULE
    33: 'del_rule',            # RTM_DELRULE
    34: 'get_rule',            # RTM_GETRULE
    36: 'new_qdisc',           # RTM_NEWQDISC
    37: 'del_qdisc',           # RTM_DELQDISC
    38: 'get_qdisc',           # RTM_GETQDISC
    40: 'new_tclass',          # RTM_NEWTCLASS
    41: 'del_tclass',          # RTM_DELTCLASS
    42: 'get_tclass',          # RTM_GETTCLASS
    44: 'new_tfilter',         # RTM_NEWTFILTER
    45: 'del_tfilter',         # RTM_DELTFILTER
    46: 'get_tfilter',         # RTM_GETTFILTER
    48: 'new_action',          # RTM_NEWACTION
    49: 'del_action',          # RTM_DELACTION
    50: 'get_action',          # RTM_GETACTION
    52: 'new_prefix',          # RTM_NEWPREFIX
    58: 'get_multicast',       # RTM_GETMULTICAST
    62: 'get_anycast',         # RTM_GETANYCAST
    64: 'new_neightbl',        # RTM_NEWNEIGHTBL
    66: 'get_neightbl',        # RTM_GETNEIGHTBL
    67: 'set_neightbl',        # RTM_SETNEIGHTBL
    68: 'new_nduseropt',       # RTM_NEWNDUSEROPT
    72: 'new_addrlabel',       # RTM_NEWADDRLABEL
    73: 'del_addrlabel',       # RTM_DELADDRLABEL
    74: 'get_addrlabel',       # RTM_GETADDRLABEL
    78: 'get_dcb',             # RTM_GETDCB
    79: 'set_dcb'              # RTM_SETDCB
}


# libnl/include/linux-private/linux/rtnetlink.h
class RtKnownTables(object):
    RT_TABLE_UNSPEC = 0
    RT_TABLE_COMPAT = 252
    RT_TABLE_DEFAULT = 253
    RT_TABLE_MAIN = 254
    RT_TABLE_LOCAL = 255
    RT_TABLE_MAX = 0xFFFFFFFF


# include/linux-private/linux/if.h
class IfaceStatus(object):
    IFF_UP = 1 << 0             # Device administrative status.
    IFF_BROADCAST = 1 << 1
    IFF_DEBUG = 1 << 2
    IFF_LOOPBACK = 1 << 3
    IFF_POINTOPOINT = 1 << 4
    IFF_NOTRAILERS = 1 << 5
    IFF_RUNNING = 1 << 6        # Device operational_status
    IFF_NOARP = 1 << 7
    IFF_PROMISC = 1 << 8
    IFF_ALLMULTI = 1 << 9
    IFF_MASTER = 1 << 10
    IFF_SLAVE = 1 << 11
    IFF_MULTICAST = 1 << 12
    IFF_PORTSEL = 1 << 13
    IFF_AUTOMEDIA = 1 << 14
    IFF_DYNAMIC = 1 << 15
    IFF_LOWER_UP = 1 << 16
    IFF_DORMANT = 1 << 17
    IFF_ECHO = 1 << 18


# include/netlink/handlers.h
class NlCbAction(object):
    NL_OK = 0  # Proceed with whatever would come next
    NL_SKIP = 1  # Skip this message
    NL_STOP = 2  # Stop parsing altogether and discard remaining messages


# include/netlink/handlers.h
class NlCbKind(object):
    NL_CB_DEFAULT = 0  # Default handlers (quiet)
    NL_CB_VERBOSE = 1  # Verbose default handlers (error messages printed)
    NL_CB_DEBUG = 2  # Debug handlers for debugging
    NL_CB_CUSTOM = 3  # Customized handler specified by user


class RtnlObjectType(object):
    BASE = 'route'
    ADDR = BASE + '/addr'  # libnl/lib/route/addr.c
    LINK = BASE + '/link'  # libnl/lib/route/link.c


def nl_geterror(error_code):
    """Return error message for an error code.

    @arg error_code      error code

    @return error message
    """
    _nl_geterror = _libnl('nl_geterror', c_char_p, c_int)
    error_message = _nl_geterror(error_code)
    return py2to3.to_str(error_message)


def nl_addr2str(addr):
    """Convert abstract address object to string.

    @arg addr            Abstract address object.

    @return Address represented as string
    """
    _nl_addr2str = _libnl(
        'nl_addr2str', c_char_p, c_void_p, c_char_p, c_size_t)
    buf = (c_char * HWADDRSIZE)()
    address = _nl_addr2str(addr, buf, sizeof(buf))
    return py2to3.to_str(address)


def nl_af2str(family):
    """Convert address family code to string.

    @arg family          Address family code.

    @return Address family represented as string
    """
    _nl_af2str = _libnl('nl_af2str', c_char_p, c_int, c_char_p, c_size_t)
    buf = (c_char * CHARBUFFSIZE)()
    address_family = _nl_af2str(family, buf, sizeof(buf))
    return py2to3.to_str(address_family)


def rtnl_scope2str(scope):
    """Convert address scope code to string.

    @arg scope           Address scope code.

    @return Address scope represented as string
    """
    _rtnl_scope2str = _libnl_route(
        'rtnl_scope2str', c_char_p, c_int, c_char_p, c_size_t)
    buf = (c_char * CHARBUFFSIZE)()
    address_scope = _rtnl_scope2str(scope, buf, sizeof(buf))
    return py2to3.to_str(address_scope)


def nl_socket_alloc():
    """Allocate new netlink socket.

    @return Newly allocated netlink socket.
    """
    _nl_socket_alloc = _libnl('nl_socket_alloc', c_void_p)
    allocated_socket = _nl_socket_alloc()
    if allocated_socket is None:
        raise IOError(get_errno(), 'Failed to allocate socket.')
    return allocated_socket


def nl_connect(socket, protocol):
    """Create file descriptor and bind socket.

    @arg socket          Netlink socket
    @arg protocol        Netlink protocol to use
    """
    _nl_connect = _libnl('nl_connect', c_int, c_void_p, c_int)
    err = _nl_connect(socket, protocol)
    if err:
        raise IOError(-err, nl_geterror(err))


def nl_socket_free(socket):
    """Free a netlink socket.

    @arg socket          Netlink socket.
    """
    _nl_socket_free = _libnl('nl_socket_free', None, c_void_p)
    _nl_socket_free(socket)


def nl_socket_set_buffer_size(socket, rx_buf_size, tx_buf_size):
    """Send/Receive Buffer Size

    The default is 32KiB.

    @arg socket          Netlink socket
    @arg rx_buf_size     RX buffer size or 0 for default
    @arg tx_buf_size     TX buffer size or 0 for default
    """
    _nl_socket_set_buffer_size = _libnl('nl_socket_set_buffer_size',
                                        c_int, c_void_p, c_int, c_int)
    err = _nl_socket_set_buffer_size(socket, rx_buf_size, tx_buf_size)
    if err:
        raise IOError(-err, nl_geterror(err))


def nl_socket_get_fd(socket):
    """Return the file descriptor of the backing socket.

    @arg socket          Netlink socket

    Only valid after calling nl_connect() to create and bind the respective
    socket.

    @return File descriptor.
    """
    _nl_socket_get_fd = _libnl('nl_socket_get_fd', c_int, c_void_p)
    file_descriptor = _nl_socket_get_fd(socket)
    if file_descriptor == -1:
        raise IOError(get_errno(), 'Failed to obtain socket file descriptor.')
    return file_descriptor


def nl_socket_add_memberships(socket, *groups):
    """Join groups.

    @arg socket          Netlink socket
    @arg group           Group identifier
    """
    _nl_socket_add_memberships = _libnl(
        'nl_socket_add_memberships',
        c_int, c_void_p, *((c_int,) * (len(GROUPS) + 1)))
    err = _nl_socket_add_memberships(socket, *groups)
    if err:
        raise IOError(-err, nl_geterror(err))


def nl_socket_drop_memberships(socket, *groups):
    """Leave groups.

    @arg socket          Netlink socket
    @arg group           Group identifier
    """
    _nl_socket_drop_memberships = _libnl(
        'nl_socket_drop_memberships',
        c_int, c_void_p, *((c_int,) * (len(GROUPS) + 1)))
    err = _nl_socket_drop_memberships(socket, *groups)
    if err:
        raise IOError(-err, nl_geterror(err))


def nl_socket_modify_cb(socket, cb_type, kind, function, argument):
    """Modify the callback handler associated with the socket.

    @arg socket          Netlink socket.
    @arg cb_type         which type callback to set
    @arg kind            kind of callback
    @arg function        callback function (CFUNCTYPE)
    @arg argument        argument to be passed to callback function
    """
    _nl_socket_modify_cb = _libnl(
        'nl_socket_modify_cb',
        c_int, c_void_p, c_int, c_int, c_void_p, py_object)
    err = _nl_socket_modify_cb(socket, cb_type, kind, function, argument)
    if err:
        raise IOError(-err, nl_geterror(err))


def prepare_cfunction_for_nl_socket_modify_cb(function):
    """Prepare callback function for nl_socket_modify_cb.

    @arg                  Python function accepting two objects (message and
                          extra argument) as arguments and returns integer
                          with libnl callback action.

    @return C function prepared for nl_socket_modify_cb.
    """
    c_function = CFUNCTYPE(c_int, c_void_p, c_void_p)(function)
    return c_function


def nl_socket_disable_seq_check(socket):
    """Disable sequence number checking.

    @arg socket          Netlink socket.

    Disables checking of sequence numbers on the netlink socket This is
    required to allow messages to be processed which were not requested by
    a preceding request message, e.g. netlink events.
    """
    _nl_socket_disable_seq_check = _libnl(
        'nl_socket_disable_seq_check', c_void_p, c_void_p)
    _nl_socket_disable_seq_check(socket)


def nl_cache_get_first(cache):
    """Return the first element in the cache.

    @arg cache           cache handle

    @return the first element in the cache or None if empty
    """
    _nl_cache_get_first = _libnl('nl_cache_get_first', c_void_p, c_void_p)
    return _nl_cache_get_first(cache)


def nl_cache_get_next(element):
    """Return the next element in the cache

    @arg element         current element

    @return the next element in the cache or None if reached the end
    """
    _nl_cache_get_next = _libnl('nl_cache_get_next', c_void_p, c_void_p)
    return _nl_cache_get_next(element)


def nl_cache_free(cache):
    """Free a cache.

    @arg cache           Cache to free.

    Calls nl_cache_clear() to remove all objects associated with the
    cache and frees the cache afterwards.
    """
    _nl_cache_free = _libnl('nl_cache_free', None, c_void_p)
    _nl_cache_free(cache)


def nl_object_get_type(obj):
    """Return the object's type.

    @arg obj             object

    @return Name of the object type or None if not recognized
    """
    _nl_object_get_type = _libnl('nl_object_get_type', c_char_p, c_void_p)
    object_type = _nl_object_get_type(obj)
    return py2to3.to_str(object_type) if object_type else None


def nl_object_get_msgtype(obj):
    """Return the netlink message type the object was derived from.

    @arg obj             object

    @return Netlink message type code.
    """
    _nl_object_get_msgtype = _libnl('nl_object_get_msgtype', c_int, c_void_p)
    message_type = _nl_object_get_msgtype(obj)
    if message_type == 0:
        raise IOError(get_errno(), 'Failed to obtain message name.')
    return message_type


def nl_msg_parse(message, function, argument):
    """Parse message with given callback function.

    @arg message         netlink message
    @arg function        callback function (CFUNCTYPE)
    @arg argument        extra arguments
    """
    _nl_msg_parse = _libnl('nl_msg_parse', c_int, c_void_p, c_void_p, c_void_p)
    err = _nl_msg_parse(message, function, argument)
    if err:
        raise IOError(-err, nl_geterror(err))


def prepare_cfunction_for_nl_msg_parse(function):
    """Prepare callback function for nl_msg_parse.

    @arg                  Python function accepting two objects (netlink object
                          obtained from a message and extra argument) as
                          arguments.

    @return C function prepared for nl_msg_parse.
    """
    c_function = CFUNCTYPE(None, c_void_p, py_object)(function)
    return c_function


def nl_recvmsgs_default(socket):
    """Receive a set of message from a netlink socket using set handlers.

    @arg socket          Netlink socket.

    Calls nl_recvmsgs() with the handlers configured in the netlink socket.
    """
    _nl_recvmsgs_default = _libnl('nl_recvmsgs_default', c_int, c_void_p)
    err = _nl_recvmsgs_default(socket)
    if err:
        raise IOError(-err, nl_geterror(err))


def rtnl_addr_alloc_cache(socket):
    """Allocate new cache and fill it with addresses.

    @arg socket          Netlink socket

    @return Newly allocated cache with addresses obtained from kernel.
    """
    _rtnl_addr_alloc_cache = _libnl_route(
        'rtnl_addr_alloc_cache', c_int, c_void_p, c_void_p)
    cache = c_void_p()
    err = _rtnl_addr_alloc_cache(socket, byref(cache))
    if err:
        raise IOError(-err, nl_geterror(err))
    return cache


def rtnl_addr_get_ifindex(rtnl_address):
    """Return interface index of rtnl address device.

    @arg rtnl_address    Netlink rtnl address

    @return Interface index.
    """
    _rtnl_addr_get_ifindex = _libnl_route(
        'rtnl_addr_get_ifindex', c_int, c_void_p)
    return _rtnl_addr_get_ifindex(rtnl_address)


def rtnl_addr_get_family(rtnl_address):
    """Return address family code of rtnl address.

    @arg rtnl_address    Netlink rtnl address

    @return Address family code, can be translated to string via nl_af2str.
    """
    _rtnl_addr_get_family = _libnl_route(
        'rtnl_addr_get_family', c_int, c_void_p)
    return _rtnl_addr_get_family(rtnl_address)


def rtnl_addr_get_prefixlen(rtnl_address):
    """Return prefixlen of rtnl address.

    @arg rtnl_address    Netlink rtnl address

    @return Address network prefix length.
    """
    _rtnl_addr_get_prefixlen = _libnl_route(
        'rtnl_addr_get_prefixlen', c_int, c_void_p)
    return _rtnl_addr_get_prefixlen(rtnl_address)


def rtnl_addr_get_scope(rtnl_address):
    """Return scope code of rtnl address.

    @arg rtnl_address    Netlink rtnl address

    @return Address scope code, can be translated to string via rtnl_scope2str.
    """
    _rtnl_addr_get_scope = _libnl_route('rtnl_addr_get_scope', c_int, c_void_p)
    return _rtnl_addr_get_scope(rtnl_address)


def rtnl_addr_get_flags(rtnl_address):
    """Return flags bitfield of rtnl address.

    @arg rtnl_address    Netlink rtnl address

    @return Address flags, in bitfield format, can be translated to string
            via rtnl_addr_flags2str.
    """
    _rtnl_addr_get_flags = _libnl_route('rtnl_addr_get_flags', c_int, c_void_p)
    return _rtnl_addr_get_flags(rtnl_address)


def rtnl_addr_get_local(rtnl_address):
    """Return local nl address for rtnl address.

    @arg rtnl_address    Netlink rtnl address

    @return Local address (as nl address object).
    """
    _rtnl_addr_get_local = _libnl_route(
        'rtnl_addr_get_local', c_void_p, c_void_p)
    return _rtnl_addr_get_local(rtnl_address)


def rtnl_addr_flags2str(flags_bitfield):
    """Return string representation of address flags bitfield.

    @arg flags_bitfield  Bitfield of address' flags

    @return String represantion of given flags in format "flag1,flag2,flag3".
    """
    _rtnl_addr_flags2str = _libnl_route(
        'rtnl_addr_flags2str', c_char_p, c_int, c_char_p, c_size_t)
    buf = (c_char * (CHARBUFFSIZE * 2))()
    flags_str = _rtnl_addr_flags2str(flags_bitfield, buf, sizeof(buf))
    return py2to3.to_str(flags_str)


def rtnl_link_alloc_cache(socket, family):
    """Allocate link cache and fill in all configured links.

    @arg socket          Netlink socket.
    @arg family          Link address family or AF_UNSPEC

    If family is set to an address family other than AF_UNSPEC the
    contents of the cache can be limited to a specific address family.
    Currently the following address families are supported:
    - AF_BRIDGE
    - AF_INET6

    @return Newly allocated cache with links obtained from kernel.
    """
    _rtnl_link_alloc_cache = _libnl_route(
        'rtnl_link_alloc_cache', c_int, c_void_p, c_int, c_void_p)
    cache = c_void_p()
    err = _rtnl_link_alloc_cache(socket, family, byref(cache))
    if err:
        raise IOError(-err, nl_geterror(err))
    return cache


def rtnl_link_is_vlan(link):
    """Check if link is a VLAN link.

    @arg link            Link object

    @return True if link is a VLAN link, otherwise False is returned.
    """
    _rtnl_link_is_vlan = _libnl_route('rtnl_link_is_vlan', c_int, c_void_p)
    is_vlan = _rtnl_link_is_vlan(link)
    return bool(is_vlan)


def rtnl_link_vlan_get_id(link):
    """Get VLAN ID.

    @arg link            Link object

    @return VLAN ID.
    """
    _rtnl_link_vlan_get_id = _libnl_route(
        'rtnl_link_vlan_get_id', c_int, c_void_p)
    vlan_id = _rtnl_link_vlan_get_id(link)
    if vlan_id < 0:
        raise IOError(-vlan_id, nl_geterror(vlan_id))
    return vlan_id


def rtnl_link_get_type(link):
    """Return type of link.

    @arg link            Link object

    @return Name of link type or None if not specified.
    """
    _rtnl_link_get_type = _libnl_route(
        'rtnl_link_get_type', c_char_p, c_void_p)
    link_type = _rtnl_link_get_type(link)
    return py2to3.to_str(link_type) if link_type else None


def rtnl_link_get_kernel(socket, ifindex, ifname):
    """Get a link object directly from kernel.

    @arg socket          Netlink socket
    @arg ifindex         Interface index, use 0 if not to be used
    @arg ifname          Name of link, use None if not to be used

    Older kernels do not support lookup by name. In that case, libnl
    will fail with NLE_OPNOTSUPP. In case no matching link was found,
    fails with NLE_OBJ_NOTFOUND.

    @return Link object.
    """
    _rtnl_link_get_kernel = _libnl_route(
        'rtnl_link_get_kernel', c_int, c_void_p, c_int, c_char_p, c_void_p)
    link = c_void_p()
    b_ifname = py2to3.to_binary(ifname) if ifname else None
    err = _rtnl_link_get_kernel(socket, ifindex, b_ifname, byref(link))
    if err:
        raise IOError(-err, nl_geterror(err))
    return link


def rtnl_link_get_addr(link):
    """Return link layer address of link object.

    @arg link            Link object

    Use nl_addr2str to convert address object into a readable string.

    @return Link layer address or None if not set.
    """
    _rtnl_link_get_addr = _libnl_route(
        'rtnl_link_get_addr', c_void_p, c_void_p)
    return _rtnl_link_get_addr(link)


def rtnl_link_get_flags(link):
    """Return flags of link object.

    @arg link            Link object

    @return Link flags or None if none have been set.
    """
    _rtnl_link_get_flags = _libnl_route('rtnl_link_get_flags', c_int, c_void_p)
    return _rtnl_link_get_flags(link)


def rtnl_link_get_ifindex(link):
    """Return interface index of link object

    @arg link            Link object

    @return Interface index or None if not set.
    """
    _rtnl_link_get_ifindex = _libnl_route(
        'rtnl_link_get_ifindex', c_int, c_void_p)
    ifindex = _rtnl_link_get_ifindex(link)
    if ifindex == 0:
        return None
    return ifindex


def rtnl_link_get_link(link):
    """Return interface index of the underlying interface.

    @arg link            Master link object

    @return Underlying interface index if there is any, None otherwise.
    """
    _rtnl_link_get_link = _libnl_route('rtnl_link_get_link', c_int, c_void_p)
    underlying_ifindex = _rtnl_link_get_link(link)
    if underlying_ifindex == 0:
        return None
    return underlying_ifindex


def rtnl_link_get_master(link):
    """Return interface index of the master interface.

    @arg link            Underlying link object

    @return Master interface index if there is any, None otherwise.
    """
    _rtnl_link_get_master = _libnl_route(
        'rtnl_link_get_master', c_int, c_void_p)
    master_ifindex = _rtnl_link_get_master(link)
    if master_ifindex == 0:
        return None
    return master_ifindex


def rtnl_link_get_mtu(link):
    """Return maximum transmission unit of link object.

    @arg link            Link object

    @return MTU in bytes or None if not set
    """
    _rtnl_link_get_mtu = _libnl_route('rtnl_link_get_mtu', c_int, c_void_p)
    mtu = _rtnl_link_get_mtu(link)
    if mtu == 0:
        return None
    return mtu


def rtnl_link_get_name(link):
    """Return name of link object.

    @arg link            Link object

    @return Link name or None if name is not specified
    """
    _rtnl_link_get_name = _libnl_route(
        'rtnl_link_get_name', c_char_p, c_void_p)
    name = _rtnl_link_get_name(link)
    return py2to3.to_str(name) if name else None


def rtnl_link_get_operstate(link):
    """Return operational status code of link object.

    @arg link            Link object

    Use rtnl_link_operstate2str to convert operstate code to readable string.

    @return Opertional state code.
    """
    _rtnl_link_get_operstate = _libnl_route(
        'rtnl_link_get_operstate', c_int, c_void_p)
    return _rtnl_link_get_operstate(link)


def rtnl_link_get_qdisc(link):
    """Return name of queueing discipline of link object.

    @arg link            Link object

    @return Name of qdisc or None if not specified.
    """
    _rtnl_link_get_qdisc = _libnl_route(
        'rtnl_link_get_qdisc', c_char_p, c_void_p)
    qdisc = _rtnl_link_get_qdisc(link)
    return py2to3.to_str(qdisc) if qdisc else None


def rtnl_link_get_by_name(cache, name):
    """Lookup link in cache by link name

    @arg cache           Link cache
    @arg name            Name of link

    Searches through the provided cache looking for a link with matching
    link name

    @attention The reference counter of the returned link object will be
            incremented. Use rtnl_link_put() to release the reference.

    @return Link object or None if no match was found.
    """
    _rtnl_link_get_by_name = _libnl_route(
        'rtnl_link_get_by_name', c_void_p, c_void_p, c_char_p)
    return _rtnl_link_get_by_name(cache, name)


def rtnl_link_i2name(cache, ifindex):
    """Translate interface index to corresponding link name.

    @arg cache           Link cache
    @arg ifindex         Interface index

    Translates the specified interface index to the corresponding link name.

    @return Name of link or None if no match was found.
    """
    _rtnl_link_i2name = _libnl_route(
        'rtnl_link_i2name', c_char_p, c_void_p, c_int, c_char_p, c_size_t)
    buf = (c_char * CHARBUFFSIZE)()
    name = _rtnl_link_i2name(cache, ifindex, buf, sizeof(buf))
    return py2to3.to_str(name) if name else None


def rtnl_link_operstate2str(operstate_code):
    """Convert operstate code to string.

    @arg operstate_code  Operstate code.

    @return Operstate represented as string
    """
    _rtnl_link_operstate2str = _libnl_route(
        'rtnl_link_operstate2str', c_char_p, c_int, c_char_p, c_size_t)
    buf = (c_char * CHARBUFFSIZE)()
    operstate = _rtnl_link_operstate2str(operstate_code, buf, sizeof(buf))
    return py2to3.to_str(operstate)


def rtnl_link_put(link):
    """Destroy link object.

    @arg link            Link object
    """
    _rtnl_link_put = _libnl_route('rtnl_link_put', None, c_void_p)
    _rtnl_link_put(link)


def rtnl_route_alloc_cache(socket, family, flags):
    """Allocate route cache and fill in all configured routes.

    @arg socket          Netlink socket.
    @arg family          Address family of routes to cover or AF_UNSPEC
    @arg flags           Flags

    Valid flags:
      * ROUTE_CACHE_CONTENT - Cache will contain contents of routing cache
                              instead of actual routes.

    @note The caller is responsible for destroying and freeing the
          cache after using it.

    @return Newly allocated cache with routes obtained from kernel.
    """
    _rtnl_route_alloc_cache = _libnl_route(
        'rtnl_route_alloc_cache', c_int, c_void_p, c_int, c_int, c_void_p)
    cache = c_void_p()
    err = _rtnl_route_alloc_cache(socket, family, flags, byref(cache))
    if err:
        raise IOError(-err, nl_geterror(err))
    return cache


def rtnl_route_get_nnexthops(route):
    """Return number of next hops of given route.

    @arg route           Route object

    @return Number of next hops.
    """
    _rtnl_route_get_nnexthops = _libnl_route(
        'rtnl_route_get_nnexthops', c_int, c_void_p)
    return _rtnl_route_get_nnexthops(route)


def rtnl_route_nexthop_n(route, index):
    """Return next hop of given route.

    @arg route           Route object
    @arg index           Index of next hop, within rtnl_route_get_nnexthops

    @return Next hop object or None if there is None on given index.
    """
    _rtnl_route_get_nexthop_n = _libnl_route(
        'rtnl_route_nexthop_n', c_void_p, c_void_p, c_int)
    return _rtnl_route_get_nexthop_n(route, index)


def rtnl_route_get_dst(route):
    """Return destination nl address object.

    @arg route           Route object

    @return Destination address (as nl address object, can be converted to a
            readable string via nl_addr2str).
    """
    _rtnl_route_get_dst = _libnl_route(
        'rtnl_route_get_dst', c_void_p, c_void_p)
    return _rtnl_route_get_dst(route)


def rtnl_route_get_src(route):
    """Return source nl address object.

    @arg route           Route object

    @return Source address (as nl address object, can be converted to a
            readable string via nl_addr2str).
    """
    _rtnl_route_get_src = _libnl_route(
        'rtnl_route_get_src', c_void_p, c_void_p)
    return _rtnl_route_get_src(route)


def rtnl_route_get_iif(route):
    """Return input interface index.

    @arg route           Route object

    @return Input interface index (can be converted to a readable string via
            rtnl_link_get_name or rtnl_link_i2name).
    """
    _rtnl_route_get_iif = _libnl_route('rtnl_route_get_iif', c_int, c_void_p)
    return _rtnl_route_get_iif(route)


def rtnl_route_get_table(route):
    """Return route table number.

    @arg route           Route object

    @return Routing table number.
    """
    _rtnl_route_get_table = _libnl_route(
        'rtnl_route_get_table', c_int, c_void_p)
    return _rtnl_route_get_table(route)


def rtnl_route_get_scope(route):
    """Return route scope code.

    @arg route           Route object

    @return Route scope code (can be converted to a readable string via
            rtnl_scope2str).
    """
    _rtnl_route_get_scope = _libnl_route(
        'rtnl_route_get_scope', c_int, c_void_p)
    scope_code = _rtnl_route_get_scope(route)
    return scope_code


def rtnl_route_get_family(route):
    """Return route address family code.

    @arg route           Route object

    @return Address family code, can be translated to string via nl_af2str.
    """
    _rtnl_route_get_family = _libnl_route(
        'rtnl_route_get_family', c_int, c_void_p)
    return _rtnl_route_get_family(route)


def rtnl_route_nh_get_ifindex(next_hop):
    """Return next hop interface index.

    @arg next_hop        Next hop object

    @return Next hop interface index (can be converted to a readable string via
            rtnl_link_get_name or rtnl_link_i2name).
    """
    _rtnl_route_nh_get_ifindex = _libnl_route(
        'rtnl_route_nh_get_ifindex', c_int, c_void_p)
    return _rtnl_route_nh_get_ifindex(next_hop)


def rtnl_route_nh_get_gateway(next_hop):
    """Return next hop gateway as nl address object.

    @arg next_hop        Next hop object

    @return Gateway address (as nl address object, can be converted to a
            readable string via nl_addr2str).
    """
    _rtnl_route_nh_get_gateway = _libnl_route(
        'rtnl_route_nh_get_gateway', c_void_p, c_void_p)
    return _rtnl_route_nh_get_gateway(next_hop)


def c_object_argument(argument):
    """Prepare prepare Python object to be used as an C argument.

    @arg                  Python object.

    Reference to the returned object must be kept by caller as long as it might
    be used by any C binding function (beware of callback arguments).

    @return C object (py_object) prepared to be used as an C argument.
    """
    return py_object(argument)


@memoized
def _libnl(function_name, return_type, *arguments):
    return CFUNCTYPE(return_type, *arguments)((function_name, LIBNL))


@memoized
def _libnl_route(function_name, return_type, *arguments):
    return CFUNCTYPE(return_type, *arguments)((function_name, LIBNL_ROUTE))
