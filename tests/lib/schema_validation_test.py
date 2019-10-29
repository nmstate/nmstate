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
import copy

import pytest

import jsonschema as js

import libnmstate
from libnmstate.schema import Constants
from libnmstate.schema import DNS
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType
from libnmstate.schema import LinuxBridge as LB
from libnmstate.schema import OVSBridge
from libnmstate.schema import RouteRule
from libnmstate.schema import Team
from libnmstate.schema import VXLAN


INTERFACES = Constants.INTERFACES
ROUTES = Constants.ROUTES
THE_BRIDGE = 'br0'
VXLAN0 = 'vxlan0'
TEAM0 = 'team0'

COMMON_DATA = {
    INTERFACES: [
        {
            'name': 'lo',
            'description': 'Loopback Interface',
            'type': 'unknown',
            'state': 'down',
            'link-speed': 1000,
            'mac-address': '12:34:56:78:90:ab',
            'mtu': 1500,
            # Read Only entries
            'if-index': 0,
            'admin-status': 'up',
            'link-status': 'down',
            'phys-address': '12:34:56:78:90:ab',
            'higher-layer-if': '',
            'lower-layer-if': '',
            'low-control': True,
            'statistics': {
                'in-octets': 0,
                'in-unicast-pkts': 0,
                'in-broadcast-pkts': 0,
                'in-multicast-pkts': 0,
                'in-discards': 0,
                'in-errors': 0,
                'out-octets': 0,
                'out-unicast-pkts': 0,
                'out-broadcast-pkts': 0,
                'out-multicast-pkts': 0,
                'out-discards': 0,
                'out-errors': 0,
            },
        }
    ],
    ROUTES: {
        'config': [
            {
                'table-id': 254,
                'metric': 100,
                'destination': '0.0.0.0/0',
                'next-hop-interface': 'eth0',
                'next-hop-address': '192.0.2.1',
            }
        ],
        'running': [
            {
                'table-id': 254,
                'metric': 100,
                'destination': '::/0',
                'next-hop-interface': 'eth0',
                'next-hop-address': 'fe80::1',
            }
        ],
    },
    RouteRule.KEY: {
        RouteRule.CONFIG: [
            {
                RouteRule.IP_FROM: '192.0.2.0/24',
                RouteRule.IP_TO: '198.51.100.0/24',
                RouteRule.PRIORITY: 500,
                RouteRule.ROUTE_TABLE: 254,
            }
        ]
    },
    DNS.KEY: {
        DNS.RUNNING: {
            DNS.SERVER: ["2001:db8::1", "192.0.2.1"],
            DNS.SEARCH: ["example.com", "example.org"],
        },
        DNS.CONFIG: {
            DNS.SERVER: ["2001:db8::1", "192.0.2.1"],
            DNS.SEARCH: ["example.com", "example.org"],
        },
    },
}


@pytest.fixture
def default_data():
    return copy.deepcopy(COMMON_DATA)


@pytest.fixture
def portless_bridge_state():
    return {
        Interface.NAME: THE_BRIDGE,
        Interface.STATE: 'up',
        Interface.TYPE: LB.TYPE,
        LB.CONFIG_SUBTREE: {LB.PORT_SUBTREE: []},
    }


@pytest.fixture
def bridge_state(portless_bridge_state):
    port = {LB.Port.NAME: 'eth1', LB.Port.VLAN_SUBTREE: {}}
    portless_bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE].append(port)
    return portless_bridge_state


@pytest.fixture
def portless_ovs_bridge_state():
    return {
        Interface.NAME: THE_BRIDGE,
        Interface.STATE: 'up',
        Interface.TYPE: OVSBridge.TYPE,
        LB.CONFIG_SUBTREE: {OVSBridge.PORT_SUBTREE: []},
    }


@pytest.fixture
def ovs_bridge_state(portless_ovs_bridge_state):
    port = {LB.Port.NAME: 'eth1', OVSBridge.Port.VLAN_SUBTREE: {}}
    ovs_bridge_state_config = portless_ovs_bridge_state[
        OVSBridge.CONFIG_SUBTREE
    ]
    ovs_bridge_state_config[OVSBridge.PORT_SUBTREE].append(port)
    return portless_ovs_bridge_state


