# SPDX-License-Identifier: Apache-2.0

import pytest
import time
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

IPSEC_CONN_NAME = "ipsec-cli-conn"


@pytest.fixture(scope="module", autouse=True)
def ipsec_env():
    IpsecTestEnv.setup()
    yield
    IpsecTestEnv.cleanup()


@pytest.fixture
def ipsec_srv_psk_gw(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_psk_gw()


@pytest.fixture
def ipsec_srv_rsa_gw(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_rsa_gw()


@pytest.fixture
def ipsec_srv_cert_gw(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_cert_gw()


@pytest.fixture
def ipsec_srv_p2p(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_p2p()


@pytest.fixture
def ipsec_srv_site_to_site(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_site_to_site()


@pytest.fixture
def ipsec_srv_transport(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_transport()


@pytest.fixture
def ipsec_srv_host_to_site(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_host_to_site()


@pytest.fixture
def ipsec_srv_4in6_6in4(ipsec_env):
    IpsecTestEnv.start_ipsec_srv_4in6_6in4()


@pytest.fixture
def load_both_keys():
    IpsecTestEnv.load_both_srv_cli_keys()
    yield
    IpsecTestEnv.load_cli_key()


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
def ipsec_cli_cleanup(scope="function", autouse=True):
    yield
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          state: absent""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)


def test_ipsec_ipv4_libreswan_cert_auth_add_and_remove(ipsec_srv_cert_gw):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: '%fromcert'
            rightsubnet: 0.0.0.0/0
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.20"),
    reason="Need NetworkManager-libreswan 1.2.20+ to support rightcert",
)
def test_ipsec_ipv4_libreswan_rightcert(ipsec_srv_cert_gw, load_both_keys):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: '%fromcert'
            rightcert: {IpsecTestEnv.SRV_KEY_ID}
            rightsubnet: 0.0.0.0/0
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )
    vpn_data = cmdlib.exec_cmd(
        f"nmcli -g vpn.data con show {IPSEC_CONN_NAME}".split()
    )[1]
    assert "rightcert =" in vpn_data


def test_ipsec_ipv4_libreswan_psk_auth_add_and_remove(
    ipsec_srv_psk_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )


def test_ipsec_apply_with_hiden_psk(
    ipsec_srv_psk_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)

    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: <_password_hid_by_nmstate>
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)

    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )


def test_ipsec_rsa_authenticate(
    ipsec_srv_rsa_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            leftrsasigkey: {IpsecTestEnv.CLI_RSA}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '{IpsecTestEnv.CLI_KEY_ID}'
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightrsasigkey: {IpsecTestEnv.SRV_RSA}
            rightid: '{IpsecTestEnv.SRV_KEY_ID}'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.SRV_ADDR_V4,
        IpsecTestEnv.CLI_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )


def test_ipsec_ipv4_libreswan_fromcert(
    ipsec_srv_cert_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftrsasigkey: '%cert'
            right: {IpsecTestEnv.SRV_ADDR_V4}
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
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )


@pytest.fixture
def ipsec_psk_with_ipsec_iface(
    ipsec_srv_psk_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ipsec-interface: 9
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        "ipsec9",
    )
    yield


def test_ipsec_ipv4_libreswan_psk_auth_with_dpd(
    ipsec_srv_psk_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
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
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        "ipsec10",
    )


def test_ipsec_ipv4_libreswan_authby(ipsec_srv_psk_gw):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ipsec-interface: 77
            authby: secret
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        "ipsec77",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.20"),
    reason="Need NetworkManager-libreswan 1.2.20+ to support "
    "leftmodecfgclient",
)
def test_ipsec_ipv4_libreswan_p2p_cert_auth_add_and_remove(ipsec_srv_p2p):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          libreswan:
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '{IpsecTestEnv.CLI_KEY_ID}'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftmodecfgclient: no
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: '{IpsecTestEnv.SRV_KEY_ID}'
            rightsubnet: {IpsecTestEnv.SRV_ADDR_V4}/32
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.CLI_ADDR_V4}/32",
        f"{IpsecTestEnv.SRV_ADDR_V4}/32",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.20"),
    reason="Need NetworkManager-libreswan 1.2.20 to support leftsubnet",
)
def test_ipsec_ipv4_libreswan_leftsubnet(ipsec_srv_site_to_site):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftsubnet: {IpsecTestEnv.CLI_SUBNET_V4}
            leftmodecfgclient: no
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: '%fromcert'
            rightsubnet: {IpsecTestEnv.SRV_SUBNET_V4}
            ikev2: insist
            ikelifetime: 24h
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.CLI_SUBNET_V4}",
        f"{IpsecTestEnv.SRV_SUBNET_V4}",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.20 to support transport mode",
)
def test_ipsec_ipv4_libreswan_transport_mode(ipsec_srv_transport):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          libreswan:
            type: transport
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '{IpsecTestEnv.CLI_KEY_ID}'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftsubnet: {IpsecTestEnv.CLI_ADDR_V4}/32
            leftmodecfgclient: no
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: '{IpsecTestEnv.SRV_KEY_ID}'
            rightsubnet: {IpsecTestEnv.SRV_ADDR_V4}/32
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.CLI_ADDR_V4}/32",
        f"{IpsecTestEnv.SRV_ADDR_V4}/32",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
