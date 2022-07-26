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

import os

from . import error
from . import schema

from .netapplier import apply
from .netapplier import commit
from .netapplier import rollback
from .netinfo import show
from .state import state_match

from .prettystate import PrettyState


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

__all__ = [
    "show",
    "apply",
    "commit",
    "rollback",
    "error",
    "schema",
    "state_match",
    "PrettyState",
]


def _get_version():
    with open(os.path.join(ROOT_DIR, "VERSION")) as f:
        version = f.read().strip()
    return version


__version__ = _get_version()
