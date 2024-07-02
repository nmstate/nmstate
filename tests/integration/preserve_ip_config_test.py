#
# Copyright (c) 2018-2020 Red Hat, Inc.
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
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState

from .testlib import statelib
from .testlib import cmdlib
from .testlib.apply import apply_with_description

_IPV4_EXTRA_CONFIG = "ipv4.dad-timeout"
_IPV4_EXTRA_VALUE = "0"
_IPV6_EXTRA_CONFIG = "ipv6.dhcp-hostname"
_IPV6_EXTRA_VALUE = "libnmstate.example.com"

IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"


def test_reapply_preserve_ip_config(eth1_up):
    apply_with_description(
        "Configure ethernet device eth1 to have the address "
        "192.0.2.251/24 and 2001:db8:1::1/64",
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            }
                        ],
                        InterfaceIPv4.ENABLED: True,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            }
                        ],
                        InterfaceIPv6.ENABLED: True,
                    },
                    Interface.MTU: 1500,
                }
            ]
        },
    )

    cur_state = statelib.show_only(("eth1",))
    iface_name = cur_state[Interface.KEY][0][Interface.NAME]

    for key, value in (
        (_IPV4_EXTRA_CONFIG, _IPV4_EXTRA_VALUE),
        (_IPV6_EXTRA_CONFIG, _IPV6_EXTRA_VALUE),
    ):
        with _extra_ip_config(iface_name, key, value):
            libnmstate.apply(cur_state)
            _assert_extra_ip_config(iface_name, key, value)


def _get_cur_extra_ip_config(profile_name, key):
    rc, output, _ = cmdlib.exec_cmd(
        ["nmcli", "--get-values", key, "connection", "show", profile_name]
    )
    assert rc == 0
    return output.split("\n")[0]


@contextmanager
def _extra_ip_config(iface_name, key, value):
    old_value = _get_cur_extra_ip_config(iface_name, key)
    _apply_extra_ip_config(iface_name, key, value)
    try:
        yield
    finally:
        _apply_extra_ip_config(iface_name, key, old_value)


def _apply_extra_ip_config(iface_name, key, value):
    assert (
        cmdlib.exec_cmd(
            ["nmcli", "connection", "modify", iface_name, key, value]
        )[0]
        == 0
    )


def _assert_extra_ip_config(iface_name, key, value):
    """
    Check whether extra config is touched by libnmstate.
    """
    cur_value = _get_cur_extra_ip_config(iface_name, key)
    assert cur_value == value