class TestIfaceCommon(object):
    def test_valid_instance(self, default_data):
        libnmstate.validator.validate(default_data)

    def test_invalid_instance(self, default_data):
        default_data[INTERFACES][0]['state'] = 'bad-state'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'bad-state' in err.value.args[0]

    def test_invalid_type(self, default_data):
        default_data[INTERFACES][0]['type'] = 'bad-type'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'bad-type' in err.value.args[0]


class TestIfaceTypeEthernet(object):
    def test_valid_ethernet_with_auto_neg(self, default_data):
        default_data[INTERFACES][0].update(
            {'type': 'ethernet', 'auto-negotiation': True}
        )
        libnmstate.validator.validate(default_data)

    def test_valid_ethernet_without_auto_neg(self, default_data):
        default_data[INTERFACES][0].update(
            {'auto-negotiation': False, 'link-speed': 1000, 'duplex': 'full'}
        )
        libnmstate.validator.validate(default_data)

    def test_valid_without_auto_neg_and_missing_speed(self, default_data):
        """
        Defining autonegotiation as false and not specifying the link-speed is
        not a valid configuration, however, this is not handled by the schema
        at the moment, deferring the handling to the application code.
        """
        default_data[INTERFACES][0].update(
            {'type': 'ethernet', 'auto-negotiation': False}
        )
        del default_data[INTERFACES][0]['link-speed']

        libnmstate.validator.validate(default_data)

    @pytest.mark.parametrize('valid_values', [0, 150, 256])
    def test_valid_with_sriov_total_vfs(self, default_data, valid_values):
        default_data[Interface.KEY][0].update(
            {
                Interface.TYPE: InterfaceType.ETHERNET,
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: valid_values
                },
            }
        )
        libnmstate.validator.validate(default_data)

    @pytest.mark.parametrize('invalid_values', [-50, -1])
    def test_over_maximum_total_vfs_is_invalid(
        self, default_data, invalid_values
    ):
        default_data[Interface.KEY][0].update(
            {
                Interface.TYPE: InterfaceType.ETHERNET,
                Ethernet.SRIOV_SUBTREE: {
                    Ethernet.SRIOV.TOTAL_VFS: invalid_values
                },
            }
        )

        with pytest.raises(js.ValidationError, match=str(invalid_values)):
            libnmstate.validator.validate(default_data)


class TestIfaceTypeVxlan(object):
    def test_bad_id_type_is_invalid(self, default_data):
        default_data[Interface.KEY].append(
            {
                Interface.NAME: VXLAN0,
                Interface.TYPE: VXLAN.TYPE,
                VXLAN.CONFIG_SUBTREE: {
                    VXLAN.ID: 'badtype',
                    VXLAN.BASE_IFACE: 'eth1',
                    VXLAN.REMOTE: '192.168.3.3',
                },
            }
        )

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)

        assert '\'badtype\' is not of type \'integer\'' in err.value.args[0]

    def test_bad_id_range_is_invalid(self, default_data):
        default_data[Interface.KEY].append(
            {
                Interface.NAME: VXLAN0,
                Interface.TYPE: VXLAN.TYPE,
                VXLAN.CONFIG_SUBTREE: {
                    VXLAN.ID: 16777216,
                    VXLAN.BASE_IFACE: 'eth1',
                    VXLAN.REMOTE: '192.168.3.3',
                },
            }
        )

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)

        assert (
            '16777216 is greater than the maximum of 16777215'
            in err.value.args[0]
        )

    def test_no_config_is_valid(self, default_data):
        default_data[Interface.KEY].append(
            {Interface.NAME: VXLAN0, Interface.TYPE: VXLAN.TYPE}
        )

        libnmstate.validator.validate(default_data)


