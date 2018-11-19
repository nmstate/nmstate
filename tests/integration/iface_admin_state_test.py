#
# Copyright 2018 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import pytest

from libnmstate import netapplier

from .testlib import assertlib
from .testlib.statelib import INTERFACES


def test_set_a_down_iface_down(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'down',
            }
        ]
    }
    netapplier.apply(desired_state)
    assertlib.assert_state(desired_state)

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)


@pytest.mark.xfail(reason='Some ifaces cannot be removed', strict=True)
def test_removing_a_non_removable_iface(eth1_up):
    desired_state = {
        INTERFACES: [
            {
                'name': 'eth1',
                'type': 'ethernet',
                'state': 'absent',
            }
        ]
    }

    netapplier.apply(desired_state)

    assertlib.assert_state(desired_state)
