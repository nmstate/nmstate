#
# Copyright (c) 2019-2020 Red Hat, Inc.
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

from libnmstate.schema import Bond
from libnmstate.schema import BondMode

from ..testlib import assertlib
from ..testlib import cmdlib
from ..testlib.bondlib import bond_interface


BOND0 = "bondtest0"


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
