# SPDX-License-Identifier: Apache-2.0

import json
import tempfile

import pytest
import yaml

from .testlib import cmdlib

APPLY_CMD = ["nmstatectl", "apply", "-k", "--no-verify"]
SHOW_CMD = ["nmstatectl", "show", "-k", "--json"]

BRIDGE0 = "br-test0"
PORT0 = "ovs-port0"
PORT1 = "ovs-port1"


def apply_kernel(state_dict):
    """Apply state via nmstatectl -k using a temp YAML file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(state_dict, f)
        f.flush()
        rc, out, err = cmdlib.exec_cmd(APPLY_CMD + [f.name])
    assert rc == 0, f"nmstatectl apply -k failed: {err}"


def show_kernel():
    """Show state via nmstatectl -k --json."""
    rc, out, err = cmdlib.exec_cmd(SHOW_CMD)
    assert rc == 0, f"nmstatectl show -k failed: {err}"
    return json.loads(out)


def cleanup_bridge(br_name):
    """Delete an OVS bridge via ovs-vsctl."""
    cmdlib.exec_cmd(["ovs-vsctl", "--if-exists", "del-br", br_name])


def _bridge_exists(br_name):
    rc, _, _ = cmdlib.exec_cmd(["ovs-vsctl", "br-exists", br_name])
    return rc == 0


def _find_iface(state, name):
    for iface in state.get("interfaces", []):
        if iface["name"] == name:
            return iface
    return None


@pytest.fixture
def bridge_cleanup():
    """Fixture that ensures cleanup of test bridge after test."""
    yield
    if _bridge_exists(BRIDGE0):
        cleanup_bridge(BRIDGE0)


class TestOvsKernelBridge:
    """OVS bridge CRUD via kernel-only (-k) mode."""

    def test_create_ovs_bridge_with_internal_port(self, bridge_cleanup):
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                        "options": {"stp": False},
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                    "ipv4": {"enabled": False},
                },
            ]
        }
        apply_kernel(state)

        # Verify with ovs-vsctl
        assert _bridge_exists(BRIDGE0)

        # Verify with nmstatectl show -k
        current = show_kernel()
        br_iface = _find_iface(current, BRIDGE0)
        assert br_iface is not None
        assert br_iface["type"] == "ovs-bridge"

    def test_delete_ovs_bridge(self, bridge_cleanup):
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)
        assert _bridge_exists(BRIDGE0)

        cleanup_bridge(BRIDGE0)
        assert not _bridge_exists(BRIDGE0)

    def test_ovs_bridge_with_stp(self, bridge_cleanup):
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                        "options": {"stp": True, "fail-mode": "secure"},
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)

        current = show_kernel()
        br = _find_iface(current, BRIDGE0)
        assert br is not None
        assert br["bridge"]["options"]["stp"] is True
        assert br["bridge"]["options"]["fail-mode"] == "secure"

    def test_ovs_bridge_mcast_snooping(self, bridge_cleanup):
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                        "options": {"mcast-snooping-enable": True},
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)

        current = show_kernel()
        br = _find_iface(current, BRIDGE0)
        assert br is not None
        assert br["bridge"]["options"]["mcast-snooping-enable"] is True

    def test_show_kernel_returns_ovs_topology(self, bridge_cleanup):
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [
                            {"name": PORT0},
                            {"name": PORT1},
                        ],
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
                {
                    "name": PORT1,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)

        current = show_kernel()
        br = _find_iface(current, BRIDGE0)
        assert br is not None
        port_names = [p["name"] for p in br["bridge"]["port"]]
        assert PORT0 in port_names
        assert PORT1 in port_names

    def test_update_bridge_options(self, bridge_cleanup):
        # Create bridge with STP disabled
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                        "options": {"stp": False},
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)

        # Update to enable STP
        update_state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                        "options": {"stp": True},
                    },
                },
            ]
        }
        apply_kernel(update_state)

        current = show_kernel()
        br = _find_iface(current, BRIDGE0)
        assert br is not None
        assert br["bridge"]["options"]["stp"] is True

    def test_add_port_to_existing_bridge(self, bridge_cleanup):
        # Create bridge with one port
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [{"name": PORT0}],
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)

        # Add a second port
        update_state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [
                            {"name": PORT0},
                            {"name": PORT1},
                        ],
                    },
                },
                {
                    "name": PORT1,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(update_state)

        current = show_kernel()
        br = _find_iface(current, BRIDGE0)
        assert br is not None
        port_names = [p["name"] for p in br["bridge"]["port"]]
        assert PORT0 in port_names
        assert PORT1 in port_names


class TestOvsKernelBond:
    """OVS bond via kernel-only (-k) mode."""

    @pytest.fixture
    def two_eth_ports(self):
        """
        Fixture that provides two ethernet port names for bonding.
        Override in CI with actual available interfaces.
        """
        rc, out, _ = cmdlib.exec_cmd(["nmstatectl", "show", "-k", "--json"])
        if rc != 0:
            pytest.skip("nmstatectl show -k failed")
        state = json.loads(out)
        eth_ifaces = [
            i["name"]
            for i in state.get("interfaces", [])
            if i.get("type") == "ethernet"
            and i["name"] not in ("lo",)
            and i.get("state") == "up"
        ]
        if len(eth_ifaces) < 2:
            pytest.skip("Need at least 2 ethernet interfaces for bond test")
        return eth_ifaces[0], eth_ifaces[1]

    def test_create_ovs_bridge_with_bond(self, bridge_cleanup, two_eth_ports):
        port0, port1 = two_eth_ports
        state = {
            "interfaces": [
                {
                    "name": BRIDGE0,
                    "type": "ovs-bridge",
                    "state": "up",
                    "bridge": {
                        "port": [
                            {
                                "name": "bond0",
                                "link-aggregation": {
                                    "mode": "balance-slb",
                                    "port": [
                                        {"name": port0},
                                        {"name": port1},
                                    ],
                                },
                            },
                            {"name": PORT0},
                        ],
                    },
                },
                {
                    "name": PORT0,
                    "type": "ovs-interface",
                    "state": "up",
                },
            ]
        }
        apply_kernel(state)

        current = show_kernel()
        br = _find_iface(current, BRIDGE0)
        assert br is not None
        bond_port = None
        for p in br["bridge"]["port"]:
            if p["name"] == "bond0":
                bond_port = p
                break
        assert bond_port is not None
        assert bond_port["link-aggregation"]["mode"] == "balance-slb"

        # Cleanup
        cleanup_bridge(BRIDGE0)
