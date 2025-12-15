# SPDX-License-Identifier: Apache-2.0

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
