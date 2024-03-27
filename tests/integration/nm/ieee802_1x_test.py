# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2021 Red Hat, Inc.
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

import os

import pytest

import libnmstate
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Ieee8021X
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceState

from ..testlib import cmdlib
from ..testlib import assertlib
from ..testlib.env import is_k8s
from ..testlib.veth import create_veth_pair
from ..testlib.veth import remove_veth_pair
from ..testlib.statelib import show_only


TEST_1X_CLI_NIC = "1x_cli"
TEST_1X_SRV_NIC = "1x_srv"
TEST_1X_NET_NAME_SPACE = "test_802_1x"

CONF_DIR = (
    f"{os.path.dirname(os.path.realpath(__file__))}/../test_802.1x_srv_files"
)

HOSTAPD_CONF_PATH = "/etc/hostapd/nmstate_test.conf"
HOSTAPD_CONF_STR = f"""
interface={TEST_1X_SRV_NIC}
driver=wired
debug=2
ieee8021x=1
eap_reauth_period=3600
eap_server=1
use_pae_group_addr=1
eap_user_file={CONF_DIR}/hostapd.eap_user
ca_cert={CONF_DIR}/ca.crt
dh_file={CONF_DIR}/dh.pem
server_cert={CONF_DIR}/server.example.org.crt
private_key={CONF_DIR}/server.example.org.key
private_key_passwd=serverpass
"""

TEST_IDENTITY = "client.example.org"
TEST_CA_CERT = f"{CONF_DIR}/ca.crt"
TEST_CLIENT_CERT = f"{CONF_DIR}/client.example.org.crt"
TEST_PRIVATE_KEY = f"{CONF_DIR}/client.example.org.key"
TEST_PRIVATE_KEY_PASSWORD = "password"


@pytest.fixture
def ieee_802_1x_env():
    """
    Create a veth pair (CLI_NIC, SRV_NIC), and then run hostapd as 802.1x
    authenticator on SRV_NIC.
    """
    remove_veth_pair(TEST_1X_CLI_NIC, TEST_1X_NET_NAME_SPACE)
    create_veth_pair(TEST_1X_CLI_NIC, TEST_1X_SRV_NIC, TEST_1X_NET_NAME_SPACE)
    _start_802_1x_authenticator()
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: TEST_1X_CLI_NIC,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        },
        verify_change=False,
    )
    _stop_802_1x_authenticator()
    remove_veth_pair(TEST_1X_CLI_NIC, TEST_1X_NET_NAME_SPACE)


def _start_802_1x_authenticator():
    with open(HOSTAPD_CONF_PATH, "w") as fd:
        fd.write(HOSTAPD_CONF_STR)

    cmdlib.exec_cmd(
        f"ip netns exec {TEST_1X_NET_NAME_SPACE} hostapd -B "
        f"{HOSTAPD_CONF_PATH}".split(),
        check=True,
    )


def _stop_802_1x_authenticator():
    hostapd_pid = cmdlib.exec_cmd(["pidof", "hostapd"])[1]
    cmdlib.exec_cmd(["kill", hostapd_pid.strip()])


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=NmstateVerificationError,
    strict=False,
)
def test_eth_with_802_1x(ieee_802_1x_env):
    desire_state = {
        Interface.KEY: [
            {
                Interface.NAME: TEST_1X_CLI_NIC,
                Ieee8021X.CONFIG_SUBTREE: {
                    Ieee8021X.IDENTITY: TEST_IDENTITY,
                    Ieee8021X.EAP_METHODS: ["tls"],
                    Ieee8021X.PRIVATE_KEY: TEST_PRIVATE_KEY,
                    Ieee8021X.PRIVATE_KEY_PASSWORD: TEST_PRIVATE_KEY_PASSWORD,
                    Ieee8021X.CLIENT_CERT: TEST_CLIENT_CERT,
                    Ieee8021X.CA_CERT: TEST_CA_CERT,
                },
            }
        ]
    }

    libnmstate.apply(desire_state)

    # Even without 802.1x authenticated, the veth peer is still pingable.
    # So we just check NetworkManager has the 802.1x config
    assertlib.assert_state_match(desire_state)

    current_iface_state = show_only((TEST_1X_CLI_NIC,), include_secrets=True)[
        Interface.KEY
    ][0]

    assert (
        TEST_PRIVATE_KEY_PASSWORD
        == current_iface_state[Ieee8021X.CONFIG_SUBTREE][
            Ieee8021X.PRIVATE_KEY_PASSWORD
        ]
    )

    current_iface_state = show_only((TEST_1X_CLI_NIC,), include_secrets=False)[
        Interface.KEY
    ][0]
    assert (
        TEST_PRIVATE_KEY_PASSWORD
        != current_iface_state[Ieee8021X.CONFIG_SUBTREE][
            Ieee8021X.PRIVATE_KEY_PASSWORD
        ]
    )
    all_con_dev_pair = cmdlib.exec_cmd(
        "nmcli -g NAME,DEVICE connection show --active".split(), check=True
    )[1]
    for con_dev_pair in all_con_dev_pair.split("\n"):
        if TEST_1X_CLI_NIC in con_dev_pair:
            con_name = con_dev_pair.split(":")[0]
            assert len(
                cmdlib.exec_cmd(
                    ["nmcli", "-g", "802-1x", "c", "show", con_name],
                    check=True,
                )[1]
            )


@pytest.fixture
def ieee_1x_cli_up(ieee_802_1x_env):
    desire_state = {
        Interface.KEY: [
            {
                Interface.NAME: TEST_1X_CLI_NIC,
                Ieee8021X.CONFIG_SUBTREE: {
                    Ieee8021X.IDENTITY: TEST_IDENTITY,
                    Ieee8021X.EAP_METHODS: ["tls"],
                    Ieee8021X.PRIVATE_KEY: TEST_PRIVATE_KEY,
                    Ieee8021X.PRIVATE_KEY_PASSWORD: TEST_PRIVATE_KEY_PASSWORD,
                    Ieee8021X.CLIENT_CERT: TEST_CLIENT_CERT,
                    Ieee8021X.CA_CERT: TEST_CA_CERT,
                },
            }
        ]
    }

    libnmstate.apply(desire_state)


@pytest.mark.tier1
@pytest.mark.xfail(
    is_k8s(),
    reason=(
        "Requires adjusts for k8s. Ref:"
        "https://github.com/nmstate/nmstate/issues/1579"
    ),
    raises=NmstateVerificationError,
    strict=False,
)
def test_apply_ieee_802_1x_with_reserved_password(ieee_1x_cli_up):
    desire_state = show_only((TEST_1X_CLI_NIC,), include_secrets=False)

    libnmstate.apply(desire_state)

    current_iface_state = show_only((TEST_1X_CLI_NIC,), include_secrets=True)[
        Interface.KEY
    ][0]

    assert (
        TEST_PRIVATE_KEY_PASSWORD
        == current_iface_state[Ieee8021X.CONFIG_SUBTREE][
            Ieee8021X.PRIVATE_KEY_PASSWORD
        ]
    )
