function start_machine_services {
    systemctl start openvswitch
    systemctl restart NetworkManager
}
