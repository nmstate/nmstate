# SPDX-License-Identifier: Apache-2.0

import pytest

from libnmstate.schema import Interface
from libnmstate.schema import LinuxBridge

from ..testlib.bridgelib import linux_bridge
from ..testlib.bridgelib import neigh_suppress_sysfs_value
from ..testlib.cmdlib import exec_cmd
from ..testlib.env import nm_version_int
from ..testlib.env import version_str_to_int
from ..testlib.vxlan import VxlanState
from ..testlib.vxlan import vxlan_interfaces


@pytest.mark.tier1
@pytest.mark.xfail(
    nm_version_int() <= version_str_to_int("1.58.1"),
    reason="neighbor-suppress requires NetworkManager > 1.58.1",
    strict=True,
)
def test_bridge_vxlan_neigh_suppress_persists_after_nm_reconnect(eth1_up):
    """Verify neigh_suppress survives an NM device reconnect.

    The ticket reports that 'bridge link set dev vxlan neigh_suppress on'
    fixes the flag temporarily, but the next NM reconnect or apply clears
    it. This test confirms that nmstate persists the flag in the NM
    connection profile so a reconnect keeps it set.
    """
    base_iface = eth1_up[Interface.KEY][0][Interface.NAME]

    vxlan = VxlanState(
        id=75101,
        base_if=base_iface,
        remote="192.0.2.1",
        learning=False,
    )

    bridge_name = "br-evpn"

    bridge_config = {
        LinuxBridge.PORT_SUBTREE: [
            {
                LinuxBridge.Port.NAME: vxlan.name,
                LinuxBridge.Port.NEIGH_SUPPRESS: True,
            }
        ],
        LinuxBridge.OPTIONS_SUBTREE: {
            LinuxBridge.STP_SUBTREE: {LinuxBridge.STP.ENABLED: False}
        },
    }

    with vxlan_interfaces(vxlan):
        with linux_bridge(bridge_name, bridge_config):
            assert neigh_suppress_sysfs_value(vxlan.name) == "1"

            connection_uuid = exec_cmd(
                (
                    "nmcli",
                    "-g",
                    "GENERAL.CON-UUID",
                    "device",
                    "show",
                    vxlan.name,
                ),
                check=True,
            )[1].strip()

            exec_cmd(
                ("nmcli", "connection", "down", "uuid", connection_uuid),
                check=True,
            )

            exec_cmd(
                ("nmcli", "connection", "up", "uuid", connection_uuid),
                check=True,
            )

            assert (
                neigh_suppress_sysfs_value(vxlan.name) == "1"
            ), "neigh_suppress was not restored after NM device reconnect"
