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

import libnmstate
from libnmstate.error import NmstateNotImplementedError
from libnmstate.schema import Ethernet
from libnmstate.schema import Interface


SRIOV_CONFIG = {Ethernet.SRIOV_SUBTREE: {Ethernet.SRIOV.TOTAL_VFS: 2}}


@pytest.mark.xfail(
    raises=NmstateNotImplementedError,
    reason='SR-IOV is not supported yet',
    strict=True,
)
def test_sriov_not_implemented(eth1_up):
    eth1_up[Interface.KEY][0][Ethernet.CONFIG_SUBTREE] = SRIOV_CONFIG
    libnmstate.apply(eth1_up)