def test_ipsec_ipv6_libreswan_p2p(ipsec_srv_p2p):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          libreswan:
            hostaddrfamily: ipv6
            clientaddrfamily: ipv6
            left: {IpsecTestEnv.CLI_ADDR_V6}
            leftid: '@{IpsecTestEnv.CLI_KEY_ID}'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftmodecfgclient: no
            right: {IpsecTestEnv.SRV_ADDR_V6}
            rightid: '@{IpsecTestEnv.SRV_KEY_ID}'
            rightsubnet: {IpsecTestEnv.SRV_ADDR_V6}/128
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V6,
        IpsecTestEnv.SRV_ADDR_V6,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{IpsecTestEnv.CLI_ADDR_V6}/128",
        f"{IpsecTestEnv.SRV_ADDR_V6}/128",
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
def test_ipsec_ipv6_host_to_subnet(ipsec_srv_host_to_site):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
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
            left: {IpsecTestEnv.CLI_ADDR_V6}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V6}
            rightid: '%fromcert'
            rightsubnet: {IpsecTestEnv.SRV_SUBNET_V6}
            ipsec-interface: 93
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V6,
        IpsecTestEnv.SRV_ADDR_V6,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V6,
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
            IpsecTestEnv.CLI_ADDR_V6,
            IpsecTestEnv.SRV_ADDR_V6,
            IpsecTestEnv.CLI_SUBNET_V4,
            IpsecTestEnv.SRV_SUBNET_V4,
        ),
        (
            IpsecTestEnv.CLI_ADDR_V4,
            IpsecTestEnv.SRV_ADDR_V4,
            IpsecTestEnv.CLI_SUBNET_V6,
            IpsecTestEnv.SRV_SUBNET_V6,
        ),
    ],
    ids=["4in6", "6in4"],
)
def test_ipsec_ipv6_ipv4_subnet_tunnel(
    ipsec_srv_4in6_6in4,
    left,
    right,
    leftsubnet,
    rightsubnet,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
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
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftsubnet: {leftsubnet}
            leftmodecfgclient: false
            right: {right}
            rightid: '%fromcert'
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


def test_ipsec_modify_exist_connection(ipsec_srv_psk_gw):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          description: TESTING
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )

    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          libreswan:
            type: tunnel
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )

    iface_state = show_only((IPSEC_CONN_NAME,))[Interface.KEY][0]

    assert iface_state[Interface.DESCRIPTION] == "TESTING"
    assert iface_state[Interface.IPV4][InterfaceIPv4.ENABLED]


