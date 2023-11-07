# SPDX-License-Identifier: Apache-2.0

import os
import glob
import shutil

import pytest
import yaml

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIP
from libnmstate.schema import InterfaceIPv4
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
HOSTA_IPV4 = "192.0.2.251"
HOSTA_IPV4_PSK = "192.0.2.250"
HOSTA_IPSEC_CONN_NAME = "hosta_conn"
HOSTB_NAME = "hostb.example.org"
HOSTB_NIC = "hostb_nic"
HOSTB_IPV4 = "192.0.2.252"
HOSTB_IPV4_PSK = "192.0.2.253"
HOSTB_VPN_SUBNET_PREFIX = "203.0.113"
HOSTB_VPN_SUBNET = f"{HOSTB_VPN_SUBNET_PREFIX}.0/24"
HOSTB_EXT_IP = "198.51.100.1"
HOSTB_DUMMY_NIC = "dummy0"
HOSTB_NS = "nmstate_ipsec_test"
HOSTB_IPSEC_CONN_NAME = "hostb_conn"
HOSTB_IPSEC_PSK_CONN_NAME = "hostb_conn_psk"
HOSTB_IPSEC_CONN_CONTENT = """
config setup
    protostack=netkey

conn hostb_conn
    hostaddrfamily=ipv4
    left=192.0.2.252
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
    left=192.0.2.253
    leftid=@hostb-psk.example.org
    leftsubnet=0.0.0.0/0
    rightaddresspool=203.0.113.102-203.0.113.200
    leftmodecfgserver=yes
    rightmodecfgclient=yes
    right=192.0.2.250
    rightid=@hosta-psk.example.org
    authby=secret
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
        conn_conf_file_path = (
            f"{HOSTB_IPSEC_CONF_DIR}/ipsec.d/{HOSTB_IPSEC_CONN_NAME}.conf"
        )
        with open(conn_conf_file_path, "w") as fd:
            fd.write(HOSTB_IPSEC_CONN_CONTENT)
        with open(f"{HOSTB_IPSEC_CONF_DIR}/ipsec.conf", "w") as fd:
            fd.write(HOSTB_IPSEC_CONF_CONTENT)
        with open(HOSTB_IPSEC_SECRETS_FILE, "w") as fd:
            fd.write(SECRET_LINE)

        shutil.copytree(
            "/etc/ipsec.d/policies/", f"{HOSTB_IPSEC_CONF_DIR}/policies"
        )

        _init_libreswan_nss_db(HOSTB_IPSEC_NSS_DIR)
        _import_certs(HOSTB_IPSEC_NSS_DIR)

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
            f"ip addr add {HOSTB_IPV4}/24 dev {HOSTB_NIC}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip addr add {HOSTB_IPV4_PSK}/24 dev {HOSTB_NIC}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip route add {HOSTB_VPN_SUBNET} dev {HOSTB_NIC}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} ipsec pluto "
            f"--config {HOSTB_IPSEC_CONF_DIR}/ipsec.conf "
            f"--secretsfile {HOSTB_IPSEC_SECRETS_FILE} "
            f"--ipsecdir {HOSTB_IPSEC_CONF_DIR} "
            f"--nssdir {HOSTB_IPSEC_NSS_DIR} "
            f"--rundir {HOSTB_IPSEC_RUN_DIR}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
            f"--config {conn_conf_file_path} "
            f"--add {HOSTB_IPSEC_CONN_NAME}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
            f"--config {conn_conf_file_path} "
            f"--add {HOSTB_IPSEC_PSK_CONN_NAME}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
            f"--asynchronous --up {HOSTB_IPSEC_CONN_NAME}".split(),
            check=True,
        )
        cmdlib.exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
            f"--asynchronous --up {HOSTB_IPSEC_PSK_CONN_NAME}".split(),
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
    libnmstate.apply(
        {
            # NetworkManager need default gateway to start ipsec connection
            Route.KEY: {
                Route.CONFIG: [
                    {
                        Route.NEXT_HOP_INTERFACE: HOSTA_NIC,
                        Route.DESTINATION: "0.0.0.0/0",
                        Route.NEXT_HOP_ADDRESS: HOSTB_IPV4,
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
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                            {
                                InterfaceIPv4.ADDRESS_IP: HOSTA_IPV4_PSK,
                                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
                            },
                        ],
                    },
                }
            ],
        }
    )
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


def _check_ipsec_ip(ip_net_prefix, nic):
    iface_state = show_only([nic])[Interface.KEY][0]
    for ip in iface_state.get(Interface.IPV4, {}).get(InterfaceIP.ADDRESS, []):
        if ip.get(InterfaceIP.ADDRESS_IP, "").startswith(ip_net_prefix):
            return True
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
        """---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            left: 192.0.2.251
            leftid: '%fromcert'
            leftcert: hosta.example.org
            right: 192.0.2.252
            rightid: 'hostb.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec, HOSTA_IPV4, HOSTB_IPV4
    )
    assert retry_till_true_or_timeout(
        RETRY_COUNT, _check_ipsec_ip, HOSTB_VPN_SUBNET_PREFIX, HOSTA_NIC
    )


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
            left: 192.0.2.250
            leftid: 'hosta-psk.example.org'
            right: 192.0.2.253
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
            left: 192.0.2.250
            leftid: 'hosta-psk.example.org'
            right: 192.0.2.253
            rightid: 'hostb-psk.example.org'
            ikev2: insist""",
        Loader=yaml.SafeLoader,
    )
    libnmstate.apply(desired_state)

    desired_state = yaml.load(
        """---
        interfaces:
        - name: hosta_conn
          type: ipsec
          ipv4:
            enabled: true
            dhcp: true
          libreswan:
            psk: <_password_hid_by_nmstate>
            left: 192.0.2.250
            leftid: 'hosta-psk.example.org'
            right: 192.0.2.253
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
