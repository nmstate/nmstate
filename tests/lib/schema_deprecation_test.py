#
# Copyright (c) 2019 Red Hat, Inc.
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

from libnmstate.schema import LinuxBridge as LB


@pytest.mark.parametrize(
    'changes',
    argvalues=[
        ['PORT_NAME', LB.Port.NAME],
        ['PORT_STP_PRIORITY', LB.Port.STP_PRIORITY],
        ['PORT_STP_HAIRPIN_MODE', LB.Port.STP_HAIRPIN_MODE],
        ['PORT_STP_PATH_COST', LB.Port.STP_PATH_COST],
    ],
)
def test_linuxbridge_deprecated_constants(changes):
    with pytest.warns(DeprecationWarning) as record:
        deprecated_value = getattr(LB, changes[0])

    assert len(record) == 1
    assert changes[0] in record[0].message.args[0]
    assert deprecated_value == changes[1]
