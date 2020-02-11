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
from contextlib import contextmanager
import functools

from libnmstate import error
from libnmstate import nm
from libnmstate.nm.nmclient import nmclient_context


class MainloopTestError(Exception):
    pass


@contextmanager
def mainloop():
    mloop = nm.nmclient.mainloop()
    yield
    try:
        mloop.run(timeout=15)
    except error.NmstateLibnmError as ex:
        nm.nmclient.mainloop(refresh=True)
        raise MainloopTestError(str(ex.args))


def mainloop_run(func):
    @nmclient_context
    @functools.wraps(func)
    def wrapper_mainloop(*args, **kwargs):
        with mainloop():
            ret = func(*args, **kwargs)
        return ret

    return wrapper_mainloop
