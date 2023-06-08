# SPDX-License-Identifier: LGPL-2.1-or-later

import libnmstate
from libnmstate.schema import Bond
from libnmstate.schema import BondMode
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6

from ..testlib import assertlib
from ..testlib import cmdlib
from ..testlib import statelib
from ..testlib.bondlib import bond_interface
from ..testlib.env import is_k8s
from ..testlib.env import nm_minor_version
from ..testlib.nmplugin import nm_service_restart
from ..testlib.retry import retry_till_true_or_timeout
from ..testlib.vlan import vlan_interface


BOND0 = "bondtest0"
TEST_VLAN = "bondtest.101"
TEST_VLAN_ID = 101
IPV4_ADDRESS1 = "192.0.2.251"
IPV6_ADDRESS1 = "2001:db8:1::1"
RETRY_TIMEOUT = 10

IGNORE_CARRIER_CFG_FILE = "/etc/NetworkManager/conf.d/ignore_carrier.conf"
IGNORE_CARRIER_CFG_CONTENT = """
[main]
ignore-carrier=no
"""


def test_bond_all_zero_ad_actor_system_been_ignored():
    extra_iface_state = {
        Bond.CONFIG_SUBTREE: {
            Bond.MODE: BondMode.LACP,
            Bond.OPTIONS_SUBTREE: {"ad_actor_system": "00:00:00:00:00:00"},
        }
    }
    with bond_interface(
        name=BOND0, port=[], extra_iface_state=extra_iface_state, create=True
    ):
        _, output, _ = cmdlib.exec_cmd(
            f"nmcli --fields bond.options c show {BOND0}".split(), check=True
        )
        assert "ad_actor_system" not in output

    assertlib.assert_absent(BOND0)


@pytest.fixture
def ignore_carrier_no():
    with open(IGNORE_CARRIER_CFG_FILE, "w") as fd:
        fd.write(IGNORE_CARRIER_CFG_CONTENT)
    with nm_service_restart():
        yield
        os.unlink(IGNORE_CARRIER_CFG_FILE)


@pytest.fixture
def vlan_over_bond_with_port_down(eth1_up, eth2_up):
    with bond_interface(name=BOND0, port=["eth1", "eth2"], create=True):
        with vlan_interface(TEST_VLAN, TEST_VLAN_ID, BOND0):
            vlan_iface = {
                Interface.NAME: TEST_VLAN,
                Interface.STATE: InterfaceState.UP,
                Interface.TYPE: InterfaceType.VLAN,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.DHCP: False,
                    InterfaceIPv4.ADDRESS: [
                        {
                            InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS1,
                            InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.DHCP: False,
                    InterfaceIPv6.AUTOCONF: False,
                    InterfaceIPv6.ADDRESS: [
                        {
                            InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS1,
                            InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            }
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: BOND0,
                            Interface.TYPE: InterfaceType.BOND,
                            Interface.STATE: InterfaceState.UP,
                        },
                        vlan_iface,
                    ]
                }
            )
            # Apply the simple configure again is the key reproducer
            libnmstate.apply(
                {
                    Interface.KEY: [
                        {
                            Interface.NAME: BOND0,
                            Interface.TYPE: InterfaceType.BOND,
                        },
                        vlan_iface,
                    ]
                }
            )
            assert retry_till_true_or_timeout(
                RETRY_TIMEOUT, vlan_is_up_with_ip
            )
            cmdlib.exec_cmd("ip link set eth1 down".split(), check=True)
            cmdlib.exec_cmd("ip link set eth2 down".split(), check=True)
            assert retry_till_true_or_timeout(
                RETRY_TIMEOUT, vlan_is_down_without_ip
            )
            yield


def vlan_is_down_without_ip():
    current_state = statelib.show_only((TEST_VLAN,))
    print(f"Current state {current_state}")
    iface_state = current_state[Interface.KEY][0]
    return (
        iface_state[Interface.IPV4][InterfaceIPv4.ENABLED] is False
        and iface_state[Interface.IPV6][InterfaceIPv6.ENABLED] is False
    )


def vlan_is_up_with_ip():
    current_state = statelib.show_only((TEST_VLAN,))
    print(f"Current state {current_state}")
    iface_state = current_state[Interface.KEY][0]
    return (
        iface_state[Interface.STATE] == InterfaceState.UP
        and len(iface_state[Interface.IPV4].get(InterfaceIPv4.ADDRESS, []))
        == 1
        # desired IPv6 address plus link local address
        and len(iface_state[Interface.IPV6].get(InterfaceIPv6.ADDRESS, []))
        == 2
    )


@pytest.mark.skipif(
    is_k8s(), reason="K8S cannot restart NetworkManager daemon"
)
@pytest.mark.tier1
# Will ping this xfail to a NM version once upstream patch merged and shipped
@pytest.mark.xfail(raises=AssertionError, strict=True)
# Detailed context is https://bugzilla.redhat.com/show_bug.cgi?id=2207690
def test_vlan_over_bond_reconnect_on_link_revive(
    ignore_carrier_no, vlan_over_bond_with_port_down
):
    cmdlib.exec_cmd("ip link set eth1 up".split(), check=True)
    cmdlib.exec_cmd("ip link set eth2 up".split(), check=True)
    assert retry_till_true_or_timeout(RETRY_TIMEOUT, vlan_is_up_with_ip)
