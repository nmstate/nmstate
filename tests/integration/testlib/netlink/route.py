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
from functools import partial
from socket import AF_UNSPEC
import errno

from . import _cache_manager
from . import _pool
from . import libnl
from .link import _nl_link_cache, _link_index_to_name


def iter_routes():
    """Generator that yields an information dictionary for each route in the
    system."""
    with _pool.socket() as sock:
        with _nl_route_cache(sock) as route_cache:
            with _nl_link_cache(sock) as link_cache:  # for index to label
                route = libnl.nl_cache_get_first(route_cache)
                while route:
                    yield _route_info(route, link_cache=link_cache)
                    route = libnl.nl_cache_get_next(route)


def _route_info(route, link_cache=None):
    destination = libnl.rtnl_route_get_dst(route)
    source = libnl.rtnl_route_get_src(route)
    gateway = _rtnl_route_get_gateway(route)
    data = {
        'destination': libnl.nl_addr2str(destination),  # network
        'source': libnl.nl_addr2str(source) if source else None,
        'gateway': libnl.nl_addr2str(gateway) if gateway else None,  # via
        'family': libnl.nl_af2str(libnl.rtnl_route_get_family(route)),
        'table': libnl.rtnl_route_get_table(route),
        'scope': libnl.rtnl_scope2str(libnl.rtnl_route_get_scope(route))}
    oif_index = _rtnl_route_get_oif(route)
    if oif_index > 0:
        data['oif_index'] = oif_index
        try:
            data['oif'] = _link_index_to_name(oif_index, cache=link_cache)
        except IOError as err:
            if err.errno != errno.ENODEV:
                raise
    return data


def _rtnl_route_alloc_cache(sock):
    return libnl.rtnl_route_alloc_cache(sock, AF_UNSPEC, 0)


def _route_get_next_hop(route):
    if libnl.rtnl_route_get_nnexthops(route) != 1:
        return None
    return libnl.rtnl_route_nexthop_n(route, 0)


def _rtnl_route_get_oif(route):
    hop = _route_get_next_hop(route)
    if hop is None:
        return -1
    else:
        return libnl.rtnl_route_nh_get_ifindex(hop)


def _rtnl_route_get_gateway(route):
    hop = _route_get_next_hop(route)
    if hop is None:
        return None
    else:
        return libnl.rtnl_route_nh_get_gateway(hop)


_nl_route_cache = partial(_cache_manager, _rtnl_route_alloc_cache)
