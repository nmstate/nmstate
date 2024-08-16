#
# Copyright (c) 2020 Red Hat, Inc.
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

from contextlib import contextmanager
import os
import time
import yaml

import pytest

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import LLDP

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import ifacelib
from .testlib import statelib
from .testlib.apply import apply_with_description
from .testlib.veth import create_veth_pair
from .testlib.veth import remove_veth_pair


LLDPTEST = "lldptest"
LLDPTEST_PEER = "lldptest.peer"

LLDP_TEST_NS = "nmstate_lldp_test"

LLDP_SYSTEM_DESC = (
    "Summit300-48 - Version 7.4e.1 (Build 5) by Release_Master "
    "05/27/05 04:53:11"
)

EXPECTED_LLDP_NEIGHBOR = """
- system-name: Summit300-48
  type: 5
- system-description: Summit300-48 - Version 7.4e.1 (Build 5) by Release_Master
    05/27/05 04:53:11
  type: 6
- system-capabilities:
  - MAC Bridge component
  - Router
  type: 7
- _description: MAC address
  chassis-id: 00:01:30:F9:AD:A0
  chassis-id-type: 4
  type: 1
- _description: Interface name
  port-id: 1/1
  port-id-type: 5
  type: 2
- ieee-802-1-vlans:
  - name: v2-0488-03-0505
    vid: 488
  oui: 00:80:c2
  subtype: 3
  type: 127
- ieee-802-3-mac-phy-conf:
    autoneg: true
    operational-mau-type: 16
    pmd-autoneg-cap: 27648
  oui: 00:12:0f
  subtype: 1
  type: 127
- ieee-802-1-ppvids:
  - 0
  oui: 00:80:c2
  subtype: 2
  type: 127
- management-addresses:
  - address: 00:01:30:F9:AD:A0
    address-subtype: MAC
    interface-number: 1001
    interface-number-subtype: 2
  type: 8
- ieee-802-3-max-frame-size: 1522
  oui: 00:12:0f
  subtype: 4
  type: 127
"""

LLDP_CAPS = ["MAC Bridge component", "Router"]

CHASSIS_ID = "chassis-id"
CHASSIS_ID_TYPE = "chassis-id-type"
MANAGEMENT_ADDRESSES = "management-addresses"
ADDRESS = "address"
ADDRESS_SUBTYPE = "address-subtype"
INTERFACE_NUMBER = "interface-number"
INTERFACE_NUMBER_SUBTYPE = "interface-number-subtype"
AUTONEG = "autoneg"
OPERATIONAL_MAU_TYPE = "operational-mau-type"
PMD_AUTONEG_CAP = "pmd-autoneg-cap"
PPVIDS_SUBTREE = "ieee-802-1-ppvids"
PPVID = "ppvid"
VLANS_SUBTREE = "ieee-802-1-vlans"
NAME = "name"
PORT_ID = "port-id"
PORT_ID_TYPE = "port-id-type"
SYSTEM_NAME = "system-name"
SYSTEM_DESCRIPTION = "system-description"
SYSTEM_CAPABILITIES = "system-capabilities"
MFS_KEY = "ieee-802-3-max-frame-size"
MAC_PHY_SUBTREE = "ieee-802-3-mac-phy-conf"

LLDP_TEST_SYSTEM_NAME = "Summit300-48"


@pytest.fixture(scope="module")
def lldpiface_env():
    try:
        create_veth_pair(LLDPTEST, LLDPTEST_PEER, LLDP_TEST_NS)
        yield
    finally:
        remove_veth_pair(LLDPTEST, LLDP_TEST_NS)


@pytest.fixture
def lldptest_up(lldpiface_env):
    with ifacelib.iface_up(LLDPTEST) as ifstate:
        yield ifstate


def test_enable_lldp(lldptest_up):
    with lldp_enabled(lldptest_up) as dstate:
        assertlib.assert_state_match(dstate)


def test_lldp_yaml(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]
        assert test_neighbor == yaml.safe_load(EXPECTED_LLDP_NEIGHBOR)


def test_lldp_system(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        seen = set()
        for tlv in test_neighbor:
            seen.add(tlv[LLDP.Neighbors.TLV_TYPE])
            if tlv[LLDP.Neighbors.TLV_TYPE] == 5:
                assert tlv[SYSTEM_NAME] == "Summit300-48"
            elif tlv[LLDP.Neighbors.TLV_TYPE] == 6:
                assert tlv[SYSTEM_DESCRIPTION] == LLDP_SYSTEM_DESC
            elif tlv[LLDP.Neighbors.TLV_TYPE] == 7:
                assert tlv[SYSTEM_CAPABILITIES] == LLDP_CAPS
        assert set([5, 6, 7]).issubset(seen)


def test_lldp_chassis(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 1, test_neighbor
            )
        )
        assert len(tlvs) == 1
        assert tlvs[0][CHASSIS_ID] == "00:01:30:F9:AD:A0"
        assert tlvs[0][CHASSIS_ID_TYPE] == 4


