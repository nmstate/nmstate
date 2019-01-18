#
# Copyright 2018-2019 Red Hat, Inc.
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
from copy import deepcopy
import difflib
import json
from operator import itemgetter

import six
import yaml

from libnmstate.schema import Constants


def format_desired_current_state_diff(desired_state, current_state):
    pretty_desired_state = PrettyState(desired_state).yaml
    pretty_current_state = PrettyState(current_state).yaml

    diff = ''.join(difflib.unified_diff(
        pretty_desired_state.splitlines(True),
        pretty_current_state.splitlines(True),
        fromfile='desired',
        tofile='current', n=3))
    return (
        '\n'
        'desired\n'
        '=======\n'
        '{}\n'
        'current\n'
        '=======\n'
        '{}\n'
        'difference\n'
        '==========\n'
        '{}\n'.format(
            pretty_desired_state,
            pretty_current_state,
            diff)
    )


class PrettyState(object):
    def __init__(self, state):
        yaml.add_representer(OrderedDict, represent_ordereddict)

        if six.PY2:
            yaml.add_representer(unicode, represent_unicode)
        self.state = order_state(deepcopy(state))

    @property
    def yaml(self):
        return yaml.dump(self.state, default_flow_style=False,
                         explicit_start=True)

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
    iface_states = state.pop(Constants.INTERFACES, None)

    state = order_iface_state(state)

    if iface_states is not None:
        state[Constants.INTERFACES] = [
            order_iface_state(iface_state) for iface_state in sorted(
                iface_states, key=itemgetter('name')
            )
        ]

    return state


def represent_unicode(_, data):
    """
    Represent unicode as regular string

    Source:
        https://stackoverflow.com/questions/1950306/pyyaml-dumping-without-tags

    """

    return yaml.ScalarNode(tag=u'tag:yaml.org,2002:str',
                           value=data.encode('utf-8'))


def order_iface_state(iface_state):
    ordered_state = OrderedDict()

    for setting in ('name', 'type', 'state'):
        try:
            ordered_state[setting] = iface_state.pop(setting)
        except KeyError:
            pass

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
