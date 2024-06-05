# SPDX-License-Identifier: Apache-2.0

import glob
import os
import re
import shutil
import time

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4
from libnmstate.schema import InterfaceIPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route

from .cmdlib import exec_cmd
from .env import is_el8
from .veth import create_veth_pair
from .veth import remove_veth_pair

CA_NAME = "nmstate-test-ca.example.org"
HOSTB_NIC = "hostb_nic"
HOSTB_DUMMY_NIC = "dummy0"
HOSTB_NS = "nmstate_ipsec_test"
HOSTB_IPSEC_CONF_NAME = "hostb_conn"
HOSTB_IPSEC_CONNS = [
    "hostb_conn_crt",
    "hostb_conn_psk",
    "hostb_conn_rsa",
    "hostb_conn_crt_p2p",
    "hostb_conn_transport",
    "hostb_conn_leftsubnet",
    "hostb_conn_ipv6_p2p",
    "hostb_conn_ipv6_cs",
    "hostb_conn_6in4",
    "hostb_conn_4in6",
]
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
    rightaddresspool=203.0.113.201-203.0.113.210
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

conn hostb_conn_leftsubnet
    hostaddrfamily=ipv4
    left=192.0.2.157
    leftsubnet=192.0.3.0/24
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=no
    right=192.0.2.246
    rightsubnet=192.0.4.0/24
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
    rightaddresspool=2001:db8:9::/120
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=yes
    rightmodecfgclient=yes
    leftsendcert=always
    right=2001:db8:e::a
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    ikev2=insist

conn hostb_conn_6in4
    left=192.0.2.158
    leftsubnet=2001:db8:ab::/64
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=no
    rightmodecfgclient=no
    leftsendcert=always
    right=192.0.2.245
    rightsubnet=2001:db8:aa::/64
    rightid=@hosta.example.org
    rightcert=hosta.example.org
    ikev2=insist

conn hostb_conn_4in6
    left=2001:db8:d::b
    leftsubnet=192.0.3.0/24
    leftid=@hostb.example.org
    leftcert=hostb.example.org
    leftmodecfgserver=no
    rightmodecfgclient=no
    leftsendcert=always
    right=2001:db8:d::a
    rightsubnet=192.0.4.0/24
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

if is_el8():
    DEFAULT_IPSEC_NSS_DIR = "/etc/ipsec.d"
else:
    DEFAULT_IPSEC_NSS_DIR = "/var/lib/ipsec/nss"

LIBRESWAN_CONF_DIR = "/etc/ipsec.d"
TEST_P12_PASSWORD = "nmstate_test!"

CERT_DIR = f"{os.path.dirname(os.path.realpath(__file__))}/../test_ipsec_certs"
PSK = "JjyNzrnHTnMqzloKaMuq2uCfJvSSUqTYdAXqD2U2OCFyVIJUUEHmXihBbPrUcmik"
SECRET_LINE = f""": PSK "{PSK}"
"""


