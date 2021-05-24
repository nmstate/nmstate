#
# Copyright (c) 2021 Red Hat, Inc.
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

from copy import deepcopy
import logging

from libnmstate.schema import Ethtool


class IfaceEthtool:
    def __init__(self, ethtool_info):
        self._info = ethtool_info
        self._pause = None
        if self._info.get(Ethtool.Pause.CONFIG_SUBTREE):
            self._pause = IfaceEthtoolPause(
                self._info[Ethtool.Pause.CONFIG_SUBTREE]
            )

    @property
    def pause(self):
        return self._pause

    def pre_edit_validation_and_cleanup(self, original_desire):
        if self.pause:
            self.pause.pre_edit_validation_and_cleanup(
                IfaceEthtoolPause(
                    original_desire.get(Ethtool.Pause.CONFIG_SUBTREE, {})
                )
            )

    def canonicalize(self):
        if self.pause:
            self.pause.canonicalize()

    def to_dict(self):
        if self.pause:
            return {Ethtool.Pause.CONFIG_SUBTREE: self.pause.to_dict()}
        else:
            return {}


class IfaceEthtoolPause:
    def __init__(self, pause_info):
        self._info = pause_info

    @property
    def autoneg(self):
        return self._info.get(Ethtool.Pause.AUTO_NEGOTIATION)

    @property
    def rx(self):
        return self._info.get(Ethtool.Pause.RX)

    @property
    def tx(self):
        return self._info.get(Ethtool.Pause.TX)

    def pre_edit_validation_and_cleanup(self, original_desire):
        """
        When AUTO_NEGOTIATION is enabled, RX and TX should be ignored.
        Log warnning if desired has AUTO_NEGOTIATION: True and RX/TX
        configured.
        """
        if self.autoneg and (
            original_desire.rx is not None or original_desire.tx is not None
        ):
            logging.warn(
                "Ignoring RX/TX configure of ethtool PAUSE when "
                "AUTO_NEGOTIATION enabled"
            )
        self.canonicalize()

    def canonicalize(self):
        """
        Remove RX/TX when AUTO_NEGOTIATION is enabled.
        """
        if self.autoneg:
            self._info.pop(Ethtool.Pause.RX, None)
            self._info.pop(Ethtool.Pause.TX, None)

    def to_dict(self):
        return deepcopy(self._info)
