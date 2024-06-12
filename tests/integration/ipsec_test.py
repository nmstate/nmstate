# SPDX-License-Identifier: Apache-2.0

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6


from .testlib import cmdlib
from .testlib.env import nm_libreswan_version_int
from .testlib.env import version_str_to_int
from .testlib.retry import retry_till_true_or_timeout
from .testlib.statelib import show_only
from .testlib.ipsec import IpsecTestEnv


RETRY_COUNT = 10


@pytest.fixture(scope="module", autouse=True)
def ipsec_env():
    with IpsecTestEnv() as env:
        yield env


def _check_ipsec(left, right):
    output = cmdlib.exec_cmd("ip xfrm state".split(), check=True)[1]
    return f"src {left} dst {right}" in output


def _check_ipsec_policy(left, right):
    output = cmdlib.exec_cmd("ip xfrm policy".split(), check=True)[1]
    return (
        f"src {left} dst {right}" in output
        and f"src {right} dst {left}" in output
    )


def _check_ipsec_ip(ip_net_prefix, nic):
    try:
        iface_state = show_only([nic])[Interface.KEY][0]
        for ip in iface_state.get(Interface.IPV4, {}).get(
            InterfaceIPv4.ADDRESS, []
        ):
            if ip.get(InterfaceIPv4.ADDRESS_IP, "").startswith(ip_net_prefix):
                return True
        for ip in iface_state.get(Interface.IPV6, {}).get(
            InterfaceIPv4.ADDRESS, []
        ):
            if ip.get(InterfaceIPv4.ADDRESS_IP, "").startswith(ip_net_prefix):
                return True
    except Exception:
        pass
    return False


