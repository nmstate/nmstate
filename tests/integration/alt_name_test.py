# SPDX-License-Identifier: LGPL-2.1-or-later

import pytest

import libnmstate

from libnmstate.error import NmstateValueError

from .testlib.yaml import load_yaml
from .testlib.iproutelib import get_ip_link_alt_names
from .testlib.cmdlib import exec_cmd
from .testlib.retry import retry_till_true_or_timeout

TEST_ALT_NAMES = [
    "port1",
    "reallyreallylonglonglonginterfacenmae",
]

RETRY_TIMEOUT = 10


@pytest.fixture
def eth1_with_alt_names(eth1_up):
    desired_state = load_yaml(
        """---
        interfaces:
        - name: eth1
          type: ethernet
          state: up
          alt-names:
          - name: port1
          - name: reallyreallylonglonglonginterfacenmae
        """
    )
    libnmstate.apply(desired_state)
    yield
    libnmstate.apply(
        load_yaml(
            """---
            interfaces:
            - name: eth1
              type: ethernet
              state: up
              alt-names:
              - name: port1
                state: absent
              - name: reallyreallylonglonglonginterfacenmae
                state: absent
            """
        )
    )
    assert get_ip_link_alt_names("eth1") == []


# https://issues.redhat.com/browse/RHEL-90096
@pytest.mark.tier1
def test_add_and_remove_alt_name(eth1_with_alt_names):
    assert get_ip_link_alt_names("eth1") == TEST_ALT_NAMES


# https://issues.redhat.com/browse/RHEL-90096
@pytest.mark.tier1
def test_add_and_remove_extra_alt_name(eth1_with_alt_names):
    try:
        libnmstate.apply(
            load_yaml(
                """---
                interfaces:
                - name: eth1
                  type: ethernet
                  state: up
                  alt-names:
                  - name: extra_name
                """
            )
        )
        assert get_ip_link_alt_names("eth1") == sorted(
            [
                "extra_name",
            ]
            + TEST_ALT_NAMES
        )
    finally:
        libnmstate.apply(
            load_yaml(
                """---
                interfaces:
                - name: eth1
                  type: ethernet
                  state: up
                  alt-names:
                  - name: extra_name
                    state: absent
                """
            )
        )
        assert get_ip_link_alt_names("eth1") == TEST_ALT_NAMES


def test_alt_name_equal_to_iface_name(eth1_up):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            load_yaml(
                """---
                interfaces:
                - name: eth1
                  type: ethernet
                  state: up
                  alt-names:
                  - name: eth1
                """
            )
        )


def test_alt_name_not_unique_among_ifaces(eth1_up, eth2_up):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            load_yaml(
                """---
                        interfaces:
                        - name: eth1
                          type: ethernet
                          state: up
                          alt-names:
                          - name: port1
                        - name: eth2
                          type: ethernet
                          alt-names:
                          - name: port1
                        """
            )
        )


def test_alt_name_equal_to_other_nic_name(eth1_up, eth2_up):
    with pytest.raises(NmstateValueError):
        libnmstate.apply(
            load_yaml(
                """---
                    interfaces:
                    - name: eth1
                      type: ethernet
                      state: up
                      alt-names:
                      - name: eth2
                    - name: eth2
                      type: ethernet
                    """
            )
        )


# https://issues.redhat.com/browse/RHEL-90096
@pytest.mark.tier1
def test_validate_persistency_of_alt_name(eth1_with_alt_names):
    """
    Remove alt name by ip command and udevadm trigger should add it back.
    This simulate OS reboot.
    """
    exec_cmd("ip link property del eth1 altname port1".split(), check=True)
    exec_cmd(
        "ip link property del eth1 altname "
        "reallyreallylonglonglonginterfacenmae".split(),
        check=True,
    )

    retry_till_true_or_timeout(
        RETRY_TIMEOUT, udev_trigger_check_alt_names, "eth1", TEST_ALT_NAMES
    )


def udev_trigger_check_alt_names(iface_name, expected_alt_names):
    exec_cmd(
        "udevadm trigger --settle --action add "
        f"/sys/class/net/{iface_name}".split(" "),
        check=True,
    )

    return get_ip_link_alt_names(iface_name) == sorted(expected_alt_names)
