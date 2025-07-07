# SPDX-License-Identifier: Apache-2.0

import glob
import os
import time
from subprocess import SubprocessError

import libnmstate
from libnmstate.schema import Interface
from libnmstate.schema import InterfaceIPv4 as IPv4
from libnmstate.schema import InterfaceIPv6 as IPv6
from libnmstate.schema import InterfaceState
from libnmstate.schema import InterfaceType
from libnmstate.schema import Route

from .cmdlib import exec_cmd
from .veth import create_veth_pair
from .veth import remove_veth_pair

SRV_CONTAINER_IMG = "quay.io/nmstate/test-env:libreswan-srv-c9s"
SRV_CONTAINER_NAME = "nmstate-ipsec-srv"
SRV_NAMESPACE = "ipsec_test_srv"
TEST_FILES_DIR = "test_ipsec_files"
TEST_FILES_DIR = (
    f"{os.path.dirname(os.path.realpath(__file__))}/../test_ipsec_files"
)

CLI_P12_PATH = f"{TEST_FILES_DIR}/cli-a.example.org.p12"
SRV_P12_PATH = f"{TEST_FILES_DIR}/ipsec-srv.example.org.p12"
DEFAULT_IPSEC_NSS_DIR = "/var/lib/ipsec/nss"

SRV_PSK_GW_CONF = f"{TEST_FILES_DIR}/psk_gw.conf"
SRV_RSA_GW_CONF = f"{TEST_FILES_DIR}/rsa_gw.conf"
SRV_CERT_GW_CONF = f"{TEST_FILES_DIR}/cert_gw.conf"
SRV_P2P_CONF = f"{TEST_FILES_DIR}/p2p.conf"
SRV_SITE_TO_SITE_CONF = f"{TEST_FILES_DIR}/site_to_site.conf"
SRV_TRANSPORT_CONF = f"{TEST_FILES_DIR}/transport.conf"
SRV_HOST_TO_SITE_CONF = f"{TEST_FILES_DIR}/host_to_site.conf"
SRV_4IN6_6IN4_CONF = f"{TEST_FILES_DIR}/4in6_6in4.conf"


