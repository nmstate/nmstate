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
#

from libnmstate import state, metadata
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceType


OVS_NAME = "ovs-br99"
TYPE_OVS_BR = InterfaceType.OVS_BRIDGE


class TestDesiredStateOvsMetadata:
    def test_ovs_creation_with_new_ports(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    },
                    {"name": "eth0", "type": "unknown"},
                    {"name": "eth1", "type": "unknown"},
                ]
            }
        )
        current_state = state.State({})
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth0"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][0]
        expected_dstate.interfaces["eth1"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][1]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_creation_with_existing_ports(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {"name": "eth0", "state": "up", "type": "unknown"},
                    {"name": "eth1", "state": "up", "type": "unknown"},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {"name": "eth0", "state": "up"}
        expected_dstate.interfaces["eth0"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth1"] = {"name": "eth1", "state": "up"}
        expected_dstate.interfaces["eth1"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth0"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][0]
        expected_dstate.interfaces["eth1"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][1]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_editing_option(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {"name": OVS_NAME, "type": TYPE_OVS_BR, "state": "down"}
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    },
                    {"name": "eth0", "type": "unknown"},
                    {"name": "eth1", "type": "unknown"},
                ]
            }
        )
        expected_desired_state = state.State(desired_state.state)
        expected_current_state = state.State(current_state.state)

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_desired_state
        assert current_state == expected_current_state

    def test_ovs_adding_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    },
                    {"name": "eth1", "state": "up", "type": "unknown"},
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {"name": "eth0", "state": "up", "type": "unknown"}
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {"name": "eth0", "state": "up"}
        expected_dstate.interfaces["eth0"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth1"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth1"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth0"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][0]
        expected_dstate.interfaces["eth1"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][1]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_removing_slaves(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {"port": [{"name": "eth0"}]},
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    },
                    {"name": "eth0", "state": "up", "type": "ethernet"},
                    {"name": "eth1", "state": "up", "type": "ethernet"},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {"name": "eth0", "state": "up"}
        expected_dstate.interfaces["eth0"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth1"] = {"name": "eth1"}
        expected_dstate.interfaces["eth0"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS_NAME]["bridge"]["port"][0]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_edit_slave(self):
        desired_state = state.State(
            {
                Interface.KEY: [
                    {"name": "eth0", "type": "unknown", "fookey": "fooval"}
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    },
                    {"name": "eth0", "type": "unknown"},
                    {"name": "eth1", "type": "unknown"},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"][metadata.MASTER] = OVS_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth0"][
            metadata.BRPORT_OPTIONS
        ] = current_state.interfaces[OVS_NAME]["bridge"]["port"][0]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate

    def test_ovs_reusing_slave_used_by_existing_bridge(self):
        OVS2_NAME = "ovs-br88"
        desired_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS2_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {"port": [{"name": "eth0"}]},
                    }
                ]
            }
        )
        current_state = state.State(
            {
                Interface.KEY: [
                    {
                        "name": OVS_NAME,
                        "type": TYPE_OVS_BR,
                        "state": "up",
                        "bridge": {
                            "port": [{"name": "eth0"}, {"name": "eth1"}]
                        },
                    },
                    {"name": "eth0", "state": "up", "type": "unknown"},
                    {"name": "eth1", "state": "up", "type": "unknown"},
                ]
            }
        )
        expected_dstate = state.State(desired_state.state)
        expected_cstate = state.State(current_state.state)
        expected_dstate.interfaces["eth0"] = {"name": "eth0", "state": "up"}
        expected_dstate.interfaces["eth0"][metadata.MASTER] = OVS2_NAME
        expected_dstate.interfaces["eth0"][metadata.MASTER_TYPE] = TYPE_OVS_BR
        expected_dstate.interfaces["eth0"][
            metadata.BRPORT_OPTIONS
        ] = desired_state.interfaces[OVS2_NAME]["bridge"]["port"][0]

        metadata.generate_ifaces_metadata(desired_state, current_state)

        assert desired_state == expected_dstate
        assert current_state == expected_cstate
