# SPDX-License-Identifier: Apache-2.0

import os
import glob
import re
import shutil
import time

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route

from .testlib import cmdlib
from .testlib.env import is_el8
from .testlib.veth import create_veth_pair
from .testlib.veth import remove_veth_pair
from .testlib.retry import retry_till_true_or_timeout
from .testlib.statelib import show_only

CA_NAME = "nmstate-test-ca.example.org"
HOSTA_NAME = "hosta.example.org"
HOSTA_NIC = "hosta_nic"
HOSTA_IPV4_CRT = "192.0.2.251"
HOSTA_IPV4_PSK = "192.0.2.250"
HOSTA_IPV4_RSA = "192.0.2.249"
HOSTA_IPV4_CRT_P2P = "192.0.2.248"
HOSTA_IPV4_CRT_SUBNET = "192.0.4.0/24"
HOSTA_IPV4_TRANSPORT = "192.0.2.247"
HOSTA_IPSEC_CONN_NAME = "hosta_conn"
HOSTA_IPV6_P2P = "2001:db8:f::a"
HOSTB_IPV6_P2P = "2001:db8:f::b"
HOSTA_IPV6_CS = "2001:db8:e::a"
HOSTB_IPV6_CS = "2001:db8:e::b"
HOSTB_NAME = "hostb.example.org"
HOSTB_NIC = "hostb_nic"
HOSTB_IPV4_CRT = "192.0.2.152"
HOSTB_IPV4_PSK = "192.0.2.153"
HOSTB_IPV4_RSA = "192.0.2.154"
HOSTB_IPV4_CRT_P2P = "192.0.2.155"
HOSTB_IPV4_CRT_SUBNET = "192.0.3.0/24"
HOSTB_IPV4_TRANSPORT = "192.0.2.156"
HOSTB_VPN_SUBNET_PREFIX = "203.0.113"
HOSTB_VPN_SUBNET = f"{HOSTB_VPN_SUBNET_PREFIX}.0/24"
HOSTB_VPN_SUBNET_PREFIX6 = "2001:db8:9::"
HOSTB_VPN_SUBNET6 = f"{HOSTB_VPN_SUBNET_PREFIX6}/64"
HOSTB_EXT_IP = "198.51.100.1"
HOSTB_EXT_IPV6 = "2001:db8:1::"
HOSTB_DUMMY_NIC = "dummy0"
HOSTB_NS = "nmstate_ipsec_test"
HOSTB_IPSEC_CONF_NAME = "hostb_conn"
HOSTB_IPSEC_CRT_CONN_NAME = "hostb_conn_crt"
HOSTB_IPSEC_PSK_CONN_NAME = "hostb_conn_psk"
HOSTB_IPSEC_RSA_CONN_NAME = "hostb_conn_rsa"
HOSTB_IPSEC_CRT_P2P_CONN_NAME = "hostb_conn_crt_p2p"
HOSTB_IPSEC_TRANSPORET_CONN_NAME = "hostb_conn_transport"
HOSTB_IPSEC_IPV6_P2P_CONN_NAME = "hostb_conn_ipv6_p2p"
HOSTB_IPSEC_IPV6_CS_CONN_NAME = "hostb_conn_ipv6_cs"
HOSTB_IPSEC_CONN_CONTENT = """
config setup
    protostack=netkey

conn hostb_conn_crt
    hostaddrfamily=ipv4
    left=192.0.2.152
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftsubnet=0.0.0.0/0
    rightaddresspool=203.0.113.2-203.0.113.100
    leftmodecfgserver=yes
    rightmodecfgclient=yes
    leftsendcert=always
    right=192.0.2.251
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    ikev2=insist

conn hostb_conn_psk
    hostaddrfamily=ipv4
    left=192.0.2.153
    leftid=@hostb-psk.example.org
    leftsubnet=0.0.0.0/0
    rightaddresspool=203.0.113.102-203.0.113.200
    leftmodecfgserver=yes
    rightmodecfgclient=yes
    right=192.0.2.250
    rightid=@hosta-psk.example.org
    authby=secret

conn hostb_conn_rsa
    hostaddrfamily=ipv4
    left=192.0.2.154
    leftid=@hostb-rsa.example.org
    leftrsasigkey={RSA_SIGNATURE_HOSTB}
    leftsubnet=0.0.0.0/0
    rightaddresspool=203.0.113.102-203.0.113.200
    rightrsasigkey={RSA_SIGNATURE_HOSTA}
    leftmodecfgserver=yes
    rightmodecfgclient=yes
    right=192.0.2.249
    rightid=@hosta-rsa.example.org
    authby=rsasig

conn hostb_conn_crt_p2p
    hostaddrfamily=ipv4
    left=192.0.2.155
    leftsubnet=192.0.2.155/32
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=no
    right=192.0.2.248
    rightsubnet=192.0.2.248/32
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    rightmodecfgclient=no
    ikev2=insist

conn hostb_conn_transport
    type=transport
    hostaddrfamily=ipv4
    left=192.0.2.156
    leftsubnet=192.0.2.156/32
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=no
    right=192.0.2.247
    rightsubnet=192.0.2.247/32
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    rightmodecfgclient=no
    ikev2=insist

conn hostb_conn_ipv6_p2p
    hostaddrfamily=ipv6
    clientaddrfamily=ipv6
    left=2001:db8:f::b
    leftsourceip=2001:db8:f::b
    leftsubnet=2001:db8:f::b/128
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=no
    right=2001:db8:f::a
    rightsubnet=2001:db8:f::a/128
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    rightmodecfgclient=no
    ikev2=insist

conn hostb_conn_ipv6_cs
    hostaddrfamily=ipv6
    clientaddrfamily=ipv6
    left=2001:db8:e::b
    leftsourceip=2001:db8:e::b
    leftsubnet=::/0
    rightaddresspool=2001:db8:9::/64
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=yes
    rightmodecfgclient=yes
    leftsendcert=always
    right=2001:db8:e::a
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    ikev2=insist
"""
HOSTB_IPSEC_NSS_DIR = "/tmp/hostb_ipsec_nss"
HOSTB_IPSEC_SECRETS_FILE = "/tmp/hostb_ipsec_secrets"
HOSTB_IPSEC_CONF_DIR = "/tmp/hostb_ipsec_conf"
HOSTB_IPSEC_RUN_DIR = "/tmp/hostb_ipsec_run"

