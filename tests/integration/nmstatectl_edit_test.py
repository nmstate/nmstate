# SPDX-License-Identifier: LGPL-2.1-or-later
#
# Copyright (c) 2018-2021 Red Hat, Inc.
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


from .testlib import cmdlib


RC_SUCCESS = 0


def test_edit_cancel(eth1_up):
    runenv = dict(os.environ)
    env = {"EDITOR": "false"}

    runenv.update(env)

    cmds = ["nmstatectl", "edit", "eth1"]
    ret = cmdlib.exec_cmd(cmds, env=runenv)
    rc, out, err = ret

    assert_rc(rc, os.EX_DATAERR, ret)


def test_edit_no_change_eth1():
    runenv = dict(os.environ)
    env = {"EDITOR": "touch"}

    runenv.update(env)

    cmds = ["nmstatectl", "edit", "eth1"]
    ret = cmdlib.exec_cmd(cmds, env=runenv)
    rc, out, err = ret

    assert_rc(rc, RC_SUCCESS, ret)


def assert_rc(actual, expected, return_tuple):
    assert actual == expected, "rc={}, out={}, err={}".format(*return_tuple)
