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

import logging
import re
import subprocess


def exec_cmd(cmd, env=None):
    """
    Execute cmd in an external process, collect its output and returncode

    :param cmd: an iterator of strings to be passed as exec(2)'s argv
    :param env: an optional dictionary to be placed as environment variables
                of the external process. If None, the environment of the
                calling process is used.
    :returns: a 3-tuple of the process's
              (returncode, stdout content, stderr content.)
    """
    logging.debug(command_log_line(cmd))

    p = subprocess.Popen(
        cmd, close_fds=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env)

    out, err = p.communicate()

    logging.debug(_retcode_log_line(p.returncode, err=err))

    return p.returncode, out, err


def command_log_line(args, cwd=None):
    return "{0} (cwd {1})".format(_list2cmdline(args), cwd)


def _retcode_log_line(code, err=None):
    result = "SUCCESS" if code == 0 else "FAILED"
    return "{0}: <err> = {1!r}; <rc> = {2!r}".format(result, err, code)


def _list2cmdline(args):
    """
    Convert argument list for exec_cmd to string for logging.
    The purpose of this log is to make it easy to run commands in the shell for
    debugging.
    """
    parts = []
    for arg in args:
        if _needs_quoting(arg) or arg == '':
            arg = "'" + arg.replace("'", r"'\''") + "'"
        parts.append(arg)
    return ' '.join(parts)


# This function returns truthy value if its argument contains unsafe characters
# for including in a command passed to the shell. The safe characters were
# stolen from pipes._safechars.
_needs_quoting = re.compile(r'[^A-Za-z0-9_%+,\-./:=@]').search
