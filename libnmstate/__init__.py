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

from . import error
from . import schema

from .netapplier import apply
from .netapplier import commit
from .netapplier import rollback
from .netinfo import show
from .netinfo import show_running_config
from .nmstate import generate_configurations
from .prettystate import PrettyState
from .version import get_version as _get_version

__all__ = [
    "PrettyState",
    "apply",
    "commit",
    "error",
    "generate_configurations",
    "rollback",
    "schema",
    "show",
    "show_running_config",
]

__version__ = _get_version()
