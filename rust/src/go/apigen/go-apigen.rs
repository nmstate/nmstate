// SPDX-License-Identifier: Apache-2.0
use std::collections::{HashMap, HashSet};
use std::error::Error;
use std::fs::File;
use std::io::Read;
use std::io::Write;
use std::process::Command;

use syn::visit::{self, Visit};
use syn::{ItemEnum, ItemStruct, Variant};

use convert_case::{Case, Casing};

use clap::Parser;

use regex::RegexSet;

const OMITEMPTY: &str = "omitempty";

struct GolangEmitter {
    output: String,
}

struct RustVisitor {
    skip_structs: RegexSet,
    skip_variants: HashMap<&'static str, HashSet<&'static str>>,
    skip_fields: HashMap<&'static str, HashSet<&'static str>>,
    current_struct: Option<StructContext>,
    current_enum: Option<EnumContext>,
    emitter: GolangEmitter,
}

#[derive(Default, Clone)]
struct FieldContext {
    is_optional: bool,
    is_number_or_string: bool,
}

#[derive(Default, Clone)]
struct StructContext {
    name: String,
    serde_rename_all: Option<String>,
}

#[derive(Default, Clone)]
struct EnumContext {
    name: String,
}

#[derive(Parser, Default, Debug)]
#[clap(
    author = "Enrique Llorente <ellorent@redhat.com>",
    about = "Golang api generator for nmstate"
)]
struct Arguments {
    input_dir: String,
    output_file: String,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Arguments::parse();

    let mut visitor = RustVisitor {
        skip_structs: RegexSet::new([
            r"Merged.*",
            "OvsBridgeInterface",
            "LinuxBridgeInterface",
            "InterfaceIpv4",
            "InterfaceIpv6",
            "FeatureVisitor",
            "IntegerOrString",
        ])?,
        skip_fields: HashMap::from([
            ("_other", HashSet::new()),
            ("prop_list", HashSet::new()),
            ("base", HashSet::new()),
            ("slaves", HashSet::new()),
            (
                "name",
                HashSet::from(["LinuxBridgePortConfig", "OvsBridgePortConfig"]),
            ),
            (
                "vlan",
                HashSet::from(["LinuxBridgePortConfig", "OvsBridgePortConfig"]),
            ),
            ("options", HashSet::from(["OvsBridgeConfig"])),
            ("ports", HashSet::from(["OvsBridgeConfig"])),
        ]),
        skip_variants: HashMap::from([
            ("LinuxBridge", HashSet::from(["Interface"])),
            ("OvsBridge", HashSet::from(["Interface"])),
            ("Dummy", HashSet::from(["Interface"])),
            ("Unknown", HashSet::from(["Interface"])),
            ("Loopback", HashSet::from(["Interface"])),
        ]),
        current_struct: None,
        current_enum: None,
        emitter: GolangEmitter {
            output: String::new(),
        },
    };

    visitor.visit_files(
        args.input_dir,
        vec![
            "lldp.rs",
            "ieee8021x.rs",
            "mptcp.rs",
            "ovs.rs",
            "iface.rs",
            "dns.rs",
            "route.rs",
            "route_rule.rs",
            "ip.rs",
            "hostname.rs",
            "ifaces/bond.rs",
            "ifaces/dummy.rs",
            "ifaces/linux_bridge.rs",
            "ifaces/bridge_vlan.rs",
            "ifaces/ovs.rs",
            "ifaces/vlan.rs",
            "ifaces/vxlan.rs",
            "ifaces/mac_vlan.rs",
            "ifaces/mac_vtap.rs",
            "ifaces/vrf.rs",
            "ifaces/infiniband.rs",
            "ifaces/loopback.rs",
            "ifaces/sriov.rs",
            "ifaces/ethtool.rs",
            "ifaces/base.rs",
            "ifaces/ethernet.rs",
            "ifaces/macsec.rs",
            "ifaces/ipsec.rs",
            "net_state.rs",
            "ovn.rs",
            "dispatch.rs",
        ],
    )?;

    let mut output_file = File::create(args.output_file.clone())?;
    write!(output_file, "{}", visitor.emitter.output)?;
    Command::new("go")
        .arg("fmt")
        .arg(args.output_file)
        .output()
        .expect("failed to format generated api");
    Ok(())
}

