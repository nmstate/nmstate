#
# Copyright (c) 2022 Red Hat, Inc.
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

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState

from ..testlib import cmdlib

NM_TEST_ID = "test_eth1"
NM_TEST_UUID = "067490bf-95fd-45ed-b32c-228713d8080d"
TEST_TRUE_VALUES = ["True", "true", True, "yes", "y", "1", 1]
TEST_FALSE_VALUES = ["False", "false", False, "no", "n", "0", 0]


def test_nm_backend_specific_setting_uuid_id(eth1_up):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.STATE: InterfaceState.UP,
                    Interface.BACKEND_SPECIFIC: {
                        "networkmanager": {
                            "connection.id": NM_TEST_ID,
                            "connection.uuid": NM_TEST_UUID,
                        }
                    },
                }
            ]
        }
    )
    cmdlib.exec_cmd(f"nmcli c show {NM_TEST_ID}".split(), check=True)
    cmdlib.exec_cmd(f"nmcli c show {NM_TEST_UUID}".split(), check=True)


@pytest.mark.tier1
@pytest.mark.parametrize(
    "may_fail_value", TEST_TRUE_VALUES + TEST_FALSE_VALUES
)
def test_nm_backend_specific_may_fail(eth1_up, may_fail_value):
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: "eth1",
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.DHCP: True,
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.DHCP: True,
                        InterfaceIPv6.AUTOCONF: True,
                    },
                    Interface.BACKEND_SPECIFIC: {
                        "networkmanager": {
                            "ipv4.may-fail": may_fail_value,
                            "ipv6.may-fail": may_fail_value,
                        }
                    },
                }
            ]
        }
    )
    if may_fail_value in TEST_TRUE_VALUES:
        expected_nm_value = "yes"
    else:
        expected_nm_value = "no"

    assert (
        cmdlib.exec_cmd(
            f"nmcli -g ipv4.may-fail c show eth1".split(), check=True
        )[1].strip()
        == expected_nm_value
    )
    assert (
        cmdlib.exec_cmd(
            f"nmcli -g ipv6.may-fail c show eth1".split(), check=True
        )[1].strip()
        == expected_nm_value
    )
