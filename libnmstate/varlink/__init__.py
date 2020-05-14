#
# Copyright (c) 2020 Red Hat, Inc.
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

import logging

from .nmstate_varlink import get_varlink_server


def run_server(address):
    """
    Runs the varlink server in the specified the file path
    """
    varlink_server = get_varlink_server(address)
    try:
        with varlink_server as server:
            logging.info("Listening address : %s", str(server.server_address))
            server.serve_forever()
    except Exception as exception:
        logging.error(str(exception))
        varlink_server.shutdown()
    finally:
        varlink_server.server_close()
        logging.info("Nmstate-varlink service has stopped")