HOSTB_IPSEC_CONF_CONTENT = """
include /etc/crypto-policies/back-ends/libreswan.config
include /tmp/hostb_ipsec_conf/ipsec.d/*.conf
"""

PSK = "JjyNzrnHTnMqzloKaMuq2uCfJvSSUqTYdAXqD2U2OCFyVIJUUEHmXihBbPrUcmik"
SECRET_LINE = f""": PSK "{PSK}"
"""

RSA_SIGNATURES = {}

if is_el8():
    DEFAULT_IPSEC_NSS_DIR = "/etc/ipsec.d"
else:
    DEFAULT_IPSEC_NSS_DIR = "/var/lib/ipsec/nss"

LIBRESWAN_CONF_DIR = "/etc/ipsec.d"
TEST_P12_PASSWORD = "nmstate_test!"

CERT_DIR = f"{os.path.dirname(os.path.realpath(__file__))}/test_ipsec_certs"

RETRY_COUNT = 10


@pytest.fixture(scope="module")
def setup_hostb_ipsec_conn():
    try:
        if not os.path.exists(HOSTB_IPSEC_CONF_DIR):
            os.mkdir(f"{HOSTB_IPSEC_CONF_DIR}")
            os.mkdir(f"{HOSTB_IPSEC_CONF_DIR}/ipsec.d")
        if not os.path.exists(HOSTB_IPSEC_NSS_DIR):
            os.mkdir(f"{HOSTB_IPSEC_NSS_DIR}")

        shutil.copytree(
            "/etc/ipsec.d/policies/", f"{HOSTB_IPSEC_CONF_DIR}/policies"
        )

        _init_libreswan_nss_db(HOSTB_IPSEC_NSS_DIR)
        RSA_SIGNATURES["hostb"] = _new_rsa_hostkey(HOSTB_IPSEC_NSS_DIR)
        _import_certs(HOSTB_IPSEC_NSS_DIR)

        conn_conf_file_path = (
            f"{HOSTB_IPSEC_CONF_DIR}/ipsec.d/{HOSTB_IPSEC_CONF_NAME}.conf"
        )
        with open(conn_conf_file_path, "w") as fd:
            fd.write(
                HOSTB_IPSEC_CONN_CONTENT.format(
                    RSA_SIGNATURE_HOSTA=RSA_SIGNATURES["hosta"],
                    RSA_SIGNATURE_HOSTB=RSA_SIGNATURES["hostb"],
                )
            )
        with open(f"{HOSTB_IPSEC_CONF_DIR}/ipsec.conf", "w") as fd:
            fd.write(HOSTB_IPSEC_CONF_CONTENT)
        with open(HOSTB_IPSEC_SECRETS_FILE, "w") as fd:
            fd.write(SECRET_LINE)

        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip link add {HOSTB_DUMMY_NIC} type dummy".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip link set {HOSTB_DUMMY_NIC} up".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip addr add {HOSTB_EXT_IP}/32 dev {HOSTB_DUMMY_NIC}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip addr add {HOSTB_EXT_IPV6}/128 dev {HOSTB_DUMMY_NIC}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip route add {HOSTB_VPN_SUBNET} dev {HOSTB_NIC}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip route add {HOSTB_VPN_SUBNET6} dev {HOSTB_NIC}".split(),
            check=True,
        )

        for ip in [
            HOSTB_IPV4_CRT,
            HOSTB_IPV4_PSK,
            HOSTB_IPV4_RSA,
            HOSTB_IPV4_CRT_P2P,
            HOSTB_IPV4_TRANSPORT,
        ]:
            cmdlib.exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ip addr add {ip}/24 dev {HOSTB_NIC}".split(),
                check=True,
            )

        for ipv6 in [HOSTB_IPV6_P2P, HOSTB_IPV6_CS]:
            cmdlib.exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ip -6 addr add {ipv6}/64 dev {HOSTB_NIC}".split(),
                check=True,
            )

        # Need to wait 2 seconds for IPv6 duplicate address detection,
        # otherwise the `pluto` will not listen on any IPv6 address
        time.sleep(2)

        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} ipsec pluto "
            f"--config {HOSTB_IPSEC_CONF_DIR}/ipsec.conf "
            f"--secretsfile {HOSTB_IPSEC_SECRETS_FILE} "
            f"--ipsecdir {HOSTB_IPSEC_CONF_DIR} "
            f"--nssdir {HOSTB_IPSEC_NSS_DIR} "
            f"--rundir {HOSTB_IPSEC_RUN_DIR}".split(),
            check=True,
        )
        for conn_name in [
            HOSTB_IPSEC_CRT_CONN_NAME,
            HOSTB_IPSEC_RSA_CONN_NAME,
            HOSTB_IPSEC_PSK_CONN_NAME,
            HOSTB_IPSEC_CRT_P2P_CONN_NAME,
            HOSTB_IPSEC_TRANSPORET_CONN_NAME,
            HOSTB_IPSEC_IPV6_P2P_CONN_NAME,
            HOSTB_IPSEC_IPV6_CS_CONN_NAME,
        ]:
            cmdlib.exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
                f"--config {conn_conf_file_path} "
                f"--add {conn_name}".split(),
                check=True,
            )
            cmdlib.exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
                f"--asynchronous --up {conn_name}".split(),
                check=True,
            )
        yield
    finally:
        _clean_hostb()


