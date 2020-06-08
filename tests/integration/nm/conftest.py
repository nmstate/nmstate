#
# Copyright (c) 2018-2020 Red Hat, Inc.
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

from libnmstate.nm.plugin import NetworkManagerPlugin
from libnmstate.nm.context import NmContext


@pytest.fixture(scope="function")
def nm_plugin():
    plugin = NetworkManagerPlugin()
    yield plugin
    if plugin.checkpoint:
        # Ignore failures as the checkpoint might already expired
        try:
            plugin.rollback_checkpoint()
        except Exception:
            pass
    plugin.unload()


@pytest.fixture(scope="function")
def nm_context():
    ctx = NmContext()
    yield ctx
    ctx.clean_up()
