#
# Copyright (c) 2018-2019 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from contextlib import contextmanager

import libnmstate
from libnmstate.nm import nmclient

from .testlib import statelib
from .testlib import cmd as libcmd
from .testlib.statelib import INTERFACES

_IPV4_EXTRA_CONFIG = 'ipv4.dad-timeout'
_IPV4_EXTRA_VALUE = '0'
_IPV6_EXTRA_CONFIG = 'ipv6.dhcp-hostname'
_IPV6_EXTRA_VALUE = 'libnmstate.example.com'

IPV4_ADDRESS1 = '192.0.2.251'
IPV6_ADDRESS1 = '2001:db8:1::1'


def test_reapply_preserve_ip_config(eth1_up):
    libnmstate.apply(
        {
            'interfaces': [
                {
                    'name': 'eth1',
                    'type': 'ethernet',
                    'state': 'up',
                    'ipv4': {
                        'address': [
                            {'ip': IPV4_ADDRESS1, 'prefix-length': 24}
                        ],
                        'enabled': True,
                    },
                    'ipv6': {
                        'address': [
                            {'ip': IPV6_ADDRESS1, 'prefix-length': 64}
                        ],
                        'enabled': True,
                    },
                    'mtu': 1500,
                }
            ]
        }
    )
    cur_state = statelib.show_only(('eth1',))
    iface_name = cur_state[INTERFACES][0]['name']

    uuid = _get_nm_profile_uuid(iface_name)

    for key, value in (
        (_IPV4_EXTRA_CONFIG, _IPV4_EXTRA_VALUE),
        (_IPV6_EXTRA_CONFIG, _IPV6_EXTRA_VALUE),
    ):
        with _extra_ip_config(uuid, key, value):
            libnmstate.apply(cur_state)
            _assert_extra_ip_config(uuid, key, value)


def _get_nm_profile_uuid(iface_name):
    nmcli = nmclient.client()
    cur_dev = None
    for dev in nmcli.get_all_devices():
        if dev.get_iface() == iface_name:
            cur_dev = dev
            break

    active_conn = cur_dev.get_active_connection()
    return active_conn.get_uuid()


def _get_cur_extra_ip_config(uuid, key):
    rc, output, _ = libcmd.exec_cmd(
        ['nmcli', '--get-values', key, 'connection', 'show', uuid]
    )
    assert rc == 0
    return output.split('\n')[0]


@contextmanager
def _extra_ip_config(uuid, key, value):
    old_value = _get_cur_extra_ip_config(uuid, key)
    _apply_extra_ip_config(uuid, key, value)
    try:
        yield
    finally:
        _apply_extra_ip_config(uuid, key, old_value)


def _apply_extra_ip_config(uuid, key, value):
    assert (
        libcmd.exec_cmd(['nmcli', 'connection', 'modify', uuid, key, value])[0]
        == 0
    )


def _assert_extra_ip_config(uuid, key, value):
    """
    Check whether extra config is touched by libnmstate.
    """
    cur_value = _get_cur_extra_ip_config(uuid, key)
    assert cur_value == value