@pytest.fixture
def ipsec_hosta_conn_cleanup():
    yield
    desired_state = yaml.load(
        """---
        interfaces:
        - name: hosta_conn
          type: ipsec
          state: absent""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)


def test_ipsec_ipv4_libreswan_cert_auth_add_and_remove(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.HOSTA_IPV4_CRT}
            leftid: '%fromcert'
            leftcert: hosta.example.org
            right: {IpsecTestEnv.HOSTB_IPV4_CRT}
            rightid: 'hostb.example.org'
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_CRT,
        IpsecTestEnv.HOSTB_IPV4_CRT,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.20"),
    reason="Need NetworkManager-libreswan 1.2.20+ to support rightcert",
)
def test_ipsec_ipv4_libreswan_rightcert(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.HOSTA_IPV4_CRT}
            leftid: '%fromcert'
            leftcert: hosta.example.org
            right: {IpsecTestEnv.HOSTB_IPV4_CRT}
            rightid: '%fromcert'
            rightcert: hostb.example.org
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_CRT,
        IpsecTestEnv.HOSTB_IPV4_CRT,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )
    vpn_data = cmdlib.exec_cmd(
        "nmcli -g vpn.data con show "
        f"{IpsecTestEnv.HOSTA_IPSEC_CONN_NAME}".split()
    )[1]
    assert "rightcert =" in vpn_data


def test_ipsec_ipv4_libreswan_psk_auth_add_and_remove(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )


def test_ipsec_apply_with_hiden_psk(ipsec_hosta_conn_cleanup):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)

    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: <_password_hid_by_nmstate>
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)

    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )


def test_ipsec_rsa_authenticate(ipsec_env, ipsec_hosta_conn_cleanup):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            leftrsasigkey: {ipsec_env.rsa_signatures["hosta"]}
            left: {IpsecTestEnv.HOSTA_IPV4_RSA}
            leftid: 'hosta-rsa.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_RSA}
            rightrsasigkey: {ipsec_env.rsa_signatures["hostb"]}
            rightid: 'hostb-rsa.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_RSA,
        IpsecTestEnv.HOSTB_IPV4_RSA,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )


def test_ipsec_ipv4_libreswan_fromcert(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.HOSTA_IPV4_CRT}
            leftid: '%fromcert'
            leftcert: hosta.example.org
            leftrsasigkey: '%cert'
            right: {IpsecTestEnv.HOSTB_IPV4_CRT}
            rightid: '%fromcert'
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_CRT,
        IpsecTestEnv.HOSTB_IPV4_CRT,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )


@pytest.fixture
def ipsec_psk_with_ipsec_iface(ipsec_hosta_conn_cleanup):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ipsec-interface: 9
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        "ipsec9",
    )
    yield


def test_ipsec_ipv4_libreswan_psk_auth_with_dpd(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            dpddelay: 1
            dpdtimeout: 60
            dpdaction: restart
            ipsec-interface: "10"
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        "ipsec10",
    )


def test_ipsec_ipv4_libreswan_authby(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ipsec-interface: 77
            authby: secret
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        "ipsec77",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.20"),
    reason="Need NetworkManager-libreswan 1.2.20+ to support "
    "leftmodecfgclient",
)
def test_ipsec_ipv4_libreswan_p2p_cert_auth_add_and_remove(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          libreswan:
            left: {IpsecTestEnv.HOSTA_IPV4_CRT_P2P}
            leftid: 'hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {IpsecTestEnv.HOSTB_IPV4_CRT_P2P}
            rightid: 'hostb.example.org'
            rightsubnet: {IpsecTestEnv.HOSTB_IPV4_CRT_P2P}/32
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_CRT_P2P,
        IpsecTestEnv.HOSTB_IPV4_CRT_P2P,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.HOSTA_IPV4_CRT_P2P}/32",
        f"{IpsecTestEnv.HOSTB_IPV4_CRT_P2P}/32",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.20"),
    reason="Need NetworkManager-libreswan 1.2.20 to support leftsubnet",
)
def test_ipsec_ipv4_libreswan_leftsubnet(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.HOSTA_IPV4_IF_SUBNET}
            leftid: 'hosta.example.org'
            leftcert: hosta.example.org
            leftsubnet: {IpsecTestEnv.HOSTA_IPV4_CRT_SUBNET}
            leftmodecfgclient: no
            right: {IpsecTestEnv.HOSTB_IPV4_IF_SUBNET}
            rightid: 'hostb.example.org'
            rightsubnet: {IpsecTestEnv.HOSTB_IPV4_CRT_SUBNET}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_IF_SUBNET,
        IpsecTestEnv.HOSTB_IPV4_IF_SUBNET,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.HOSTA_IPV4_CRT_SUBNET}",
        f"{IpsecTestEnv.HOSTB_IPV4_CRT_SUBNET}",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.20 to support transport mode",
)
def test_ipsec_ipv4_libreswan_transport_mode(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          libreswan:
            type: transport
            left: {IpsecTestEnv.HOSTA_IPV4_TRANSPORT}
            leftid: 'hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {IpsecTestEnv.HOSTB_IPV4_TRANSPORT}
            rightid: 'hostb.example.org'
            rightsubnet: {IpsecTestEnv.HOSTB_IPV4_TRANSPORT}/32
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_TRANSPORT,
        IpsecTestEnv.HOSTB_IPV4_TRANSPORT,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.HOSTA_IPV4_TRANSPORT}/32",
        f"{IpsecTestEnv.HOSTB_IPV4_TRANSPORT}/32",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
def test_ipsec_ipv6_libreswan_p2p(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          libreswan:
            hostaddrfamily: ipv6
            clientaddrfamily: ipv6
            left: {IpsecTestEnv.HOSTA_IPV6_P2P}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {IpsecTestEnv.HOSTB_IPV6_P2P}
            rightid: '@hostb.example.org'
            rightsubnet: {IpsecTestEnv.HOSTB_IPV6_P2P}/128
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV6_P2P,
        IpsecTestEnv.HOSTB_IPV6_P2P,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.HOSTA_IPV6_P2P}/128",
        f"{IpsecTestEnv.HOSTB_IPV6_P2P}/128",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
def test_ipsec_ipv6_host_to_subnet(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            dhcp: true
            autoconf: true
          libreswan:
            hostaddrfamily: ipv6
            clientaddrfamily: ipv6
            left: {IpsecTestEnv.HOSTA_IPV6_CS}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            right: {IpsecTestEnv.HOSTB_IPV6_CS}
            rightid: '@hostb.example.org'
            ipsec-interface: 93
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV6_CS,
        IpsecTestEnv.HOSTB_IPV6_CS,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX6,
        "ipsec93",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
@pytest.mark.parametrize(
    "left,right,leftsubnet,rightsubnet",
    [
        (
            IpsecTestEnv.HOSTA_IPV6_4IN6,
            IpsecTestEnv.HOSTB_IPV6_4IN6,
            IpsecTestEnv.HOSTA_IPV4_CRT_SUBNET,
            IpsecTestEnv.HOSTB_IPV4_CRT_SUBNET,
        ),
        (
            IpsecTestEnv.HOSTA_IPV4_6IN4,
            IpsecTestEnv.HOSTB_IPV4_6IN4,
            IpsecTestEnv.HOSTA_IPV6_SUBNET,
            IpsecTestEnv.HOSTB_IPV6_SUBNET,
        ),
    ],
    ids=["4in6", "6in4"],
)
def test_ipsec_ipv6_ipv4_subnet_tunnel(
    ipsec_hosta_conn_cleanup,
    left,
    right,
    leftsubnet,
    rightsubnet,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            dhcp: true
            autoconf: true
          libreswan:
            left: {left}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            leftsubnet: {leftsubnet}
            leftmodecfgclient: false
            right: {right}
            rightid: '@hostb.example.org'
            rightsubnet: {rightsubnet}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        left,
        right,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        leftsubnet,
        rightsubnet,
    )


def test_ipsec_modify_exist_connection(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          description: TESTING
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )

    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          libreswan:
            type: tunnel
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        IpsecTestEnv.HOSTA_NIC,
    )

    iface_state = show_only(["hosta_conn"])[Interface.KEY][0]

    assert iface_state[Interface.DESCRIPTION] == "TESTING"
    assert iface_state[Interface.IPV4][InterfaceIPv4.ENABLED]


def test_ipsec_ipv4_libreswan_change_ipsec_iface(ipsec_psk_with_ipsec_iface):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ipsec-interface: 99
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTB_IPV4_PSK,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.HOSTB_VPN_SUBNET_PREFIX,
        "ipsec99",
    )


# DHCPv4 off with empty IP address means IP disabled for IPSec interface
def test_ipsec_dhcpv4_off_and_empty_ip_addr(
    ipsec_env,
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: false
          libreswan:
            leftrsasigkey: {ipsec_env.rsa_signatures["hosta"]}
            left: {IpsecTestEnv.HOSTA_IPV4_RSA}
            leftid: 'hosta-rsa.example.org'
            right: {IpsecTestEnv.HOSTB_IPV4_RSA}
            rightrsasigkey: {ipsec_env.rsa_signatures["hostb"]}
            rightid: 'hostb-rsa.example.org'
            ipsec-interface: 97
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV4_RSA,
        IpsecTestEnv.HOSTB_IPV4_RSA,
    )

    iface_state = show_only(["ipsec97"])[Interface.KEY][0]
    assert not iface_state[Interface.IPV4][InterfaceIPv4.ENABLED]


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
def test_ipsec_ipv6_host_to_site_with_dhcpv6_off(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          ipv6:
            enabled: true
            dhcp: false
            autoconf: false
          libreswan:
            hostaddrfamily: ipv6
            clientaddrfamily: ipv6
            left: {IpsecTestEnv.HOSTA_IPV6_CS}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            right: {IpsecTestEnv.HOSTB_IPV6_CS}
            rightid: '@hostb.example.org'
            ipsec-interface: 97
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.HOSTA_IPV6_CS,
        IpsecTestEnv.HOSTB_IPV6_CS,
    )

    iface_state = show_only(["ipsec97"])[Interface.KEY][0]
    assert not iface_state[Interface.IPV6].get(InterfaceIPv6.DHCP)
    assert not iface_state[Interface.IPV6].get(InterfaceIPv6.AUTOCONF)
