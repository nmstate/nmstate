# SPDX-License-Identifier: LGPL-2.1-or-later

from libnmstate.schema import Interface


def get_wait_ip(applied_config):
    if applied_config:
        nm_ipv4_may_fail = _get_may_fail(applied_config, False)
        nm_ipv6_may_fail = _get_may_fail(applied_config, True)
        if nm_ipv4_may_fail and not nm_ipv6_may_fail:
            return Interface.WAIT_IP_IPV6
        elif not nm_ipv4_may_fail and nm_ipv6_may_fail:
            return Interface.WAIT_IP_IPV4
        elif not nm_ipv4_may_fail and not nm_ipv6_may_fail:
            return Interface.WAIT_IP_IPV4_AND_IPV6
    return Interface.WAIT_IP_ANY


def set_wait_ip(nm_ipv4_set, nm_ipv6_set, wait_ip):
    if nm_ipv4_set:
        if wait_ip == Interface.WAIT_IP_ANY:
            nm_ipv4_set.props.may_fail = True
        elif wait_ip in (
            Interface.WAIT_IP_IPV4,
            Interface.WAIT_IP_IPV4_AND_IPV6,
        ):
            nm_ipv4_set.props.may_fail = False
    if nm_ipv6_set:
        if wait_ip == Interface.WAIT_IP_ANY:
            nm_ipv6_set.props.may_fail = True
        elif wait_ip in (
            Interface.WAIT_IP_IPV6,
            Interface.WAIT_IP_IPV4_AND_IPV6,
        ):
            nm_ipv6_set.props.may_fail = False


def _get_may_fail(nm_profile, is_ipv6):
    if is_ipv6:
        nm_set = nm_profile.get_setting_ip6_config()
    else:
        nm_set = nm_profile.get_setting_ip4_config()

    if nm_set:
        return nm_set.props.may_fail
    else:
        # NM is defaulting `may-fail` as True
        return True
