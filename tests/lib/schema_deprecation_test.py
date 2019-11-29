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

from libnmstate.schema import LinuxBridge


@pytest.mark.parametrize(
    'changes',
    argvalues=[
        ['PORT_NAME', LinuxBridge.Port.NAME],
        ['PORT_STP_HAIRPIN_MODE', LinuxBridge.Port.STP_HAIRPIN_MODE],
        ['PORT_STP_PATH_COST', LinuxBridge.Port.STP_PATH_COST],
        ['PORT_STP_PRIORITY', LinuxBridge.Port.STP_PRIORITY],
        ['STP_ENABLED', LinuxBridge.STP.ENABLED],
        ['STP_FORWARD_DELAY', LinuxBridge.STP.FORWARD_DELAY],
        ['STP_HELLO_TIME', LinuxBridge.STP.HELLO_TIME],
        ['STP_MAX_AGE', LinuxBridge.STP.MAX_AGE],
        ['STP_PRIORITY', LinuxBridge.STP.PRIORITY],
    ],
)
def test_linuxbridge_deprecated_constants(changes):
    with pytest.warns(FutureWarning) as record:
        deprecated_value = getattr(LinuxBridge, changes[0])

    assert len(record) == 1
    assert changes[0] in record[0].message.args[0]
    assert deprecated_value == changes[1]
