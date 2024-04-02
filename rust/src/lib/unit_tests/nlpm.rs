use crate::nlpm;

#[test]
fn test_nlpm() {
    nlpm::nlpm(r"Please create a linux bridge br0 using eth1 and eth2".to_string());
}