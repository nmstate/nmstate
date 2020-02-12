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

import inspect
import warnings


def _warn_keyword_as_positional(func):
    signature = inspect.signature(func)
    parameters = signature.parameters.values()
    intended_posargs_count = len(
        [p for p in parameters if p.default == inspect.Parameter.empty]
    )

    def wrapper(*args, **kwargs):
        for arg_number in range(intended_posargs_count, len(args)):
            bad_argname = list(parameters)[arg_number].name
            warnings.warn(
                f"Specifying '{bad_argname}' as positional argument is "
                "deprecated. Please specify it as a keyword argument.",
                FutureWarning,
                stacklevel=2,
            )
        return func(*args, **kwargs)

    return wrapper