def test_lldp_management_addresses(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 8, test_neighbor
            )
        )
        assert len(tlvs) == 1
        test_mngt = tlvs[0][MANAGEMENT_ADDRESSES][0]
        assert test_mngt[ADDRESS] == "00:01:30:F9:AD:A0"
        assert test_mngt[ADDRESS_SUBTYPE] == "MAC"
        assert test_mngt[INTERFACE_NUMBER] == 1001
        assert test_mngt[INTERFACE_NUMBER_SUBTYPE] == 2


def test_lldp_macphy(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 127
                and tlv[LLDP.Neighbors.ORGANIZATION_CODE] == "00:12:0f"
                and tlv[LLDP.Neighbors.TLV_SUBTYPE] == 1,
                test_neighbor,
            )
        )
        assert len(tlvs) == 1
        assert tlvs[0][MAC_PHY_SUBTREE][AUTONEG] is True
        assert tlvs[0][MAC_PHY_SUBTREE][OPERATIONAL_MAU_TYPE] == 16
        assert tlvs[0][MAC_PHY_SUBTREE][PMD_AUTONEG_CAP] == 27648


def test_lldp_port(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 2, test_neighbor
            )
        )
        assert len(tlvs) == 1
        assert tlvs[0][PORT_ID] == "1/1"
        assert tlvs[0][PORT_ID_TYPE] == 5
        assert tlvs[0][LLDP.Neighbors.DESCRIPTION] == "Interface name"


def test_lldp_port_vlan(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 127
                and tlv[LLDP.Neighbors.ORGANIZATION_CODE] == "00:80:c2"
                and tlv[LLDP.Neighbors.TLV_SUBTYPE] == 2,
                test_neighbor,
            )
        )
        assert len(tlvs) == 1
        assert tlvs[0][PPVIDS_SUBTREE][0] == 0


def test_lldp_vlan(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 127
                and tlv[LLDP.Neighbors.ORGANIZATION_CODE] == "00:80:c2"
                and tlv[LLDP.Neighbors.TLV_SUBTYPE] == 3,
                test_neighbor,
            )
        )
        assert len(tlvs) == 1
        test_vlan = tlvs[0][VLANS_SUBTREE][0]
        assert test_vlan[NAME] == "v2-0488-03-0505"


def test_lldp_mfs(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        test_neighbor = lldp_config[LLDP.NEIGHBORS_SUBTREE][0]

        tlvs = list(
            filter(
                lambda tlv: tlv[LLDP.Neighbors.TLV_TYPE] == 127
                and tlv[LLDP.Neighbors.ORGANIZATION_CODE] == "00:12:0f"
                and tlv[LLDP.Neighbors.TLV_SUBTYPE] == 4,
                test_neighbor,
            )
        )
        assert len(tlvs) == 1
        assert tlvs[0][MFS_KEY] == 1522


def test_lldp_empty_neighbors(lldptest_up):
    with lldp_enabled(lldptest_up):
        dstate = statelib.show_only((LLDPTEST,))
        lldp_state = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert not lldp_state.get(LLDP.NEIGHBORS_SUBTREE, [])


def test_show_running_config_has_no_lldp_neighbor(lldptest_up):
    with lldp_enabled(lldptest_up):
        _send_lldp_packet()
        dstate = statelib.show_only((LLDPTEST,))
        lldp_config = dstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
        assert len(lldp_config[LLDP.NEIGHBORS_SUBTREE]) == 1
        running_config = libnmstate.show_running_config()
        for iface_config in running_config[Interface.KEY]:
            if iface_config[Interface.NAME] == LLDPTEST:
                lldp_iface_config = iface_config
                break
        assert lldp_iface_config[LLDP.CONFIG_SUBTREE][LLDP.ENABLED]
        assert (
            LLDP.NEIGHBORS_SUBTREE
            not in lldp_iface_config[LLDP.CONFIG_SUBTREE]
        )


@contextmanager
def lldp_enabled(ifstate):
    lldp_config = ifstate[Interface.KEY][0][LLDP.CONFIG_SUBTREE]
    lldp_config[LLDP.ENABLED] = True
    apply_with_description(
        "Configure the ethernet device lldptest with lldp enabled", ifstate
    )
    try:
        yield ifstate
    finally:
        lldp_config[LLDP.ENABLED] = False
        apply_with_description(
            "Set up the ethernet device lldptest with lldp disabled", ifstate
        )


def _send_lldp_packet():
    test_dir = os.path.dirname(os.path.realpath(__file__))
    cmdlib.exec_cmd(
        f"ip netns exec {LLDP_TEST_NS} "
        f"tcpreplay --intf1={LLDPTEST_PEER} "
        f"{test_dir}/test_captures/lldp.pcap".split(),
        check=True,
    )
    time.sleep(1)
