# SPDX-License-Identifier: Apache-2.0

from contextlib import contextmanager
import os
import tempfile


@contextmanager
def tmp_plugin_dir():
    with tempfile.TemporaryDirectory() as plugin_dir:
        os.environ["NMSTATE_PLUGIN_DIR"] = plugin_dir
        try:
            yield plugin_dir
        finally:
            os.environ.pop("NMSTATE_PLUGIN_DIR")