class TestIfaceTypeTeam(object):
    def test_valid_team_without_options(self, default_data):
        default_data[Interface.KEY].append(
            {
                Interface.NAME: TEAM0,
                Interface.TYPE: Team.TYPE,
                Team.CONFIG_SUBTREE: {},
            }
        )

        libnmstate.validator.validate(default_data)

    def test_valid_team_with_ports(self, default_data):
        default_data[Interface.KEY].append(
            {
                Interface.NAME: TEAM0,
                Interface.TYPE: Team.TYPE,
                Team.CONFIG_SUBTREE: {
                    Team.PORT_SUBTREE: [{Team.Port.NAME: 'eth1'}]
                },
            }
        )

        libnmstate.validator.validate(default_data)

    def test_valid_team_with_runner(self, default_data):
        default_data[Interface.KEY].append(
            {
                Interface.NAME: TEAM0,
                Interface.TYPE: Team.TYPE,
                Team.CONFIG_SUBTREE: {
                    Team.PORT_SUBTREE: [],
                    Team.RUNNER_SUBTREE: {
                        Team.Runner.NAME: Team.Runner.RunnerMode.LOAD_BALANCE
                    },
                },
            }
        )

        libnmstate.validator.validate(default_data)

    def test_valid_team_with_ports_and_runner(self, default_data):
        default_data[Interface.KEY].append(
            {
                Interface.NAME: TEAM0,
                Interface.TYPE: Team.TYPE,
                Team.CONFIG_SUBTREE: {
                    Team.PORT_SUBTREE: [{Team.Port.NAME: 'eth1'}],
                    Team.RUNNER_SUBTREE: {
                        Team.Runner.NAME: Team.Runner.RunnerMode.LOAD_BALANCE
                    },
                },
            }
        )

        libnmstate.validator.validate(default_data)


class TestRoutes(object):
    def test_valid_state_absent(self, default_data):
        default_data[ROUTES]['config'][0]['state'] = 'absent'
        libnmstate.validator.validate(default_data)

    def test_invalid_state(self, default_data):
        default_data[ROUTES]['config'][0]['state'] = 'bad-state'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'bad-state' in err.value.args[0]