def _clean_hostb():
    if os.path.exists(HOSTB_IPSEC_NSS_DIR):
        shutil.rmtree(HOSTB_IPSEC_NSS_DIR)
    if os.path.exists(HOSTB_IPSEC_CONF_DIR):
        shutil.rmtree(HOSTB_IPSEC_CONF_DIR)
    if os.path.exists(HOSTB_IPSEC_SECRETS_FILE):
        os.unlink(HOSTB_IPSEC_SECRETS_FILE)
    pid_file = f"{HOSTB_IPSEC_RUN_DIR}/pluto.pid"
    if os.path.exists(pid_file):
        with open(pid_file) as fd:
            pid = fd.read().strip()
            cmdlib.exec_cmd(f"kill {pid}".split(), check=True)
    if os.path.exists(HOSTB_IPSEC_RUN_DIR):
        shutil.rmtree(HOSTB_IPSEC_RUN_DIR)


@pytest.fixture(scope="module")
def setup_hosta_ipsec_env(setup_hosta_ip):
    _init_libreswan_nss_db(DEFAULT_IPSEC_NSS_DIR)
    RSA_SIGNATURES["hosta"] = _new_rsa_hostkey(DEFAULT_IPSEC_NSS_DIR)
    _import_certs(DEFAULT_IPSEC_NSS_DIR)
    cmdlib.exec_cmd("systemctl restart ipsec".split())
    yield
    _init_libreswan_nss_db(DEFAULT_IPSEC_NSS_DIR)
    cmdlib.exec_cmd("systemctl restart ipsec".split())