class IpsecTestEnv:
    HOSTA_NIC = "hosta_nic"
    HOSTA_NAME = "hosta.example.org"
    HOSTA_IPV4_CRT = "192.0.2.251"
    HOSTA_IPV4_PSK = "192.0.2.250"
    HOSTA_IPV4_RSA = "192.0.2.249"
    HOSTA_IPV4_CRT_P2P = "192.0.2.248"
    HOSTA_IPV4_TRANSPORT = "192.0.2.247"
    HOSTA_IPV4_IF_SUBNET = "192.0.2.246"
    HOSTA_IPV4_6IN4 = "192.0.2.245"
    HOSTA_IPV4_CRT_SUBNET = "192.0.4.0/24"
    HOSTA_IPSEC_CONN_NAME = "hosta_conn"
    HOSTA_IPV6_P2P = "2001:db8:f::a"
    HOSTA_IPV6_SUBNET = "2001:db8:aa::/64"
    HOSTB_IPV6_P2P = "2001:db8:f::b"
    HOSTA_IPV6_CS = "2001:db8:e::a"
    HOSTB_IPV6_CS = "2001:db8:e::b"
    HOSTA_IPV6_4IN6 = "2001:db8:d::a"
    HOSTB_IPV6_4IN6 = "2001:db8:d::b"
    HOSTB_NAME = "hostb.example.org"
    HOSTB_IPV4_CRT = "192.0.2.152"
    HOSTB_IPV4_PSK = "192.0.2.153"
    HOSTB_IPV4_RSA = "192.0.2.154"
    HOSTB_IPV4_CRT_P2P = "192.0.2.155"
    HOSTB_IPV4_TRANSPORT = "192.0.2.156"
    HOSTB_IPV4_IF_SUBNET = "192.0.2.157"
    HOSTB_IPV4_6IN4 = "192.0.2.158"
    HOSTB_IPV4_CRT_SUBNET = "192.0.3.0/24"
    HOSTB_VPN_SUBNET_PREFIX = "203.0.113"
    HOSTB_VPN_SUBNET = f"{HOSTB_VPN_SUBNET_PREFIX}.0/24"
    HOSTB_VPN_SUBNET_PREFIX6 = "2001:db8:9::"
    HOSTB_VPN_SUBNET6 = f"{HOSTB_VPN_SUBNET_PREFIX6}/64"
    HOSTB_IPV6_SUBNET = "2001:db8:ab::/64"
    HOSTB_EXT_IP = "198.51.100.1"
    HOSTB_EXT_IPV6 = "2001:db8:1::"
    PSK = PSK

    @property
    def rsa_signatures(self):
        return self._rsa_signatures

    def __init__(self):
        self._inited = False
        self._rsa_signatures = {}

    def __enter__(self):
        if not self._inited:
            self.setup()
            self._inited = True
        return self

    def __exit__(self, _type, _value, _traceback):
        self.cleanup()

    def setup(self):
        try:
            remove_veth_pair(IpsecTestEnv.HOSTA_NIC, HOSTB_NS)
        except Exception:
            pass
        try:
            create_veth_pair(IpsecTestEnv.HOSTA_NIC, HOSTB_NIC, HOSTB_NS)
            setup_hosta_ip()
            self._setup_hosta_ipsec_env()
            self._setup_hostb_ipsec_conn()
        except Exception as e:
            self.cleanup()
            raise e

    def cleanup(self):
        try:
            _init_libreswan_nss_db(DEFAULT_IPSEC_NSS_DIR)
        except Exception:
            pass
        exec_cmd("systemctl restart ipsec".split())
        _clean_hostb()
        _clean_hosta()
        remove_veth_pair(IpsecTestEnv.HOSTA_NIC, HOSTB_NS)

    def _setup_hosta_ipsec_env(self):
        _init_libreswan_nss_db(DEFAULT_IPSEC_NSS_DIR)
        self._rsa_signatures["hosta"] = _new_rsa_hostkey(DEFAULT_IPSEC_NSS_DIR)
        _import_certs(DEFAULT_IPSEC_NSS_DIR)
        exec_cmd("systemctl restart ipsec".split())

    def _setup_hostb_ipsec_conn(self):
        if not os.path.exists(HOSTB_IPSEC_CONF_DIR):
            os.mkdir(f"{HOSTB_IPSEC_CONF_DIR}")
            os.mkdir(f"{HOSTB_IPSEC_CONF_DIR}/ipsec.d")
        if not os.path.exists(HOSTB_IPSEC_NSS_DIR):
            os.mkdir(f"{HOSTB_IPSEC_NSS_DIR}")

        shutil.copytree(
            "/etc/ipsec.d/policies/", f"{HOSTB_IPSEC_CONF_DIR}/policies"
        )

        _init_libreswan_nss_db(HOSTB_IPSEC_NSS_DIR)
        self._rsa_signatures["hostb"] = _new_rsa_hostkey(HOSTB_IPSEC_NSS_DIR)
        _import_certs(HOSTB_IPSEC_NSS_DIR)

        conn_conf_file_path = (
            f"{HOSTB_IPSEC_CONF_DIR}/ipsec.d/{HOSTB_IPSEC_CONF_NAME}.conf"
        )
        with open(conn_conf_file_path, "w") as fd:
            fd.write(
                HOSTB_IPSEC_CONN_CONTENT.format(
                    RSA_SIGNATURE_HOSTA=self.rsa_signatures["hosta"],
                    RSA_SIGNATURE_HOSTB=self.rsa_signatures["hostb"],
                )
            )
        with open(f"{HOSTB_IPSEC_CONF_DIR}/ipsec.conf", "w") as fd:
            fd.write(HOSTB_IPSEC_CONF_CONTENT)
        with open(HOSTB_IPSEC_SECRETS_FILE, "w") as fd:
            fd.write(SECRET_LINE)

        exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip link add {HOSTB_DUMMY_NIC} type dummy".split(),
            check=True,
        )
        exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip link set {HOSTB_DUMMY_NIC} up".split(),
            check=True,
        )
        exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip addr add {IpsecTestEnv.HOSTB_EXT_IP}/32 "
            f"dev {HOSTB_DUMMY_NIC}".split(),
            check=True,
        )
        exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip addr add {IpsecTestEnv.HOSTB_EXT_IPV6}/128 "
            f"dev {HOSTB_DUMMY_NIC}".split(),
            check=True,
        )
        exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip route add {IpsecTestEnv.HOSTB_VPN_SUBNET} "
            f"dev {HOSTB_NIC}".split(),
            check=True,
        )
        exec_cmd(
            f"ip netns exec {HOSTB_NS} "
            f"ip route add {IpsecTestEnv.HOSTB_VPN_SUBNET6} "
            f"dev {HOSTB_NIC}".split(),
            check=True,
        )

        for ip in [
            IpsecTestEnv.HOSTB_IPV4_CRT,
            IpsecTestEnv.HOSTB_IPV4_PSK,
            IpsecTestEnv.HOSTB_IPV4_RSA,
            IpsecTestEnv.HOSTB_IPV4_CRT_P2P,
            IpsecTestEnv.HOSTB_IPV4_IF_SUBNET,
            IpsecTestEnv.HOSTB_IPV4_TRANSPORT,
            IpsecTestEnv.HOSTB_IPV4_6IN4,
        ]:
            exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ip addr add {ip}/24 dev {HOSTB_NIC}".split(),
                check=True,
            )

        for ipv6 in [
            IpsecTestEnv.HOSTB_IPV6_P2P,
            IpsecTestEnv.HOSTB_IPV6_CS,
            IpsecTestEnv.HOSTB_IPV6_4IN6,
        ]:
            exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ip -6 addr add {ipv6}/64 dev {HOSTB_NIC}".split(),
                check=True,
            )

        # Need to wait 2 seconds for IPv6 duplicate address detection,
        # otherwise the `pluto` will not listen on any IPv6 address
        time.sleep(5)

        exec_cmd(
            f"ip netns exec {HOSTB_NS} ipsec pluto "
            f"--config {HOSTB_IPSEC_CONF_DIR}/ipsec.conf "
            f"--secretsfile {HOSTB_IPSEC_SECRETS_FILE} "
            f"--ipsecdir {HOSTB_IPSEC_CONF_DIR} "
            f"--nssdir {HOSTB_IPSEC_NSS_DIR} "
            f"--rundir {HOSTB_IPSEC_RUN_DIR}".split(),
            check=True,
        )
        for conn_name in HOSTB_IPSEC_CONNS:
            exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
                f"--config {conn_conf_file_path} "
                f"--add {conn_name}".split(),
                check=True,
            )
            exec_cmd(
                f"ip netns exec {HOSTB_NS} "
                f"ipsec auto --ctlsocket {HOSTB_IPSEC_RUN_DIR}/pluto.ctl "
                f"--asynchronous --up {conn_name}".split(),
                check=True,
            )


