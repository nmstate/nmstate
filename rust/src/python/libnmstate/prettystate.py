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

from collections.abc import Mapping
from collections.abc import Sequence
from copy import deepcopy
import difflib
import json
import warnings
import yaml  # type: ignore

from .schema import DNS
from .schema import Route
from .schema import RouteRule
from .schema import Interface

PRIORITY_LIST = (
    "name",
    "type",
    "state",
    "enabled",
    DNS.KEY,
    RouteRule.KEY,
    Route.KEY,
    Interface.KEY,
)

try:
    from warnings import deprecated
except ImportError:

    class deprecated:
        def __init__(self, message=None):
            default_message = (
                "PrettyState class is deprecated; "
                "to be removed in future release. "
                "The output of libnmstate.show() "
                "is already sorted."
            )
            self.message = message or default_message

        def __call__(self, cls):
            warnings.warn(self.message, DeprecationWarning)
            return cls


def format_desired_current_state_diff(desired_state, current_state):
    pretty_desired_state = PrettyState(desired_state).yaml
    pretty_current_state = PrettyState(current_state).yaml

    diff = "".join(
        difflib.unified_diff(
            pretty_desired_state.splitlines(True),
            pretty_current_state.splitlines(True),
            fromfile="desired",
            tofile="current",
            n=3,
        )
    )
    return (
        "\n"
        "desired\n"
        "=======\n"
        "{}\n"
        "current\n"
        "=======\n"
        "{}\n"
        "difference\n"
        "==========\n"
        "{}\n".format(pretty_desired_state, pretty_current_state, diff)
    )


@deprecated("Output of libnmstate.show() is already sorted.")
class PrettyState:
    def __init__(self, state):
        yaml.add_representer(dict, represent_dict)
        self.state = _sort_with_priority(state)

    @property
    def yaml(self):
        return yaml.dump(
            self.state, default_flow_style=False, explicit_start=True
        )

    @property
    def json(self):
        return json.dumps(self.state, indent=4, separators=(",", ": "))


def represent_dict(dumper, data):
    """
    Represent dictionary with insert order
    """
    value = []

    for item_key, item_value in data.items():
        node_key = dumper.represent_data(item_key)
        node_value = dumper.represent_data(item_value)
        value.append((node_key, node_value))

    return yaml.nodes.MappingNode("tag:yaml.org,2002:map", value)


def represent_unicode(_, data):
    """
    Represent unicode as regular string

    Source:
        https://stackoverflow.com/questions/1950306/pyyaml-dumping-without-tags

    """

    return yaml.ScalarNode(
        tag="tag:yaml.org,2002:str", value=data.encode("utf-8")
    )


def _sort_with_priority(data):
    if isinstance(data, Sequence) and not isinstance(data, str):
        return [_sort_with_priority(item) for item in data]
    elif isinstance(data, Mapping):
        new_data = {}
        for key in sorted(data.keys(), key=_sort_with_priority_key_func):
            new_data[key] = _sort_with_priority(data[key])
        return new_data
    else:
        return deepcopy(data)


def _sort_with_priority_key_func(key):
    try:
        priority = PRIORITY_LIST.index(key)
    except ValueError:
        priority = len(PRIORITY_LIST)
    return (priority, key)
