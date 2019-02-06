#
# Copyright 2019 Red Hat, Inc.
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

import os


PATH_MAX = 4096


def find_examples_dir():
    """
    Look recursively for the directory containing the examples
    """

    path = ''
    parent = '../'
    rootdir = '/'
    examples = None
    for _ in range(PATH_MAX // len('x/')):
        maybe_examples = os.path.abspath(os.path.join(path, 'examples'))
        if os.path.isdir(maybe_examples):
            examples = maybe_examples
            break

        if os.path.abspath(path) == rootdir:
            break

        path = parent + path

    if examples:
        return examples
    else:
        raise RuntimeError('Cannot find examples directory')