def setup_hosta_ip():
    # NM creates the default connection 'Wired connection 1' with dhcp4
    # enabled, but the lack of dhcp server will cause the activation
    # pending and necessitate ipsec test failures
    all_con_dev_pair = exec_cmd(
        "nmcli -g NAME,DEVICE connection show --active".split(), check=True
    )[1]
    for con_dev_pair in all_con_dev_pair.split("\n"):
        if IpsecTestEnv.HOSTA_NIC in con_dev_pair:
            con_name = con_dev_pair.split(":")[0]
            exec_cmd(["nmcli", "connection", "del", con_name], check=True)

    desired_state = {
        # NetworkManager need default gateway to start ipsec connection
        Route.KEY: {
            Route.CONFIG: [
                {
                    Route.NEXT_HOP_INTERFACE: IpsecTestEnv.HOSTA_NIC,
                    Route.DESTINATION: "0.0.0.0/0",
                    Route.NEXT_HOP_ADDRESS: IpsecTestEnv.HOSTB_IPV4_CRT,
                },
                {
                    Route.NEXT_HOP_INTERFACE: IpsecTestEnv.HOSTA_NIC,
                    Route.DESTINATION: "::",
                    Route.NEXT_HOP_ADDRESS: IpsecTestEnv.HOSTB_IPV6_P2P,
                },
            ]
        },
        Interface.KEY: [
            {
                Interface.NAME: IpsecTestEnv.HOSTA_NIC,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    InterfaceIPv4.ENABLED: True,
                    InterfaceIPv4.ADDRESS: [],
                },
                Interface.IPV6: {
                    InterfaceIPv6.ENABLED: True,
                    InterfaceIPv6.ADDRESS: [],
                },
            }
        ],
    }

    for ip in [
        IpsecTestEnv.HOSTA_IPV4_CRT,
        IpsecTestEnv.HOSTA_IPV4_PSK,
        IpsecTestEnv.HOSTA_IPV4_RSA,
        IpsecTestEnv.HOSTA_IPV4_CRT_P2P,
        IpsecTestEnv.HOSTA_IPV4_IF_SUBNET,
        IpsecTestEnv.HOSTA_IPV4_TRANSPORT,
        IpsecTestEnv.HOSTA_IPV4_6IN4,
    ]:
        desired_state[Interface.KEY][0][Interface.IPV4][
            InterfaceIPv4.ADDRESS
        ].append(
            {
                InterfaceIPv4.ADDRESS_IP: ip,
                InterfaceIPv4.ADDRESS_PREFIX_LENGTH: 24,
            }
        )
    for ip in [
        IpsecTestEnv.HOSTA_IPV6_P2P,
        IpsecTestEnv.HOSTA_IPV6_CS,
        IpsecTestEnv.HOSTA_IPV6_4IN6,
    ]:
        desired_state[Interface.KEY][0][Interface.IPV6][
            InterfaceIPv6.ADDRESS
        ].append(
            {
                InterfaceIPv6.ADDRESS_IP: ip,
                InterfaceIPv6.ADDRESS_PREFIX_LENGTH: 64,
            }
        )

    libnmstate.apply(desired_state)
    # Need to wait 2 seconds for IPv6 duplicate address detection,
    # otherwise the `pluto` will not listen on any IPv6 address
    time.sleep(2)


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
            exec_cmd(f"kill {pid}".split(), check=True)
    if os.path.exists(HOSTB_IPSEC_RUN_DIR):
        shutil.rmtree(HOSTB_IPSEC_RUN_DIR)


