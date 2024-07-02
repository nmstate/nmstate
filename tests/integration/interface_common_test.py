# SPDX-License-Identifier: LGPL-2.1-or-later
from contextlib import contextmanager
import time

import pytest

import libnmstate
from libnmstate.error import NmstateValueError
from libnmstate.error import NmstateVerificationError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState

from .testlib import assertlib
from .testlib import cmdlib
from .testlib import statelib
from .testlib.apply import apply_with_description
from .testlib.genconf import gen_conf_apply


DUMMY_INTERFACE = "dummy_test"


@pytest.fixture(scope="function")
def ip_link_dummy():
    cmdlib.exec_cmd(["ip", "link", "add", DUMMY_INTERFACE, "type", "dummy"])
    try:
        yield
    finally:
        cmdlib.exec_cmd(["ip", "link", "del", DUMMY_INTERFACE])


@contextmanager
def dummy_interface(name):
    dummy_desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: name,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {InterfaceIPv4.ENABLED: False},
                Interface.IPV6: {InterfaceIPv6.ENABLED: False},
            }
        ]
    }
    apply_with_description(
        f"Bring up the interface {name}",
        dummy_desired_state,
    )
    try:
        yield dummy_desired_state
    finally:
        dummy_state = dummy_desired_state[Interface.KEY][0]
        dummy_state[Interface.STATE] = InterfaceState.ABSENT
        apply_with_description(
            f"Delete the interface {name}",
            dummy_desired_state,
        )


def test_iface_description_removal(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.DESCRIPTION] = "bar"
    apply_with_description(
        "Bring up eth1 interface and add the description 'bar'", desired_state
    )
    current_state = statelib.show_only(("eth1",))
    assert current_state[Interface.KEY][0][Interface.DESCRIPTION] == "bar"

    desired_state[Interface.KEY][0][Interface.DESCRIPTION] = ""
    libnmstate.apply(desired_state)
    current_state = statelib.show_only(("eth1",))
    assert Interface.DESCRIPTION not in current_state[Interface.KEY][0]


def test_iface_mac_address_lowercase(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.MAC] = "d4:ee:07:25:42:5a"
    apply_with_description(
        "Set the MAC address to d4:ee:07:25:42:5a for eth1 interface",
        desired_state,
    )
    current_state = statelib.show_only(("eth1",))
    assert (
        current_state[Interface.KEY][0][Interface.MAC] == "D4:EE:07:25:42:5A"
    )


def test_iface_mac_address_mixedcase(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.MAC] = "d4:EE:07:25:42:5a"
    apply_with_description(
        "Set the MAC address to d4:EE:07:25:42:5a for eth1 interface",
        desired_state,
    )
    current_state = statelib.show_only(("eth1",))
    assert (
        current_state[Interface.KEY][0][Interface.MAC] == "D4:EE:07:25:42:5A"
    )


def test_take_over_virtual_interface_then_remove(ip_link_dummy):
    with dummy_interface(DUMMY_INTERFACE) as dummy_desired_state:
        assertlib.assert_state_match(dummy_desired_state)

    current_state = statelib.show_only((DUMMY_INTERFACE,))
    assert len(current_state[Interface.KEY]) == 0


def test_take_over_virtual_interface_and_rollback(ip_link_dummy):
    with dummy_interface(DUMMY_INTERFACE) as dummy_desired_state:
        assertlib.assert_state_match(dummy_desired_state)

        dummy_desired_state[Interface.KEY][0]["invalid_key"] = "foo"
        with pytest.raises((NmstateVerificationError, NmstateValueError)):
            libnmstate.apply(dummy_desired_state)

        time.sleep(5)

        current_state = statelib.show_only((DUMMY_INTERFACE,))
        assert len(current_state[Interface.KEY]) == 1


def test_enable_and_disable_accept_all_mac_addresses(eth1_up):
    desired_state = eth1_up
    desired_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = True
    apply_with_description(
        "Enable accept all mac address for eth1 interface", desired_state
    )
    current_state = statelib.show_only(("eth1",))
    assert current_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES]

    desired_state[Interface.KEY][0][Interface.ACCEPT_ALL_MAC_ADDRESSES] = False
    apply_with_description(
        "Set accept all mac address to false for eth1 interface", desired_state
    )
    current_state = statelib.show_only(("eth1",))
    eth1_state = current_state[Interface.KEY][0]
    assert not eth1_state[Interface.ACCEPT_ALL_MAC_ADDRESSES]


def test_gen_conf_iface_description(eth1_up):
    desired_state = {
        Interface.KEY: [
            {
                Interface.NAME: "eth1",
                Interface.DESCRIPTION: "bar",
            }
        ]
    }
    with gen_conf_apply(desired_state):
        assertlib.assert_state_match(desired_state)
