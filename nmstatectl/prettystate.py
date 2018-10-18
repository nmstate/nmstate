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

from collections import OrderedDict
import json
from operator import itemgetter


import yaml


class PrettyState(object):
    def __init__(self, state):

        yaml.add_representer(OrderedDict, represent_ordereddict)
        self.state = order_state(state)

    @property
    def yaml(self):
        return yaml.dump(self.state, default_flow_style=False)

    @property
    def json(self):
        return json.dumps(self.state, indent=4, separators=(',', ': '))


def represent_ordereddict(dumper, data):
    """
    Represent OrderedDict as regular dictionary

    Source: https://stackoverflow.com/questions/16782112/can-pyyaml-dump-dict-items-in-non-alphabetical-order
    """  # noqa: E501
    value = []

    for item_key, item_value in data.items():
        node_key = dumper.represent_data(item_key)
        node_value = dumper.represent_data(item_value)

        value.append((node_key, node_value))

    return yaml.nodes.MappingNode(u'tag:yaml.org,2002:map', value)


def order_state(state):
    iface_states = state.pop('interfaces', [])
    state['interfaces'] = [
        order_iface_state(iface_state) for iface_state in sorted(
            iface_states, key=itemgetter('name')
        )
    ]

    return state


def order_iface_state(iface_state):
    ordered_state = OrderedDict()

    ordered_state['name'] = iface_state.pop('name')

    for key, value in order_dict(iface_state).items():
        ordered_state[key] = value

    return ordered_state


def order_dict(dict_):
    ordered_dict = OrderedDict()
    for key, value in sorted(dict_.items()):
        if isinstance(value, dict):
            value = order_dict(value)
        ordered_dict[key] = value

    return ordered_dict