@pytest.fixture(scope="module")
def ipsec_veth_peer():
    create_veth_pair(HOSTA_NIC, HOSTB_NIC, HOSTB_NS)
    yield
    remove_veth_pair(HOSTA_NIC, HOSTB_NS)


def _new_rsa_hostkey(nss_path):
    cmdlib.exec_cmd(
        f"ipsec newhostkey --nssdir {nss_path}".split(), check=True
    )
    output = cmdlib.exec_cmd(
        f"ipsec showhostkey --nssdir {nss_path} --list".split(), check=True
    )[1].strip()
    ckaid = re.search("ckaid: ([a-f0-9]+)", output).group(1)
    return re.search(
        "leftrsasigkey=(.+)$",
        cmdlib.exec_cmd(
            f"ipsec showhostkey --nssdir {nss_path} "
            f"--left --ckaid {ckaid}".split(),
            check=True,
        )[1].strip(),
    ).group(1)


def _init_libreswan_nss_db(path):
    try:
        for f in glob.glob(f"{path}/*.db"):
            os.remove(f)
    except Exception:
        pass
    cmdlib.exec_cmd(f"ipsec initnss --nssdir {path}".split(), check=True)


def _import_certs(nss_dir):
    for host_name in (HOSTA_NAME, HOSTB_NAME):
        p12_file = f"/tmp/{host_name}.p12"
        try:
            cmdlib.exec_cmd(
                f"openssl pkcs12 -export -in {CERT_DIR}/{host_name}.crt "
                f"-inkey {CERT_DIR}/{host_name}.key "
                f"-certfile {CERT_DIR}/ca.crt "
                f"-passout pass:{TEST_P12_PASSWORD} "
                f"-out {p12_file} -name {host_name}".split(),
                check=True,
            )
            # The documented command is `ipsec import` which does not support
            # scriptable password input. The `ipsec import` is just a wrapper
            # of pk12util, hence we use pk12util directly which support passing
            # password in script.
            cmdlib.exec_cmd(
                f"pk12util -i {p12_file} "
                f"-d sql:{nss_dir} -W {TEST_P12_PASSWORD}".split(),
                check=True,
            )
        finally:
            os.unlink(p12_file)
    cmdlib.exec_cmd(
        f"certutil -M -n {CA_NAME} -t CT,, -d sql:{nss_dir}".split(),
        check=True,
    )