class TestLinuxBridgeVlanFiltering(object):
    @pytest.mark.parametrize('port_type', argvalues=['trunk', 'access'])
    def test_vlan_port_types(self, default_data, bridge_state, port_type):
        valid_port_type = self._generate_vlan_filtering_config(port_type)
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(valid_port_type)
        default_data[Interface.KEY].append(bridge_state)

        libnmstate.validator.validate(default_data)

    def test_invalid_vlan_port_type(self, default_data, bridge_state):
        invalid_port_type = self._generate_vlan_filtering_config('fake-type')
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(invalid_port_type)
        default_data[Interface.KEY].append(bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        expected_error_msg = "'fake-type' is not one of ['trunk', 'access']"
        assert expected_error_msg in err.value.args[0]

    def test_access_port_accepted(self, default_data, bridge_state):
        vlan_access_port_state = self._generate_vlan_filtering_config(
            'access', access_tag=101
        )
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(vlan_access_port_state)
        default_data[Interface.KEY].append(bridge_state)

        libnmstate.validator.validate(default_data)

    def test_wrong_access_port_tag_type(self, default_data, bridge_state):
        invalid_access_port_tag_type = self._generate_vlan_filtering_config(
            'access', access_tag='holy-guacamole!'
        )
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(invalid_access_port_tag_type)
        default_data[Interface.KEY].append(bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        expected_error_msg = "'holy-guacamole!' is not of type 'integer'"
        assert expected_error_msg in err.value.args[0]

    def test_wrong_access_tag_range(self, default_data, bridge_state):
        invalid_vlan_id_range = self._generate_vlan_filtering_config(
            'access', access_tag=48000
        )
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(invalid_vlan_id_range)
        default_data[Interface.KEY].append(bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        expected_error_msg = '48000 is greater than the maximum of 4095'
        assert expected_error_msg in err.value.args[0]

    @pytest.mark.parametrize(
        'is_native_vlan', argvalues=[True, False], ids=['native', 'not-native']
    )
    def test_trunk_port_native_vlan(
        self, default_data, bridge_state, is_native_vlan
    ):
        vlan_access_port_state = self._generate_vlan_filtering_config(
            'trunk',
            access_tag=101 if is_native_vlan else None,
            native_vlan=is_native_vlan,
        )
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(vlan_access_port_state)
        default_data[Interface.KEY].append(bridge_state)

        libnmstate.validator.validate(default_data)

    def test_trunk_ports(self, default_data, bridge_state):
        trunk_tags = self._generate_vlan_id_config(101, 102, 103)
        trunk_tags.append(self._generate_vlan_id_range_config(500, 1000))
        vlan_trunk_tags_port_state = self._generate_vlan_filtering_config(
            'trunk', trunk_tags=trunk_tags
        )
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(vlan_trunk_tags_port_state)
        default_data[Interface.KEY].append(bridge_state)

        libnmstate.validator.validate(default_data)

    def test_invalid_trunk_port_vlan_range(self, default_data, bridge_state):
        invalid_port_vlan_configuration = self._generate_vlan_filtering_config(
            'trunk',
            trunk_tags=[self._generate_vlan_id_range_config(100, 5000)],
        )
        the_port = bridge_state[LB.CONFIG_SUBTREE][LB.PORT_SUBTREE][0]
        the_port.update(invalid_port_vlan_configuration)
        default_data[Interface.KEY].append(bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert '5000 is greater than the maximum of 4095' in err.value.args[0]

    @staticmethod
    def _generate_vlan_filtering_config(
        port_type, trunk_tags=None, access_tag=None, native_vlan=None
    ):
        vlan_filtering_state = {
            LB.Port.Vlan.MODE: port_type,
            LB.Port.Vlan.TRUNK_TAGS: trunk_tags or [],
        }

        if access_tag:
            vlan_filtering_state[LB.Port.Vlan.TAG] = access_tag
        if native_vlan:
            vlan_filtering_state[LB.Port.Vlan.ENABLE_NATIVE] = native_vlan

        return {LB.Port.VLAN_SUBTREE: vlan_filtering_state}

    @staticmethod
    def _generate_vlan_id_config(*vlan_ids):
        return [{LB.Port.Vlan.TrunkTags.ID: vlan_id} for vlan_id in vlan_ids]

    @staticmethod
    def _generate_vlan_id_range_config(min_vlan_id, max_vlan_id):
        return {
            LB.Port.Vlan.TrunkTags.ID_RANGE: {
                LB.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan_id,
                LB.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan_id,
            }
        }


class TestOvsBridgeVlan(object):
    @pytest.mark.parametrize('vlan_mode', argvalues=['trunk', 'access'])
    def test_vlan_port_modes(self, default_data, ovs_bridge_state, vlan_mode):
        valid_vlan_mode = self._generate_vlan_config(vlan_mode)
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(valid_vlan_mode)
        default_data[Interface.KEY].append(ovs_bridge_state)

        libnmstate.validator.validate(default_data)

    def test_invalid_vlan_port_mode(self, default_data, ovs_bridge_state):
        invalid_vlan_mode = self._generate_vlan_config('fake-mode')
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_vlan_mode)
        default_data[Interface.KEY].append(ovs_bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        expected_error_msg = "'fake-mode' is not one of ['trunk', 'access']"
        assert expected_error_msg in err.value.args[0]

    def test_access_port_accepted(self, default_data, ovs_bridge_state):
        vlan_access_port_state = self._generate_vlan_config(
            'access', access_tag=101
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(vlan_access_port_state)
        default_data[Interface.KEY].append(ovs_bridge_state)

        libnmstate.validator.validate(default_data)

    def test_wrong_access_port_tag_mode(self, default_data, ovs_bridge_state):
        invalid_access_port_tag_mode = self._generate_vlan_config(
            'access', access_tag='holy-guacamole!'
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_access_port_tag_mode)
        default_data[Interface.KEY].append(ovs_bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        expected_error_msg = "'holy-guacamole!' is not of type 'integer'"
        assert expected_error_msg in err.value.args[0]

    def test_wrong_access_tag_range(self, default_data, ovs_bridge_state):
        invalid_vlan_id_range = self._generate_vlan_config(
            'access', access_tag=48000
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_vlan_id_range)
        default_data[Interface.KEY].append(ovs_bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        expected_error_msg = '48000 is greater than the maximum of 4095'
        assert expected_error_msg in err.value.args[0]

    @pytest.mark.parametrize(
        'is_native_vlan', argvalues=[True, False], ids=['native', 'not-native']
    )
    def test_trunk_port_native_vlan(
        self, default_data, ovs_bridge_state, is_native_vlan
    ):
        vlan_access_port_state = self._generate_vlan_config(
            'trunk',
            access_tag=101 if is_native_vlan else None,
            native_vlan=is_native_vlan,
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(vlan_access_port_state)
        default_data[Interface.KEY].append(ovs_bridge_state)

        libnmstate.validator.validate(default_data)

    def test_trunk_ports(self, default_data, ovs_bridge_state):
        trunk_tags = self._generate_vlan_id_config(101, 102, 103)
        trunk_tags.append(self._generate_vlan_id_range_config(500, 1000))
        vlan_trunk_tags_port_state = self._generate_vlan_config(
            'trunk', trunk_tags=trunk_tags
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(vlan_trunk_tags_port_state)
        default_data[Interface.KEY].append(ovs_bridge_state)

        libnmstate.validator.validate(default_data)

    def test_invalid_trunk_port_vlan_range(
        self, default_data, ovs_bridge_state
    ):
        invalid_port_vlan_configuration = self._generate_vlan_config(
            'trunk',
            trunk_tags=[self._generate_vlan_id_range_config(100, 5000)],
        )
        bridge_state_config = ovs_bridge_state[OVSBridge.CONFIG_SUBTREE]
        the_port = bridge_state_config[OVSBridge.PORT_SUBTREE][0]
        the_port.update(invalid_port_vlan_configuration)
        default_data[Interface.KEY].append(ovs_bridge_state)

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert '5000 is greater than the maximum of 4095' in err.value.args[0]

    @staticmethod
    def _generate_vlan_config(
        vlan_mode, trunk_tags=None, access_tag=None, native_vlan=None
    ):
        vlan_state = {
            OVSBridge.Port.Vlan.MODE: vlan_mode,
            OVSBridge.Port.Vlan.TRUNK_TAGS: trunk_tags or [],
        }

        if access_tag:
            vlan_state[OVSBridge.Port.Vlan.TAG] = access_tag
        if native_vlan:
            enable_native = OVSBridge.Port.Vlan.ENABLE_NATIVE
            vlan_state[enable_native] = native_vlan

        return {OVSBridge.Port.VLAN_SUBTREE: vlan_state}

    @staticmethod
    def _generate_vlan_id_config(*vlan_ids):
        return [
            {OVSBridge.Port.Vlan.TrunkTags.ID: vlan_id} for vlan_id in vlan_ids
        ]

    @staticmethod
    def _generate_vlan_id_range_config(min_vlan_id, max_vlan_id):
        return {
            OVSBridge.Port.Vlan.TrunkTags.ID_RANGE: {
                OVSBridge.Port.Vlan.TrunkTags.MIN_RANGE: min_vlan_id,
                OVSBridge.Port.Vlan.TrunkTags.MAX_RANGE: max_vlan_id,
            }
        }


class TestRouteRules(object):
    def test_non_interger_route_table(self, default_data):
        route_rules = default_data[RouteRule.KEY][RouteRule.CONFIG]
        route_rules[0][RouteRule.ROUTE_TABLE] = 'main'

        with pytest.raises(js.ValidationError) as err:
            libnmstate.validator.validate(default_data)
        assert 'main' in err.value.args[0]


class TestOVSBridgeLinkAggregation:
    def test_valid_link_aggregation_port(self, default_data):
        link_aggregation_port = {
            OVSBridge.PORT_NAME: 'bond',
            OVSBridge.Port.LINK_AGGREGATION_SUBTREE: {
                OVSBridge.Port.LinkAggregation.MODE: 'bond-mode',
                OVSBridge.Port.LinkAggregation.SLAVES_SUBTREE: [
                    {OVSBridge.Port.LinkAggregation.Slave.NAME: 'iface1'},
                    {OVSBridge.Port.LinkAggregation.Slave.NAME: 'iface2'},
                ],
            },
        }
        default_data[Interface.KEY].append(
            {
                Interface.NAME: 'bridge',
                Interface.TYPE: InterfaceType.OVS_BRIDGE,
                OVSBridge.CONFIG_SUBTREE: {
                    OVSBridge.PORT_SUBTREE: [link_aggregation_port]
                },
            }
        )

        libnmstate.validator.validate(default_data)