class IpsecTestEnv:
    """
    Steps:
        1. `IpsecTestEnv.setup()`
        2. `IpsecTestEnv.start_ipsec_srv_XXX`
        3. Run your tests
        4. `IpsecTestEnv.cleanup()`
    """

    SRV_ADDR_V4 = "192.0.2.1"
    CLI_ADDR_V4 = "192.0.2.2"
    SRV_ADDR_V6 = "2001:db8:a::1"
    CLI_ADDR_V6 = "2001:db8:a::2"
    SRV_POOL_PREFIX_V4 = "10.0.1"
    SRV_POOL_PREFIX_V6 = "2001:db8:c::"
    SRV_SUBNET_V4 = "10.0.0.0/24"
    SRV_SUBNET_V6 = "fd00:a::/64"
    CLI_SUBNET_V4 = "10.0.9.0/24"
    CLI_SUBNET_V6 = "fd00:9::/64"
    CLI_SUBNET_NIC_NAME = "cli-sub0"
    CLI_SUBADDR_V4 = "10.0.9.2"
    CLI_SUBADDR_V6 = "fd00:9::2"
    CLI_KEY_ID = "cli-a.example.org"
    SRV_KEY_ID = "ipsec-srv.example.org"
    CLI_NIC = "ipsec_cli0"
    SRV_NIC = "ipsec_srv0"
    PSK = "JjyNzrnHTnMqzloKaMuq2uCfJvSSUqTYdAXqD2U2OCFyVIJUUEHmXihBbPrUcmik"
    SRV_RSA = (
        "0sAwEAAbZ8FjGFvVcmtBidI2f/ZKXWXZ6XrG1mREQWWZMr19domUQwJQjpN"
        "KXCFCGWgG7FNd8fmpgpJPUVpflTs5U+9tYC5daLQrmoO7Jlx4IPBOgem4ps"
        "mnrMBzad5vpSxfj5+yVGM2OvSVyHJxJjpiFnHk1YldJWZaz3HHZY+dznkTH"
        "wzKrWMYJOCV+48xsr0mxcxdUbQKerYOq0StJmXcL9gjgp9yDpbcWcCUqGtk"
        "hW4+vuu/US8Unp216tCdgTdWMIu4rO6+Z/sWQ7TSwK+swrpy/yslau9xBR3"
        "jmOUPEyv+/JxxlmKF0WoqTvWrz/Kgg913yep8aSLmSHSUzco2mR8ec="
    )
    CLI_RSA = (
        "0sAwEAAeEQ7pKlVTTsAeb4EWCLJqV1wI/QvCDeh2nfIcSKtzXqc8T2Llt4+"
        "i9fyGzM4ZHqoSbSarMFZ2+B8iIIr6ElChrniszxAG7hczHL+4oLTUbCeC81"
        "h84waZc9OTB2MUemEMm5KI3XtsY9p+E/lfRIFyBiX4slnIUKaf3A/PvXtAQ"
        "iVrwV8t14RktDTqNVv1WT/AaiAia+GbmNfHQhIXZemQ1Ng4zI9ZoQZKPVCF"
        "Uek6imRehfI5JEOpTd1Uwk5amd9ZdzWntZ+PUS0YGMYs37YRqNNr+Gh3gEn"
        "ZM9ZiX2oLC6i+osr2u2UhvQ6PXVvOwdn19u310kyH+T6T4wQLnZZ68="
    )

    def setup():
        try:
            start_ipsec_srv_container()
            setup_cli_ip()
            IpsecTestEnv.load_cli_key()

        except Exception as e:
            IpsecTestEnv.cleanup()
            raise e

    def load_both_srv_cli_keys():
        """ """
        _init_libreswan_nss_db()
        _import_certs(CLI_P12_PATH, IpsecTestEnv.CLI_KEY_ID)
        _import_certs(SRV_P12_PATH, IpsecTestEnv.SRV_KEY_ID)
        _restart_ipsec_service()

    def load_cli_key():
        _init_libreswan_nss_db()
        _import_certs(CLI_P12_PATH, IpsecTestEnv.CLI_KEY_ID)
        _restart_ipsec_service()

    def start_ipsec_srv_psk_gw():
        _start_ipsec_connection(SRV_PSK_GW_CONF)

    def start_ipsec_srv_rsa_gw():
        _start_ipsec_connection(SRV_RSA_GW_CONF)

    def start_ipsec_srv_cert_gw():
        _start_ipsec_connection(SRV_CERT_GW_CONF)

    def start_ipsec_srv_p2p():
        _start_ipsec_connection(SRV_P2P_CONF)

    def start_ipsec_srv_site_to_site():
        _start_ipsec_connection(SRV_SITE_TO_SITE_CONF)

    def start_ipsec_srv_transport():
        _start_ipsec_connection(SRV_TRANSPORT_CONF)

    def start_ipsec_srv_host_to_site():
        _start_ipsec_connection(SRV_HOST_TO_SITE_CONF)

    def start_ipsec_srv_4in6_6in4():
        _start_ipsec_connection(SRV_4IN6_6IN4_CONF)

    def cleanup():
        try:
            _init_libreswan_nss_db()
        except Exception:
            pass
        _restart_ipsec_service()
        exec_cmd(
            f"podman rm -f {SRV_CONTAINER_NAME}".split(),
            check=True,
        )
        libnmstate.apply(
            {
                Interface.KEY: [
                    {
                        Interface.NAME: IpsecTestEnv.CLI_NIC,
                        Interface.TYPE: InterfaceType.ETHERNET,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                    {
                        Interface.NAME: IpsecTestEnv.CLI_SUBNET_NIC_NAME,
                        Interface.TYPE: InterfaceType.DUMMY,
                        Interface.STATE: InterfaceState.ABSENT,
                    },
                ]
            }
        )
        remove_veth_pair(IpsecTestEnv.CLI_NIC, SRV_NAMESPACE)


def setup_cli_ip():
    # NM creates the default connection 'Wired connection 1' with dhcp4
    # enabled, but the lack of dhcp server will cause the activation
    # pending and necessitate ipsec test failures
    all_con_dev_pair = exec_cmd(
        "nmcli -g NAME,DEVICE connection show --active".split(), check=True
    )[1]
    for con_dev_pair in all_con_dev_pair.split("\n"):
        if IpsecTestEnv.CLI_NIC in con_dev_pair:
            con_name = con_dev_pair.split(":")[0]
            exec_cmd(["nmcli", "connection", "del", con_name], check=True)

    desired_state = {
        # NetworkManager need default gateway to start ipsec connection
        Route.KEY: {
            Route.CONFIG: [
                {
                    Route.NEXT_HOP_INTERFACE: IpsecTestEnv.CLI_NIC,
                    Route.DESTINATION: "0.0.0.0/0",
                    Route.NEXT_HOP_ADDRESS: IpsecTestEnv.SRV_ADDR_V4,
                },
                {
                    Route.NEXT_HOP_INTERFACE: IpsecTestEnv.CLI_NIC,
                    Route.DESTINATION: "::",
                    Route.NEXT_HOP_ADDRESS: IpsecTestEnv.SRV_ADDR_V6,
                },
            ]
        },
        Interface.KEY: [
            {
                Interface.NAME: IpsecTestEnv.CLI_NIC,
                Interface.TYPE: InterfaceType.ETHERNET,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    IPv4.ENABLED: True,
                    IPv4.DHCP: False,
                    IPv4.ADDRESS: [
                        {
                            IPv4.ADDRESS_IP: IpsecTestEnv.CLI_ADDR_V4,
                            IPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Interface.IPV6: {
                    IPv6.ENABLED: True,
                    IPv6.DHCP: False,
                    IPv6.AUTOCONF: False,
                    IPv6.ADDRESS: [
                        {
                            IPv6.ADDRESS_IP: IpsecTestEnv.CLI_ADDR_V6,
                            IPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            },
            {
                Interface.NAME: IpsecTestEnv.CLI_SUBNET_NIC_NAME,
                Interface.TYPE: InterfaceType.DUMMY,
                Interface.STATE: InterfaceState.UP,
                Interface.IPV4: {
                    IPv4.ENABLED: True,
                    IPv4.DHCP: False,
                    IPv4.ADDRESS: [
                        {
                            IPv4.ADDRESS_IP: IpsecTestEnv.CLI_SUBADDR_V4,
                            IPv4.ADDRESS_PREFIX_LENGTH: 24,
                        }
                    ],
                },
                Interface.IPV6: {
                    IPv6.ENABLED: True,
                    IPv6.DHCP: False,
                    IPv6.AUTOCONF: False,
                    IPv6.ADDRESS: [
                        {
                            IPv6.ADDRESS_IP: IpsecTestEnv.CLI_SUBADDR_V6,
                            IPv6.ADDRESS_PREFIX_LENGTH: 64,
                        }
                    ],
                },
            },
        ],
    }

    libnmstate.apply(desired_state)
    # Need to wait 2 seconds for IPv6 duplicate address detection,
    # otherwise the `pluto` will not listen on any IPv6 address
    time.sleep(2)


def _init_libreswan_nss_db():
    try:
        for f in glob.glob(f"{DEFAULT_IPSEC_NSS_DIR}/*.db"):
            os.remove(f)
    except Exception:
        pass
    exec_cmd(
        f"ipsec initnss --nssdir {DEFAULT_IPSEC_NSS_DIR}".split(), check=True
    )


def _import_certs(key_path, key_id):
    # The documented command is `ipsec import` which does not
    # support scriptable password input. The `ipsec import` is just
    # a wrapper of pk12util, hence we use pk12util directly which
    # support passing password in script.
    exec_cmd(
        [
            "pk12util",
            "-i",
            key_path,
            "-d",
            f"sql:{DEFAULT_IPSEC_NSS_DIR}",
            "-W",
            "",
        ],
        check=True,
    )
    exec_cmd(
        [
            "certutil",
            "-M",
            "-n",
            "Easy-RSA CA",
            "-t",
            "CT",
            "-d",
            f"sql:{DEFAULT_IPSEC_NSS_DIR}",
        ],
        check=True,
    )


def start_ipsec_srv_container():
    try:
        remove_veth_pair(IpsecTestEnv.CLI_NIC, SRV_NAMESPACE)
    except Exception:
        pass
    create_veth_pair(
        IpsecTestEnv.CLI_NIC,
        IpsecTestEnv.SRV_NIC,
        SRV_NAMESPACE,
    )
    exec_cmd(
        "podman run -d --privileged --replace "
        "--pull=never "
        f"--name {SRV_CONTAINER_NAME} "
        "--hostname ipsec-srv.example.org "
        f"--network ns:/run/netns/{SRV_NAMESPACE} "
        f"{SRV_CONTAINER_IMG}".split(),
        check=True,
    )
    exec_cmd(
        [
            "podman",
            "exec",
            "-i",
            f"{SRV_CONTAINER_NAME}",
            "/bin/bash",
            "-c",
            "systemctl start NetworkManager.service;"
            "for i in {0..30}; do"
            "   if systemctl is-active NetworkManager.service; then exit; fi;"
            "   sleep 1;"
            "done;"
            "exit 1",
        ],
        check=True,
    )
    exec_cmd(
        [
            "podman",
            "exec",
            "-i",
            f"{SRV_CONTAINER_NAME}",
            "/bin/bash",
            "-c",
            "systemctl start nmstate.service; "
            "for i in {0..30}; do"
            "   if systemctl is-active nmstate.service; then exit; fi;"
            "   sleep 1;"
            "done;"
            "exit 1",
        ],
        check=True,
    )

    # Need to wait 2 seconds for IPv6 duplicate address detection
    time.sleep(2)


def _start_ipsec_connection(conf_path):
    exec_cmd(
        f"podman cp {conf_path} "
        f"{SRV_CONTAINER_NAME}:/etc/ipsec.d/srv.conf".split(),
        check=True,
    )
    exec_cmd(
        f"podman exec {SRV_CONTAINER_NAME} systemctl restart ipsec".split(),
        check=True,
    )
    exec_cmd(
        [
            "podman",
            "exec",
            "-i",
            f"{SRV_CONTAINER_NAME}",
            "/bin/bash",
            "-c",
            "systemctl reset-failed ipsec.service;"
            "systemctl restart ipsec.service;"
            "for i in {0..30}; do"
            "   if systemctl is-active ipsec.service; then exit; fi;"
            "   sleep 1;"
            "done;"
            "exit 1",
        ],
        check=True,
    )


def pull_ipsec_srv_container_image():
    i = 0
    while i < 5:
        try:
            exec_cmd(f"podman pull {SRV_CONTAINER_IMG}".split(), check=True)
            break
        except SubprocessError:
            i += 1
            pass


def _restart_ipsec_service():
    exec_cmd("systemctl reset-failed ipsec.service".split(), check=False)
    exec_cmd("systemctl restart ipsec.service".split())
