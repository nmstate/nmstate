use crate::{
    EthernetInterface, Interface, InterfaceType, LinuxBridgeInterface,
    OvsBridgeConfig, OvsBridgeInterface, OvsBridgePortConfig, OvsInterface,
    UnknownInterface,
};

pub(crate) fn new_eth_iface(name: &str) -> Interface {
    let mut iface = EthernetInterface::new();
    iface.base.name = name.to_string();
    Interface::Ethernet(iface)
}

pub(crate) fn new_unknown_iface(name: &str) -> Interface {
    let mut iface = UnknownInterface::new();
    iface.base.name = name.to_string();
    Interface::Unknown(iface)
}

pub(crate) fn new_br_iface(name: &str) -> Interface {
    let mut iface = LinuxBridgeInterface::new();
    iface.base.name = name.to_string();
    Interface::LinuxBridge(iface)
}

pub(crate) fn new_ovs_br_iface(name: &str, port_names: &[&str]) -> Interface {
    let mut br0 = OvsBridgeInterface::new();
    br0.base.iface_type = InterfaceType::OvsBridge;
    br0.base.name = name.to_string();
    let mut br_conf = OvsBridgeConfig::new();
    let mut br_port_confs = Vec::new();
    for port_name in port_names {
        let mut br_port_conf = OvsBridgePortConfig::new();
        br_port_conf.name = port_name.to_string();
        br_port_confs.push(br_port_conf);
    }
    br_conf.ports = Some(br_port_confs);
    br0.bridge = Some(br_conf);
    Interface::OvsBridge(br0)
}

pub(crate) fn new_ovs_iface(name: &str, ctrl_name: &str) -> Interface {
    let mut iface = OvsInterface::new();
    iface.base.iface_type = InterfaceType::OvsInterface;
    iface.base.name = name.to_string();
    iface.base.controller = Some(ctrl_name.to_string());
    iface.base.controller_type = Some(InterfaceType::OvsBridge);
    Interface::OvsInterface(iface)
}

pub(crate) fn new_nested_4_ifaces() -> [Interface; 6] {
    let br0 = new_br_iface("br0");
    let mut br1 = new_br_iface("br1");
    let mut br2 = new_br_iface("br2");
    let mut br3 = new_br_iface("br3");
    let mut p1 = new_eth_iface("p1");
    let mut p2 = new_eth_iface("p2");

    br1.base_iface_mut().controller = Some("br0".to_string());
    br1.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    br2.base_iface_mut().controller = Some("br1".to_string());
    br2.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    br3.base_iface_mut().controller = Some("br2".to_string());
    br3.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    p1.base_iface_mut().controller = Some("br3".to_string());
    p1.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);
    p2.base_iface_mut().controller = Some("br3".to_string());
    p2.base_iface_mut().controller_type = Some(InterfaceType::LinuxBridge);

    // Place the ifaces in mixed order to complex the work
    [br0, br1, br2, br3, p1, p2]
}
