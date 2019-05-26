#
# Copyright 2016 Red Hat, Inc.
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
import logging

from . import monitor
from .link import get_link, is_link_up


@contextmanager
def waitfor_linkup(iface, oper_blocking=True, timeout=10):
    iface_up_check = _is_oper_up if oper_blocking else _is_admin_up
    with monitor.Monitor(groups=('link',), timeout=timeout,
                         silent_timeout=True) as mon:
        try:
            yield
        finally:
            if iface_up_check(iface):
                return
            for event in (e for e in mon if e.get('name') == iface):
                if is_link_up(event.get('flags', 0), oper_blocking):
                    return


@contextmanager
def waitfor_ipv4_addr(iface, address=None, timeout=10):
    """
    Silently block until an ipv4 global scope address message is detected from
    the kernel (through netlink).
    :param iface: The device name.
    :param address: Optional CIDR address expected - <address/bitmask>
                    Note that for a full mask(32) address, no mask is specified
    :param timeout: The maximum time in seconds to wait for the message.
    """
    expected_event = {'label': iface, 'family': 'inet', 'scope': 'global'}
    if address:
        expected_event.update(address=address)
    groups = ('ipv4-ifaddr',)
    with _wait_for_event(iface, expected_event, groups, timeout):
        yield


@contextmanager
def waitfor_ipv6_addr(iface, address=None, timeout=10):
    """
    Silently block until an ipv6 global scope address message is detected from
    the kernel (through netlink).
    :param iface: The device name.
    :param address: Optional CIDR address expected - <address/bitmask>
    :param timeout: The maximum time in seconds to wait for the message.
    """
    expected_event = {'label': iface, 'family': 'inet6', 'scope': 'global'}
    if address:
        expected_event.update(address=address)
    groups = ('ipv6-ifaddr',)
    with _wait_for_event(iface, expected_event, groups, timeout):
        yield


@contextmanager
def waitfor_link_exists(iface, timeout=0.5):
    """
    Silently block until a link is created/detected.
    :param iface: The device name.
    :param timeout: The maximum time in seconds to wait for the message.
    """
    expected_event = {'name': iface, 'event': 'new_link'}
    with _wait_for_link_event(iface, expected_event, timeout):
        yield


@contextmanager
def _wait_for_link_event(iface, expected_event, timeout):
    groups = ('link',)
    with _wait_for_event(iface, expected_event, groups, timeout):
        yield


@contextmanager
def _wait_for_event(iface, expected_event, groups, timeout):
    with monitor.Monitor(groups=groups, timeout=timeout) as mon:
        try:
            yield
        finally:
            caught_events = []
            try:
                for event in mon:
                    caught_events.append(event)
                    if _is_subdict(expected_event, event):
                        return
            except monitor.MonitorError as e:
                if e.args[0] == monitor.E_TIMEOUT:
                    logging.warning('Expected event "%s" of interface "%s" '
                                    'was not caught within %ssec. '
                                    'Caught events: %s',
                                    expected_event, iface, timeout,
                                    caught_events)
                else:
                    raise


def _is_subdict(subdict, superdict):
    return all(item in frozenset(superdict.items())
               for item in frozenset(subdict.items()))


def _is_admin_up(iface):
    return is_link_up(get_link(iface)['flags'], check_oper_status=False)


def _is_oper_up(iface):
    return is_link_up(get_link(iface)['flags'], check_oper_status=True)
