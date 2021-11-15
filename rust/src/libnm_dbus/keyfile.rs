use std::collections::HashMap;
use std::convert::TryFrom;

use log::error;

use crate::{ErrorKind, NmError};

pub(crate) fn zvariant_value_to_keyfile(
    value: &zvariant::Value,
    section_name: &str,
) -> Result<String, NmError> {
    match value {
        zvariant::Value::Bool(b) => Ok(if *b {
            "true".to_string()
        } else {
            "false".to_string()
        }),
        zvariant::Value::I32(d) => Ok(format!("{}", d)),
        zvariant::Value::U32(d) => Ok(format!("{}", d)),
        zvariant::Value::U8(d) => Ok(format!("{}", d)),
        zvariant::Value::U16(d) => Ok(format!("{}", d)),
        zvariant::Value::I16(d) => Ok(format!("{}", d)),
        zvariant::Value::U64(d) => Ok(format!("{}", d)),
        zvariant::Value::I64(d) => Ok(format!("{}", d)),
        zvariant::Value::Dict(d) => {
            let data: HashMap<String, zvariant::Value> =
                HashMap::try_from(d.clone())?;
            if data.is_empty() {
                return Ok("".to_string());
            }
            let mut ret = String::new();

            let mut names: Vec<String> = data.keys().cloned().collect();
            if section_name.is_empty() {
                // Only sort the top level sections
                names.sort_unstable();
            } else {
                // place the sub-section at the end of section_names.
                names.sort_unstable_by(|a, b| {
                    let a_is_subsection =
                        matches!(data.get(a), Some(zvariant::Value::Dict(_)));
                    let b_is_subsection =
                        matches!(data.get(b), Some(zvariant::Value::Dict(_)));
                    a_is_subsection.cmp(&b_is_subsection)
                });
            }

            for key in &names {
                let key = if section_name == "ipv4" || section_name == "ipv6" {
                    if key == "addresses" || key == "routes" {
                        // Ignore deprecated 'addresses' in favor of
                        // 'address-data'.
                        // Ignore deprecated 'routes' in favor of 'route-data'
                        continue;
                    } else if key == "dhcp-client-id" {
                        "dhcp-iaid".to_string()
                    } else {
                        key.to_string()
                    }
                } else {
                    key.to_string()
                };

                if let Some(section_value) = data.get(&key) {
                    if key == "mac-address" {
                        ret += &format!(
                            "mac-address={}\n",
                            mac_address_value_to_string(section_value)
                        );
                    } else if key == "type" && section_name == "connection" {
                        let iface_type = zvariant_value_to_keyfile(
                            section_value,
                            section_name,
                        )?;
                        ret += &format!(
                            "type={}\n",
                            if iface_type == "802-3-ethernet" {
                                "ethernet".to_string()
                            } else {
                                iface_type
                            }
                        );
                    } else if key == "address-data" {
                        ret += &ip_address_value_to_string(section_value);
                    } else if let zvariant::Value::Dict(_) = section_value {
                        let sub_section: HashMap<String, zvariant::Value> =
                            HashMap::try_from(section_value.clone())?;
                        if sub_section.is_empty() {
                            continue;
                        }

                        let sub_section_name = if section_name.is_empty() {
                            key.to_string()
                        } else {
                            format!("{}-{}", section_name, key)
                        };
                        ret += &format!("\n[{}]\n", sub_section_name);
                        ret += &zvariant_value_to_keyfile(
                            section_value,
                            &sub_section_name,
                        )?;
                    } else {
                        ret += &format!(
                            "{}={}\n",
                            key,
                            zvariant_value_to_keyfile(
                                section_value,
                                section_name
                            )?
                        );
                    }
                }
            }
            Ok(ret)
        }
        zvariant::Value::Array(a) => {
            let mut ret = String::new();
            for item in a.get() {
                ret += &zvariant_value_to_keyfile(item, section_name)?;
                ret += ";";
            }
            ret.pop();
            Ok(ret)
        }
        zvariant::Value::Str(s) => Ok(s.as_str().to_string()),
        _ => {
            let e = NmError::new(
                ErrorKind::Bug,
                format!(
                    "BUG: Unknown value type in section {}: {:?}",
                    section_name, value
                ),
            );
            error!("{}", e);
            Err(e)
        }
    }
}

fn mac_address_value_to_string(value: &zvariant::Value) -> String {
    let mut ret = String::new();
    if let zvariant::Value::Array(a) = value {
        for item in a.get() {
            if let Ok(s) = zvariant_value_to_keyfile(item, "") {
                ret += &s;
                ret += ":";
            }
        }
        ret.pop();
    }
    ret
}

fn ip_address_value_to_string(value: &zvariant::Value) -> String {
    let mut ret = String::new();
    let mut index = 0u32;
    if let zvariant::Value::Array(ip_addrs) = value {
        for ip_addr_value in ip_addrs.get() {
            let ip_addr_value = if let zvariant::Value::Dict(i) = ip_addr_value
            {
                i
            } else {
                continue;
            };
            let address = if let Ok(Some(s)) = ip_addr_value.get("address") {
                zvariant_value_to_keyfile(s, "")
            } else {
                continue;
            };
            let prefix = if let Ok(Some(p)) = ip_addr_value.get("prefix") {
                zvariant_value_to_keyfile(p, "")
            } else {
                continue;
            };
            if let Ok(address) = address {
                if let Ok(prefix) = prefix {
                    ret +=
                        &format!("address{}={}/{}\n", index, address, prefix);
                    index += 1;
                }
            }
        }
    }
    ret
}
