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

import pytest

from libnmstate.error import NmstateValueError
from libnmstate.schema import VXLAN
from libnmstate.schema import InterfaceType

from libnmstate.ifaces.vxlan import VxlanIface

from ..testlib.constants import IPV4_ADDRESS1
from ..testlib.ifacelib import gen_foo_iface_info

BASE_IFACE_NAME = "base1"


class TestVxlanIface:
    def _gen_iface_info(self):
        iface_info = gen_foo_iface_info(iface_type=InterfaceType.VXLAN)
        iface_info[VXLAN.CONFIG_SUBTREE] = {
            VXLAN.ID: 101,
            VXLAN.BASE_IFACE: BASE_IFACE_NAME,
            VXLAN.REMOTE: IPV4_ADDRESS1,
        }
        return iface_info

    def test_get_parent(self):
        assert VxlanIface(self._gen_iface_info()).parent == BASE_IFACE_NAME

    def test_need_parent(self):
        assert VxlanIface(self._gen_iface_info()).need_parent

    def test_is_virtual(self):
        assert VxlanIface(self._gen_iface_info()).is_virtual

    def test_can_have_ip_when_enslaved(self):
        assert VxlanIface(self._gen_iface_info()).can_have_ip_when_enslaved

    @pytest.mark.parametrize(
        "required_field", [VXLAN.ID, VXLAN.REMOTE, VXLAN.BASE_IFACE]
    )
    def test_validate_require_field_missing(self, required_field):
        iface_info = self._gen_iface_info()
        iface_info[VXLAN.CONFIG_SUBTREE].pop(required_field)

        iface = VxlanIface(iface_info)
        with pytest.raises(NmstateValueError):
            iface.pre_edit_validation_and_cleanup()
