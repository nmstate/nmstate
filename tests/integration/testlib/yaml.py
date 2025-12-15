# SPDX-License-Identifier: Apache-2.0

import yaml


def load_yaml(content):
    return yaml.load(content, Loader=yaml.SafeLoader)
