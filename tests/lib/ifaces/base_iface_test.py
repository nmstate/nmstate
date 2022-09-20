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

from copy import deepcopy

import pytest

from libnmstate.error import NmstateInternalError
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState

from libnmstate.ifaces.base_iface import BaseIface
from ..testlib.constants import MAC_ADDRESS1
from ..testlib.constants import IPV6_LINK_LOCAL_ADDRESS1
from ..testlib.constants import IPV4_ADDRESS3
from ..testlib.constants import IPV4_ADDRESSES
from ..testlib.constants import IPV6_ADDRESSES
from ..testlib.constants import IPV6_ADDRESS3
from ..testlib.ifacelib import gen_foo_iface_info


class TestBaseIface:
    def test_merge(self):
        des_info = gen_foo_iface_info()
        des_info.update(
            {"list_a": [], "dict_b": {"item_a": 1, "dict_c": {"item_b": 2}}}
        )
        cur_info = gen_foo_iface_info()
        cur_info.update(
            {
                "state": "up",
                "list_a": ["a", "b", "c"],
                "dict_b": {
                    "item_a1": 11,
                    "dict_c": {"item_b": 3, "item_d": 4},
                },
            }
        )
        ori_cur_info = deepcopy(cur_info)
        ori_des_info = deepcopy(des_info)
        des_iface = BaseIface(des_info)
        cur_iface = BaseIface(cur_info)
        des_iface.merge(cur_iface)

        expected_info = gen_foo_iface_info()
        expected_info.update(
            {
                "list_a": [],
                "dict_b": {
                    "item_a": 1,
                    "item_a1": 11,
                    "dict_c": {"item_b": 2, "item_d": 4},
                },
            }
        )

        assert cur_info == ori_cur_info
        assert des_info == ori_des_info
        assert cur_iface.to_dict() == ori_cur_info
        assert des_iface.to_dict() == expected_info

    def test_do_not_merge_down_state_from_current(self):
        iface_info = gen_foo_iface_info()
        cur_iface_info = gen_foo_iface_info()
        iface_info.pop(Interface.STATE)
        cur_iface_info[Interface.STATE] = InterfaceState.DOWN

        iface = BaseIface(iface_info)
        cur_iface = BaseIface(cur_iface_info)

        iface.merge(cur_iface)

        assert iface.is_up

    def test_capitalize_mac(self):
        iface_info = gen_foo_iface_info()
        iface_info.update({Interface.MAC: MAC_ADDRESS1})

        expected_info = deepcopy(iface_info)
        iface_info[Interface.MAC] = iface_info[Interface.MAC].lower()

        iface = BaseIface(iface_info)

        assert iface.state_for_verify() == expected_info

    def test_iface_match_other_has_more(self):
        iface = BaseIface(gen_foo_iface_info())
        other_iface_info = gen_foo_iface_info()
        other_iface_info["foo_a"] = "b"
        other_iface = BaseIface(other_iface_info)

        assert iface.match(other_iface)

    def test_iface_match_other_has_less(self):
        iface_info = gen_foo_iface_info()
        iface_info["foo_a"] = "b"
        iface = BaseIface(iface_info)
        other_iface = BaseIface(gen_foo_iface_info())

        assert not iface.match(other_iface)

    def test_iface_match_other_has_diff(self):
        iface_info = gen_foo_iface_info()
        iface_info["foo_a"] = "b"
        iface = BaseIface(iface_info)
        other_iface_info = gen_foo_iface_info()
        other_iface_info["foo_a"] = "c"
        other_iface = BaseIface(other_iface_info)

        assert not iface.match(other_iface)

    def test_state_for_verify_remove_link_local_address(self):
        iface_info = gen_foo_iface_info()
        ipv6_info = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: IPV6_ADDRESSES,
        }
        iface_info[Interface.IPV6] = ipv6_info
        expected_iface_info = deepcopy(iface_info)

        iface_info[Interface.IPV6][InterfaceIPv6.ADDRESS].append(
            {
                InterfaceIPv6.ADDRESS_IP: IPV6_LINK_LOCAL_ADDRESS1,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        )
        iface = BaseIface(iface_info)

        assert iface.state_for_verify() == expected_iface_info

    def test_state_for_verify_empty_description(self):
        iface_info = gen_foo_iface_info()
        expected_iface_info = deepcopy(iface_info)

        iface_info[Interface.DESCRIPTION] = ""

        iface = BaseIface(iface_info)

        assert iface.state_for_verify() == expected_iface_info

    def test_state_for_verify_remove_undesired_data(self):
        iface_info = gen_foo_iface_info()
        expected_iface_info = deepcopy(iface_info)

        iface = BaseIface(iface_info)
        iface.raw["foo_a"] = "b"
        iface.mark_as_desired()

        assert iface.state_for_verify() == expected_iface_info

    def test_remove_port(self):
        iface = BaseIface(gen_foo_iface_info())

        with pytest.raises(NmstateInternalError):
            iface.remove_port("port_name")

    def test_is_virtual(self):
        iface = BaseIface(gen_foo_iface_info())
        assert iface.is_virtual is False

    def test_create_virtual_port(self):
        iface = BaseIface(gen_foo_iface_info())
        assert iface.create_virtual_port("port_name") is None

    def test_config_changed_port(self):
        iface = BaseIface(gen_foo_iface_info())
        iface2 = BaseIface(gen_foo_iface_info())
        assert iface.config_changed_port(iface2) == []

    def test_original_desire_dict(self):
        iface = BaseIface(gen_foo_iface_info())

        assert iface.original_desire_dict == {}

        iface.mark_as_changed()
        assert iface.original_desire_dict == {}

        iface.mark_as_desired()
        iface.raw["foo_a"] = "b"
        assert iface.original_desire_dict == gen_foo_iface_info()

    def test_state_for_verify_remove_metadata(self):
        iface_info = gen_foo_iface_info()
        iface_info[BaseIface.PERMANENT_MAC_ADDRESS_METADATA] = MAC_ADDRESS1
        iface = BaseIface(iface_info)

        assert (
            BaseIface.PERMANENT_MAC_ADDRESS_METADATA
            not in iface.state_for_verify()
        )

    def test_to_dict_hide_the_password(self):
        iface_info = gen_foo_iface_info()
        iface_info["password"] = "foo"
        iface = BaseIface(iface_info)

        assert iface.to_dict()["password"] != "foo"

    def test_to_verify_allow_extra_ipv4(self):
        des_iface_info = gen_foo_iface_info()
        des_iface_info[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: IPV4_ADDRESSES,
        }
        des_iface = BaseIface(des_iface_info)

        cur_iface_info = gen_foo_iface_info()
        cur_iface_info[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: IPV4_ADDRESSES
            + [
                {
                    InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS3,
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
        cur_iface = BaseIface(cur_iface_info)

        assert des_iface.match(cur_iface)

    def test_to_verify_allow_extra_ipv6(self):
        des_iface_info = gen_foo_iface_info()
        des_iface_info[Interface.IPV6] = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: IPV6_ADDRESSES,
        }
        des_iface = BaseIface(des_iface_info)

        cur_iface_info = gen_foo_iface_info()
        cur_iface_info[Interface.IPV6] = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: IPV6_ADDRESSES
            + [
                {
                    InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS3,
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            ],
        }
        cur_iface = BaseIface(cur_iface_info)

        assert des_iface.match(cur_iface)

    def test_to_verify_not_allow_extra_ipv4(self):
        des_iface_info = gen_foo_iface_info()
        des_iface_info[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: IPV4_ADDRESSES,
            InterfaceIPv4.ALLOW_EXTRA_ADDRESS: False,
        }
        des_iface = BaseIface(des_iface_info)

        cur_iface_info = gen_foo_iface_info()
        cur_iface_info[Interface.IPV4] = {
            InterfaceIPv4.ENABLED: True,
            InterfaceIPv4.ADDRESS: IPV4_ADDRESSES
            + [
                {
                    InterfaceIPv4.ADDRESS_IP: IPV4_ADDRESS3,
                    InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                }
            ],
        }
        cur_iface = BaseIface(cur_iface_info)

        assert not des_iface.match(cur_iface)

    def test_to_verify_not_allow_extra_ipv6(self):
        des_iface_info = gen_foo_iface_info()
        des_iface_info[Interface.IPV6] = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: IPV6_ADDRESSES,
            InterfaceIPv6.ALLOW_EXTRA_ADDRESS: False,
        }
        des_iface = BaseIface(des_iface_info)

        cur_iface_info = gen_foo_iface_info()
        cur_iface_info[Interface.IPV6] = {
            InterfaceIPv6.ENABLED: True,
            InterfaceIPv6.ADDRESS: IPV6_ADDRESSES
            + [
                {
                    InterfaceIPv6.ADDRESS_IP: IPV6_ADDRESS3,
                    InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                }
            ],
        }
        cur_iface = BaseIface(cur_iface_info)

        assert not des_iface.match(cur_iface)
