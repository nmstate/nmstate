# SPDX-License-Identifier: LGPL-2.1-or-later

import json

import libnmstate
from libnmstate.schema import Interface

from .cmdlib import exec_cmd


def get_sriov_vf_names(pf_name):
    output = exec_cmd(f"ip -j -d link show {pf_name}".split())[1]
    link_info = json.loads(output)[0]
    macs = [
        vf_info["address"].upper()
        for vf_info in link_info.get("vfinfo_list", [])
    ]
    return [
        iface[Interface.NAME]
        for iface in libnmstate.show()[Interface.KEY]
        if iface[Interface.MAC] in macs
    ]
