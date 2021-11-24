use crate::{BaseInterface, EthernetInterface};

pub(crate) fn np_ethernet_to_nmstate(
    _np_iface: &nispor::Iface,
    base_iface: BaseInterface,
) -> EthernetInterface {
    EthernetInterface {
        base: base_iface,
        ..Default::default()
    }
}