@pytest.fixture(scope="module")
def setup_hosta_ip():
    # NM creates the default connection 'Wired connection 1' with dhcp4
    # enabled, but the lack of dhcp server will cause the activation
    # pending and necessitate ipsec test failures
    all_con_dev_pair = cmdlib.exec_cmd(
        "nmcli -g NAME,DEVICE connection show --active".split(), check=True
    )[1]
    for con_dev_pair in all_con_dev_pair.split("\n"):
        if HOSTA_NIC in con_dev_pair:
            con_name = con_dev_pair.split(":")[0]
            cmdlib.exec_cmd(
                ["nmcli", "connection", "del", con_name], check=True
            )
    libnmstate.apply(
        {
            # NetworkManager need default gateway to start ipsec connection
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.NEXT_HOP_INTERFACE: HOSTA_NIC,
                        Route.DESTINATION: "0.0.0.0/0",
                        Route.NEXT_HOP_ADDRESS: HOSTB_IPV4_CRT,
                    },
                    {
                        Route.NEXT_HOP_INTERFACE: HOSTA_NIC,
                        Route.DESTINATION: "::",
                        Route.NEXT_HOP_ADDRESS: HOSTB_IPV6_P2P,
                    },
                ]
            },
            Interface.KEY: [
                {
                    Interface.NAME: HOSTA_NIC,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.UP,
                    Interface.IPV4: {
                        InterfaceIPv4.ENABLED: True,
                        InterfaceIPv4.ADDRESS: [
                            {
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4_CRT,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                            {
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4_PSK,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                            {
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4_RSA,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                            {
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4_CRT_P2P,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                            {
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4_TRANSPORT,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                        ],
                    },
                    Interface.IPV6: {
                        InterfaceIPv6.ENABLED: True,
                        InterfaceIPv6.ADDRESS: [
                            {
                                InterfaceIPv6.ADDRESS_IP: HOSTA_IPV6_P2P,
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            },
                            {
                                InterfaceIPv6.ADDRESS_IP: HOSTA_IPV6_CS,
                                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
                            },
                        ],
                    },
                }
            ],
        }
    )
    # Need to wait 2 seconds for IPv6 duplicate address detection,
    # otherwise the `pluto` will not listen on any IPv6 address
    time.sleep(2)
    yield
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: HOSTA_NIC,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


@pytest.fixture(scope="module", autouse=True)
def ipsec_env(
    ipsec_veth_peer,
    setup_hosta_ipsec_env,
    setup_hostb_ipsec_conn,
):
    yield


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
            InterfaceIP.ADDRESS, []
        ):
            if ip.get(InterfaceIP.ADDRESS_IP, "").startswith(ip_net_prefix):
                return True
        for ip in iface_state.get(Interface.IPV6, {}).get(
            InterfaceIP.ADDRESS, []
        ):
            if ip.get(InterfaceIP.ADDRESS_IP, "").startswith(ip_net_prefix):
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
            left: {HOSTA_IPV4_CRT}
            leftid: '%fromcert'
            leftcert: hosta.example.org
            right: {HOSTB_IPV4_CRT}
            rightid: 'hostb.example.org'
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_CRT, HOSTB_IPV4_CRT
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
    )


@pytest.mark.xfail(
    reason="NetworkManager-libreswan might be too old",
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
            left: {HOSTA_IPV4_CRT}
            leftid: '%fromcert'
            leftcert: hosta.example.org
            right: {HOSTB_IPV4_CRT}
            rightid: '%fromcert'
            rightcert: hostb.example.org
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_CRT, HOSTB_IPV4_CRT
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
    )
    vpn_data = cmdlib.exec_cmd(
        f"nmcli -g vpn.data con show {HOSTA_IPSEC_CONN_NAME}".split()
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
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
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)

    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
    )


def test_ipsec_rsa_authenticate(ipsec_hosta_conn_cleanup):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            leftrsasigkey: {RSA_SIGNATURES["hosta"]}
            left: {HOSTA_IPV4_RSA}
            leftid: 'hosta-rsa.example.org'
            right: {HOSTB_IPV4_RSA}
            rightrsasigkey: {RSA_SIGNATURES["hostb"]}
            rightid: 'hostb-rsa.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_RSA, HOSTB_IPV4_RSA
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
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
            left: {HOSTA_IPV4_CRT}
            leftid: '%fromcert'
            leftcert: hosta.example.org
            leftrsasigkey: '%cert'
            right: {HOSTB_IPV4_CRT}
            rightid: '%fromcert'
            ikev2: insist
            ikelifetime: 24h
            salifetime: 24h""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_CRT, HOSTB_IPV4_CRT
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ipsec-interface: 9
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, "ipsec9"
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
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
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, "ipsec10"
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ipsec-interface: 77
            authby: secret
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, "ipsec77"
    )


@pytest.mark.xfail(
    reason="NetworkManager-libreswan might be too old",
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
            left: {HOSTA_IPV4_CRT_P2P}
            leftid: 'hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {HOSTB_IPV4_CRT_P2P}
            rightid: 'hostb.example.org'
            rightsubnet: {HOSTB_IPV4_CRT_P2P}/32
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_CRT_P2P, HOSTB_IPV4_CRT_P2P
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{HOSTA_IPV4_CRT_P2P}/32",
        f"{HOSTB_IPV4_CRT_P2P}/32",
    )


