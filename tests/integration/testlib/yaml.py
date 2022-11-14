# SPDX-License-Identifier: LGPL-2.1-or-later

import yaml


def load_yaml(content):
    return yaml.load(content, Loader=yaml.SafeLoader)
