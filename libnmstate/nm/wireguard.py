#
# Copyright (c) 2021 Red Hat, Inc.
#
# This file is part of nmstate
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

from libnmstate.schema import Wireguard

from .common import NM
from .secrets import get_secrets


def create_wireguard_setting(wireguard_iface, base_con_profile):
    wireguard_setting = None
    if base_con_profile:
        wireguard_setting = base_con_profile.get_setting_by_name(
            NM.SETTING_WIREGUARD_SETTING_NAME
        )
        if wireguard_setting:
            wireguard_setting = wireguard_setting.duplicate()

    if not wireguard_setting:
        wireguard_setting = NM.SettingWireGuard.new()
    if wireguard_iface.fwmark:
        wireguard_setting.props.fwmark = wireguard_iface.fwmark
    if wireguard_iface.listen_port:
        wireguard_setting.props.listen_port = wireguard_iface.listen_port
    if wireguard_iface.private_key:
        wireguard_setting.props.private_key = wireguard_iface.private_key

    _set_wireguard_peers(wireguard_setting, wireguard_iface.peers)

    return wireguard_setting


def _set_wireguard_peers(wireguard_setting, peers_config):
    wireguard_setting.clear_peers()
    for peer in peers_config:
        wireguard_peer = NM.WireGuardPeer.new()
        wireguard_peer.set_endpoint(peer.get(Wireguard.Peer.ENDPOINT), True)
        if peer.get(Wireguard.Peer.PERSISTENT_KEEPALIVE):
            wireguard_peer.set_persistent_keepalive(
                peer[Wireguard.Peer.PERSISTENT_KEEPALIVE]
            )

        if peer.get(Wireguard.Peer.PRESHARED_KEY):
            wireguard_peer.set_preshared_key_flags(0)
            wireguard_peer.set_preshared_key(
                peer.get(Wireguard.Peer.PRESHARED_KEY), True
            )
        if peer.get(Wireguard.Peer.PUBLIC_KEY):
            wireguard_peer.set_public_key(
                peer.get(Wireguard.Peer.PUBLIC_KEY), True
            )

        for allowed_ip in peer.get(Wireguard.Peer.ALLOWED_IPS, []):
            wireguard_peer.append_allowed_ip(allowed_ip, True)

        wireguard_setting.append_peer(wireguard_peer)


def get_info(context, nm_ac):
    if not nm_ac:
        return {}
    nm_profile = nm_ac.get_connection()
    if not nm_profile:
        return {}

    wireguard_setting = nm_profile.get_setting_by_name(
        NM.SETTING_WIREGUARD_SETTING_NAME
    )
    if not wireguard_setting:
        return {}

    secrets = get_secrets(
        context,
        nm_profile,
        f"Retrieve WireGuard secrets of profile {nm_profile.get_uuid()}",
        NM.SETTING_WIREGUARD_SETTING_NAME,
    )
    peer_secrets = secrets.get(Wireguard.Peer.CONFIG_SUBTREE, [])
    info = {
        Wireguard.FWMARK: wireguard_setting.props.fwmark,
        Wireguard.LISTEN_PORT: wireguard_setting.props.listen_port,
        Wireguard.Peer.CONFIG_SUBTREE: _get_wireguard_peers(
            wireguard_setting, peer_secrets
        ),
    }
    if secrets.get(NM.SETTING_WIREGUARD_PRIVATE_KEY):
        info[Wireguard.PRIVATE_KEY] = secrets[NM.SETTING_WIREGUARD_PRIVATE_KEY]

    return {Wireguard.CONFIG_SUBTREE: info}


def _get_wireguard_peers(wireguard_setting, peer_secrets):
    peers = []
    peers_len = wireguard_setting.get_peers_len()
    if peers_len:
        for peer_id in range(peers_len):
            peer_setting = wireguard_setting.get_peer(peer_id)
            peer_info = {
                Wireguard.Peer.ALLOWED_IPS: _get_peer_allowed_ips(
                    peer_setting
                ),
                Wireguard.Peer.PERSISTENT_KEEPALIVE: (
                    peer_setting.get_persistent_keepalive()
                ),
            }
            if peer_setting.get_endpoint():
                peer_info[
                    Wireguard.Peer.ENDPOINT
                ] = peer_setting.get_endpoint()
            if peer_secrets[peer_id].get(Wireguard.Peer.PRESHARED_KEY):
                peer_info[Wireguard.Peer.PRESHARED_KEY] = peer_secrets[
                    peer_id
                ][Wireguard.Peer.PRESHARED_KEY]
            if peer_setting.get_public_key():
                peer_info[
                    Wireguard.Peer.PUBLIC_KEY
                ] = peer_setting.get_public_key()
            peers.append(peer_info)

    return peers


def _get_peer_allowed_ips(peer_setting):
    allowed_ips = []
    allowed_ips_len = peer_setting.get_allowed_ips_len()
    if allowed_ips_len:
        for allowed_ip_id in range(allowed_ips_len):
            allowed_ips.append(
                peer_setting.get_allowed_ip(allowed_ip_id, None)
            )

    return allowed_ips