def _clean_hosta():
    libnmstate.apply(
        {
            Interface.KEY: [
                {
                    Interface.NAME: IpsecTestEnv.HOSTA_NIC,
                    Interface.TYPE: InterfaceType.ETHERNET,
                    Interface.STATE: InterfaceState.ABSENT,
                }
            ]
        }
    )


def _new_rsa_hostkey(nss_path):
    exec_cmd(f"ipsec newhostkey --nssdir {nss_path}".split(), check=True)
    output = exec_cmd(
        f"ipsec showhostkey --nssdir {nss_path} --list".split(), check=True
    )[1].strip()
    ckaid = re.search("ckaid: ([a-f0-9]+)", output).group(1)
    return re.search(
        "leftrsasigkey=(.+)$",
        exec_cmd(
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
    exec_cmd(f"ipsec initnss --nssdir {path}".split(), check=True)


def _import_certs(nss_dir):
    for host_name in (IpsecTestEnv.HOSTA_NAME, IpsecTestEnv.HOSTB_NAME):
        p12_file = f"/tmp/{host_name}.p12"
        try:
            exec_cmd(
                f"openssl pkcs12 -export -in {CERT_DIR}/{host_name}.crt "
                f"-inkey {CERT_DIR}/{host_name}.key "
                f"-certfile {CERT_DIR}/ca.crt "
                f"-passout pass:{TEST_P12_PASSWORD} "
                f"-out {p12_file} -name {host_name}".split(),
                check=True,
            )
            # The documented command is `ipsec import` which does not
            # support scriptable password input. The `ipsec import` is just
            # a wrapper of pk12util, hence we use pk12util directly which
            # support passing password in script.
            exec_cmd(
                f"pk12util -i {p12_file} "
                f"-d sql:{nss_dir} -W {TEST_P12_PASSWORD}".split(),
                check=True,
            )
        finally:
            os.unlink(p12_file)
    exec_cmd(
        f"certutil -M -n {CA_NAME} -t CT,, -d sql:{nss_dir}".split(),
        check=True,
    )