impl<'ast> Visit<'ast> for RustVisitor {
    fn visit_item_struct(&mut self, node: &'ast ItemStruct) {
        if self.should_skip_struct(node) {
            return;
        }
        let visited_struct = StructContext {
            name: node.ident.to_string(),
            serde_rename_all: self.parse_serde_rename_all(node.attrs.clone()),
        };

        self.emitter.emit_struct_begin(visited_struct.clone().name);
        self.current_struct = Some(visited_struct.clone());

        visit::visit_item_struct(self, node);

        self.emitter.emit_struct_end();
        self.current_struct = None;
    }

    fn visit_item_enum(&mut self, node: &'ast ItemEnum) {
        let enum_name: String = node.ident.to_string();
        self.current_enum = Some(EnumContext {
            name: enum_name.clone(),
        });
        if enum_name == "Interface" {
            // To make CRD happy we have to trick Linux/Ovs bridge into one
            // struct with some field shared
            self.emitter.output.push_str(
                r#"
// +k8s:deepcopy-gen=true
type OvsBridgeStpOptions struct {
	Enabled       *bool `json:"enabled,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortConfigMetaData struct {
	Name string                `json:"name"`
	Vlan *BridgePortVlanConfig `json:"vlan,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgePortConfig struct {
	BridgePortConfigMetaData `json:""`
	*OvsBridgePortConfig     `json:",omitempty"`
	*LinuxBridgePortConfig   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeOptions struct {
	*LinuxBridgeOptions `json:",omitempty"`
	*OvsBridgeOptions   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeConfig struct {
	*OvsBridgeConfig `json:",omitempty"`
	Options          *BridgeOptions      `json:"options,omitempty"`
	Ports            *[]BridgePortConfig `json:"port,omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeInterface struct {
	*BridgeConfig `json:"bridge,omitempty"`
}

// +k8s:deepcopy-gen=true
type Interface struct {
	BaseInterface        `json:",omitempty"`
	*BridgeInterface     `json:",omitempty"`
"#,
            );
            visit::visit_item_enum(self, node);
            self.emitter.emit_struct_end();
        } else if enum_name == "BridgePortTrunkTag" {
            self.emitter.emit_struct_begin(enum_name);
            visit::visit_item_enum(self, node);
            self.emitter.emit_struct_end();
        } else {
            self.emitter.emit_string_enum_begin(enum_name.clone());
            visit::visit_item_enum(self, node);
            self.emitter.emit_string_enum_end(enum_name);
        }
        self.current_enum = None;
    }

    fn visit_variant(&mut self, node: &'ast Variant) {
        if self.should_skip_variant(node) {
            return;
        }
        if let Some(current_enum) = self.current_enum.clone() {
            match current_enum.name.as_str() {
                "Interface" => self.emit_variant_as_field(String::new(), node),
                "BridgePortTrunkTag" => self.emit_variant_as_field(
                    to_kebab_case(&node.ident.to_string()),
                    node,
                ),
                _ => {
                    self.emitter.emit_string_enum_variant(
                        current_enum.name,
                        node.ident.to_string(),
                    );
                }
            }
        }
    }

    fn visit_field(&mut self, node: &'ast syn::Field) {
        if self.should_skip_field(node) {
            return;
        }

        if let Some(current_struct) = self.current_struct.clone() {
            if let Some(field_ident) = node.clone().ident {
                let mut field_name = field_ident.to_string();

                // Rename "IfaceType" to "Type" since the context
                // is already the interface
                if field_name == "iface_type"
                    && current_struct.name == "BaseInterface"
                {
                    field_name = "type".to_string()
                }
                self.emitter.emit_field_begin(field_name.clone());

                let mut field_context = FieldContext {
                    is_number_or_string: self
                        .has_serde_deserialize_with_number_or_string(
                            node.attrs.clone(),
                        ),
                    // Force optional if serde skip_serializating annotation
                    // is found, so fields are not passed to nmstate if not
                    // set
                    is_optional: self
                        .has_serde_skip_serialization(node.attrs.clone()),
                };
                self.parse_field_type(node.clone().ty, &mut field_context);

                if let Some(renamed_field_name) =
                    self.parse_serde_rename(node.attrs.clone())
                {
                    field_name = renamed_field_name;
                } else if let Some(renamed_field_name) =
                    to_custom_name(&field_name)
                {
                    field_name = renamed_field_name;
                } else if let Some(struct_serde_rename_all) =
                    current_struct.serde_rename_all
                {
                    if struct_serde_rename_all == "kebab-case" {
                        field_name = to_kebab_case(&field_name)
                    }
                }
                let mut json_tag = vec![field_name.clone()];
                if self
                    .parse_serde_skip_serialization_if(node.attrs.clone())
                    .is_some()
                    || field_context.is_optional
                    || field_name == "dns-resolver"
                    || field_name == "route-rules"
                    || field_name == "routes"
                    || field_name == "interfaces"
                    || field_name == "ovs-db"
                    || field_name == "ovn"
                    || field_name == "type"
                    || field_name == "state"
                    || field_name == "other"
                    || field_name == "allow-extra-address"
                    || field_name == "allow-extra-patch-ports"
                {
                    json_tag.push(String::from(OMITEMPTY));
                }
                self.emitter.emit_json_tag(json_tag);

                self.emitter.emit_field_end();
            }
        }
    }
}

impl<'ast> RustVisitor {
    fn visit_files(
        &mut self,
        input_dir: String,
        files_to_visit: Vec<&'static str>,
    ) -> Result<(), Box<dyn Error>> {
        self.emitter.emit_package_name(String::from("v2"));

        self.emitter.output.push_str(
            r#"    
import (
    "k8s.io/apimachinery/pkg/util/intstr"
)
"#,
        );

        for file_to_visit in files_to_visit {
            let mut file =
                File::open(format!("{}/{}", input_dir, file_to_visit))?;
            let mut content = String::new();
            file.read_to_string(&mut content)?;
            let ast = syn::parse_file(&content)?;
            self.visit_file(&ast);
        }
        Ok(())
    }

    fn should_skip_struct(&self, node: &'ast ItemStruct) -> bool {
        self.skip_structs.is_match(&node.ident.to_string())
    }

    fn should_skip_variant(&self, node: &'ast Variant) -> bool {
        if let Some(current_enum) = self.current_enum.clone() {
            if let Some(skip_variant_enums) =
                self.skip_variants.get(node.ident.to_string().as_str())
            {
                skip_variant_enums.is_empty()
                    || skip_variant_enums.contains(current_enum.name.as_str())
            } else {
                false
            }
        } else {
            true
        }
    }

    fn should_skip_field(&mut self, node: &'ast syn::Field) -> bool {
        if self
            .parse_serde_attribute(node.attrs.clone(), "skip")
            .is_some()
        {
            return true;
        }
        if let Some(current_struct) = self.current_struct.clone() {
            if let Some(node_ident) = node.ident.clone() {
                if let Some(skip_field_structs) =
                    self.skip_fields.get(node_ident.to_string().as_str())
                {
                    return skip_field_structs.is_empty()
                        || skip_field_structs
                            .contains(current_struct.name.as_str());
                } else {
                    return false;
                }
            }
        }
        true
    }

    fn emit_variant_as_field(
        &mut self,
        json_name: String,
        node: &'ast Variant,
    ) {
        if !json_name.is_empty() {
            self.emitter.emit_field_begin(node.ident.to_string());
        }
        if let syn::Fields::Unnamed(unamed_fields) = node.fields.clone() {
            if let Some(field) = unamed_fields.unnamed.first() {
                self.emitter.emit_optional();
                self.parse_field_type(
                    field.ty.clone(),
                    &mut FieldContext::default(),
                );
            }
        }
        self.emitter
            .emit_json_tag(vec![json_name, String::from(OMITEMPTY)]);
        self.emitter.emit_field_end();
    }

    fn parse_field_type(&mut self, t: syn::Type, field_ctx: &mut FieldContext) {
        match t {
            syn::Type::Path(t) => self.parse_field_path_type(t, field_ctx),
            _ => {
                self.emitter.emit_type_name(
                    String::from("todo"),
                    &mut FieldContext::default(),
                );
            }
        }
    }

    fn parse_field_path_type(
        &mut self,
        t: syn::TypePath,
        field_context: &mut FieldContext,
    ) {
        if let Some(last_segment) = t.path.segments.last() {
            let last_segment_name = last_segment.ident.to_string();
            if last_segment_name == "Option" || last_segment_name == "Vec" {
                self.emitter
                    .emit_type_name(last_segment_name, field_context);
                if let syn::PathArguments::AngleBracketed(ab) =
                    last_segment.arguments.clone()
                {
                    if let Some(syn::GenericArgument::Type(gt)) =
                        ab.args.first()
                    {
                        self.parse_field_type(gt.clone(), field_context);
                    }
                }
            } else if last_segment_name == "HashMap" {
                if let syn::PathArguments::AngleBracketed(ab) =
                    last_segment.arguments.clone()
                {
                    if field_context.is_optional {
                        self.emitter.emit_optional();
                        field_context.is_optional = false;
                    }
                    self.emitter.emit_map_begin();
                    if let Some(syn::GenericArgument::Type(key)) =
                        ab.args.first()
                    {
                        self.parse_field_type(
                            key.clone(),
                            &mut FieldContext::default(),
                        );
                    }
                    self.emitter.emit_map_end();
                    if let Some(syn::GenericArgument::Type(value)) =
                        ab.args.last()
                    {
                        self.parse_field_type(
                            value.clone(),
                            &mut FieldContext::default(),
                        );
                    }
                }
            } else {
                self.emitter
                    .emit_type_name(last_segment_name, field_context);
            }
        }
    }

    fn parse_serde_rename(
        &mut self,
        attributes: Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "rename")
    }

    fn parse_serde_skip_serialization_if(
        &mut self,
        attributes: Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "skip_serializing_if")
    }

    fn has_serde_skip_serialization(
        &mut self,
        attributes: Vec<syn::Attribute>,
    ) -> bool {
        self.parse_serde_attribute(attributes, "skip_serializing")
            .is_some()
    }

    fn parse_serde_rename_all(
        &mut self,
        attributes: Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "rename_all")
    }

    fn parse_serde_deserialize_with(
        &mut self,
        attributes: Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "deserialize_with")
    }

    fn has_serde_deserialize_with_number_or_string(
        &mut self,
        attributes: Vec<syn::Attribute>,
    ) -> bool {
        match self.parse_serde_deserialize_with(attributes) {
            Some(deserializer) => matches!(
                deserializer.as_str(),
                "crate::deserializer::option_u8_or_string"
                    | "crate::deserializer::option_u16_or_string"
                    | "crate::deserializer::option_u32_or_string"
                    | "crate::deserializer::option_u64_or_string"
                    | "crate::deserializer::option_i8_or_string"
                    | "crate::deserializer::option_i16_or_string"
                    | "crate::deserializer::option_i32_or_string"
                    | "crate::deserializer::option_i64_or_string"
            ),
            _ => false,
        }
    }

    fn parse_serde_attribute(
        &mut self,
        attributes: Vec<syn::Attribute>,
        attribute_name: &str,
    ) -> Option<String> {
        for attr in attributes {
            if let syn::Meta::List(list) = attr.clone().meta {
                if let Some(first_segment) = list.path.segments.first() {
                    if first_segment.ident == "serde" {
                        let mut tokens_iter = list.tokens.into_iter();
                        while let Some(token) = tokens_iter.next() {
                            if let proc_macro2::TokenTree::Ident(iden_token) =
                                token
                            {
                                if iden_token == attribute_name {
                                    tokens_iter.next(); // =
                                    if let Some(rename_value) =
                                        tokens_iter.next()
                                    {
                                        return Some(
                                            rename_value
                                                .to_string()
                                                .replace('"', ""),
                                        );
                                    }
                                    return Some(String::new());
                                }
                            }
                        }
                    }
                }
            }
        }
        None
    }
}

impl GolangEmitter {
    fn emit_string_enum_begin(&mut self, name: String) -> &mut GolangEmitter {
        self.output.push_str("type ");
        self.output.push_str(&name);
        self.output.push_str(" string\n");
        self
    }
    fn emit_string_enum_variant(
        &mut self,
        enum_name: String,
        variant: String,
    ) -> &mut GolangEmitter {
        self.output.push_str("const ");
        self.output.push_str(&enum_name);
        self.output.push_str(&variant);
        self.output.push_str(" = ");
        self.output.push_str(&enum_name);
        self.output.push_str("(\"");
        if let Some(custom_value) = to_custom_name(&variant) {
            self.output.push_str(&custom_value);
        } else {
            self.output.push_str(&to_kebab_case(&variant));
        }
        self.output.push_str("\")\n");
        self
    }

    fn emit_string_enum_end(&mut self, name: String) -> &mut GolangEmitter {
        self.output.push_str("// enum ");
        self.output.push_str(&name);
        self.output.push_str("\n\n");
        self
    }

    fn emit_package_name(&mut self, name: String) -> &mut GolangEmitter {
        self.output.push_str("package ");
        self.output.push_str(&name);
        self.output.push_str("\n\n");
        self
    }

    fn emit_struct_begin(&mut self, name: String) -> &mut GolangEmitter {
        self.output.push_str("// +k8s:deepcopy-gen=true\n");
        self.output.push_str("type ");
        self.output.push_str(&name);
        self.output.push_str(" struct {\n");
        self
    }

    fn emit_struct_end(&mut self) -> &mut GolangEmitter {
        self.output.push_str("}\n\n");
        self
    }

    fn emit_field_begin(&mut self, field_name: String) -> &mut GolangEmitter {
        self.output.push_str("  ");
        self.output.push_str(&rust_name_to_golang_name(&field_name));
        self.output.push(' ');
        self
    }

    fn emit_field_end(&mut self) -> &mut GolangEmitter {
        self.output.push('\n');
        self
    }

    fn emit_type_name(
        &mut self,
        type_name: String,
        field_ctx: &mut FieldContext,
    ) -> &mut GolangEmitter {
        if type_name == "String"
            || type_name == "IpAddr"
            || type_name == "Value"
        {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("string");
        } else if field_ctx.is_number_or_string && type_name != "Option" {
            self.output.push_str("*intstr.IntOrString")
        } else if type_name == "u8" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("uint8");
        } else if type_name == "u16" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("uint16");
        } else if type_name == "i16" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("int16");
        } else if type_name == "u32" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("uint32");
        } else if type_name == "i32" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("int32");
        } else if type_name == "i64" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("int64");
        } else if type_name == "u64" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("uint64");
        } else if type_name == "Vec" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("[]");
            field_ctx.is_optional = false
        } else if type_name == "Option" {
            field_ctx.is_optional = true;
        } else if type_name == "DnsState" {
            self.output.push_str("*DnsState");
        } else if type_name == "EthtoolFeatureConfig" {
            self.output.push_str("map[string]bool");
        } else if type_name == "Interfaces" {
            self.output.push_str("[]Interface");
        } else if type_name == "RouteRules"
            || type_name == "Routes"
            || type_name == "OvsDbGlobalConfig"
            || type_name == "OvnConfiguration"
        {
            self.emit_optional();
            self.output.push_str(&type_name);
        } else if type_name == "InterfaceIpv4" || type_name == "InterfaceIpv6" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("InterfaceIp");
        } else {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str(&type_name);
        }
        self
    }

    fn emit_map_begin(&mut self) -> &mut GolangEmitter {
        self.output.push_str("map[");
        self
    }
    fn emit_map_end(&mut self) -> &mut GolangEmitter {
        self.output.push(']');
        self
    }
    fn emit_optional(&mut self) -> &mut GolangEmitter {
        self.output.push('*');
        self
    }
    fn emit_json_tag(&mut self, args: Vec<String>) -> &mut GolangEmitter {
        self.output
            .push_str(&format!(" `json:\"{}\"`", args.join(",")));
        self
    }
}

pub fn to_golang_name(s: &str, sep: char) -> String {
    let mut converted = String::new();
    let parts = s.split(sep);
    for part in parts {
        converted += &capitalize(part)
    }
    converted
}

pub fn to_kebab_case(s: &str) -> String {
    s.to_case(Case::Kebab)
}

pub fn to_custom_name(s: &str) -> Option<String> {
    if s == "Ipv4" || s == "IPv4" || s == "ipv4" {
        return Some(String::from("ipv4"));
    } else if s == "Ipv6" || s == "IPv6" || s == "ipv6" {
        return Some(String::from("ipv6"));
    } else if s == "base" {
        return Some(String::new());
    } else if s == "InfiniBand" {
        return Some(String::from("infiniband"));
    }
    None
}

pub fn rust_name_to_golang_name(s: &str) -> String {
    s.to_case(Case::Pascal)
}

pub fn capitalize(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
    }
}