def test_ipsec_ipv4_libreswan_change_ipsec_iface(ipsec_psk_with_ipsec_iface):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: {IpsecTestEnv.PSK}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: {IpsecTestEnv.SRV_KEY_ID}
            ipsec-interface: 99
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        "ipsec99",
    )


# DHCPv4 off with empty IP address means IP disabled for IPSec interface
def test_ipsec_dhcpv4_off_and_empty_ip_addr(
    ipsec_srv_rsa_gw,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: false
          libreswan:
            leftrsasigkey: {IpsecTestEnv.CLI_RSA}
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '{IpsecTestEnv.CLI_KEY_ID}'
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightrsasigkey: {IpsecTestEnv.SRV_RSA}
            rightid: '{IpsecTestEnv.SRV_KEY_ID}'
            ipsec-interface: 97
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.SRV_ADDR_V4,
        IpsecTestEnv.CLI_ADDR_V4,
    )

    # The libreswan might take time to create xfrm interface after
    # xfrm policy been created.
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _is_ipsec_nic_ipv4_disabled, "ipsec97"
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.22"),
    reason="Need NetworkManager-libreswan 1.2.22+ to support IPv6",
)
def test_ipsec_ipv6_host_to_site_with_dhcpv6_off(ipsec_srv_host_to_site):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
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
            left: {IpsecTestEnv.CLI_ADDR_V6}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            right: {IpsecTestEnv.SRV_ADDR_V6}
            rightid: '%fromcert'
            rightsubnet: {IpsecTestEnv.SRV_SUBNET_V6}
            ipsec-interface: 97
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V6,
        IpsecTestEnv.SRV_ADDR_V6,
    )

    # The libreswan might take time to create xfrm interface after
    # xfrm policy been created.
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _is_ipsec_nic_ipv6_no_auto, "ipsec97"
    )


@pytest.mark.xfail(
    nm_libreswan_version_int() < version_str_to_int("1.2.23"),
    reason="Need NetworkManager-libreswan 1.2.23+ to support "
    "require-id-on-certificate",
)
def test_ipsec_require_id_on_certificate(ipsec_srv_cert_gw, load_both_keys):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: {IPSEC_CONN_NAME}
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: {IpsecTestEnv.CLI_ADDR_V4}
            leftid: '%fromcert'
            leftcert: {IpsecTestEnv.CLI_KEY_ID}
            leftmodecfgclient: true
            right: {IpsecTestEnv.SRV_ADDR_V4}
            rightid: '%fromcert'
            rightcert: {IpsecTestEnv.SRV_KEY_ID}
            rightsubnet: 0.0.0.0/0
            require-id-on-certificate: yes
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )

    desired_iface = desired_state[Interface.KEY][0]

    desired_iface["libreswan"]["rightid"] = "other.fail"
    libnmstate.apply(desired_state)
    time.sleep(5)
    assert not _check_ipsec(IpsecTestEnv.CLI_ADDR_V4, IpsecTestEnv.SRV_ADDR_V4)

    desired_iface["libreswan"]["require-id-on-certificate"] = False
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec,
        IpsecTestEnv.CLI_ADDR_V4,
        IpsecTestEnv.SRV_ADDR_V4,
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_ip,
        IpsecTestEnv.SRV_POOL_PREFIX_V4,
        IpsecTestEnv.CLI_NIC,
    )


def _is_ipsec_nic_ipv4_disabled(nic_name):
    try:
        iface_state = show_only((nic_name,))[Interface.KEY][0]
    except IndexError:
        return False
    return not iface_state[Interface.IPV4][InterfaceIPv4.ENABLED]


def _is_ipsec_nic_ipv6_no_auto(nic_name):
    try:
        iface_state = show_only((nic_name,))[Interface.KEY][0]
    except IndexError:
        return False
    return not (
        iface_state[Interface.IPV6].get(InterfaceIPv6.DHCP)
        or iface_state[Interface.IPV6].get(InterfaceIPv6.AUTOCONF)
    )