@pytest.mark.xfail(
    reason="NetworkManager-libreswan might be older than 1.2.20",
)
def test_ipsec_ipv4_libreswan_leftsubnet(
    ipsec_hosta_conn_cleanup,
):
    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          libreswan:
            left: {HOSTA_IPV4_CRT_P2P}
            leftid: 'hosta.example.org'
            leftcert: hosta.example.org
            leftsubnet: {HOSTA_IPV4_CRT_SUBNET}
            leftmodecfgclient: no
            right: {HOSTB_IPV4_CRT_P2P}
            rightid: 'hostb.example.org'
            rightsubnet: {HOSTB_IPV4_CRT_SUBNET}
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_CRT_P2P, HOSTB_IPV4_CRT_P2P
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{HOSTA_IPV4_CRT_SUBNET}",
        f"{HOSTB_IPV4_CRT_SUBNET}",
    )


@pytest.mark.xfail(
    reason="NetworkManager-libreswan might be too old",
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
            left: {HOSTA_IPV4_TRANSPORT}
            leftid: 'hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {HOSTB_IPV4_TRANSPORT}
            rightid: 'hostb.example.org'
            rightsubnet: {HOSTB_IPV4_TRANSPORT}/32
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_TRANSPORT, HOSTB_IPV4_TRANSPORT
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{HOSTA_IPV4_TRANSPORT}/32",
        f"{HOSTB_IPV4_TRANSPORT}/32",
    )


@pytest.mark.xfail(
    reason="This is not supported by latest NM-libreswan yet",
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
            left: {HOSTA_IPV6_P2P}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {HOSTB_IPV6_P2P}
            rightid: '@hostb.example.org'
            rightsubnet: {HOSTB_IPV6_P2P}/128
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV6_P2P, HOSTB_IPV6_P2P
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT,
        _check_ipsec_policy,
        f"{HOSTA_IPV6_P2P}/128",
        f"{HOSTB_IPV6_P2P}/128",
    )


@pytest.mark.xfail(
    reason="This is not supported by latest NM-libreswan yet",
)
def test_ipsec_ipv6_libreswan_client_server(
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
            hostaddrfamily: ipv6
            clientaddrfamily: ipv6
            left: {HOSTA_IPV6_CS}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {HOSTB_IPV6_CS}
            rightid: '@hostb.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV6_CS, HOSTB_IPV6_CS
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX6, HOSTA_NIC
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
    )

    desired_state = yaml.load(
        f"""---
        interfaces:
        - name: hosta_conn
          type: ipsec
          libreswan:
            type: tunnel
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
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
            psk: {PSK}
            left: {HOSTA_IPV4_PSK}
            leftid: 'hosta-psk.example.org'
            right: {HOSTB_IPV4_PSK}
            rightid: 'hostb-psk.example.org'
            ipsec-interface: 99
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_PSK, HOSTB_IPV4_PSK
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, "ipsec99"
    )


# DHCPv4 off with empty IP address means IP disabled for IPSec interface
def test_ipsec_dhcpv4_off_and_empty_ip_addr(
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
            leftrsasigkey: {RSA_SIGNATURES["hosta"]}
            left: {HOSTA_IPV4_RSA}
            leftid: 'hosta-rsa.example.org'
            right: {HOSTB_IPV4_RSA}
            rightrsasigkey: {RSA_SIGNATURES["hostb"]}
            rightid: 'hostb-rsa.example.org'
            ipsec-interface: 97
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_RSA, HOSTB_IPV4_RSA
    )

    iface_state = show_only(["ipsec97"])[Interface.KEY][0]
    assert not iface_state[Interface.IPV4][InterfaceIPv4.ENABLED]


@pytest.mark.xfail(
    reason="This is not supported by latest NM-libreswan yet",
)
def test_ipsec_dhcpv6_off(
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
            hostaddrfamily: ipv6
            clientaddrfamily: ipv6
            left: {HOSTA_IPV6_CS}
            leftid: '@hosta.example.org'
            leftcert: hosta.example.org
            leftmodecfgclient: no
            right: {HOSTB_IPV6_CS}
            rightid: '@hostb.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4_RSA, HOSTB_IPV4_RSA
    )

    iface_state = show_only(["ipsec97"])[Interface.KEY][0]
    assert not iface_state[Interface.IPV6].get(InterfaceIPv6.DHCP)
    assert not iface_state[Interface.IPV6].get(InterfaceIPv6.AUTOCONF)
