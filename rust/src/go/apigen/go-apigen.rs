// SPDX-License-Identifier: Apache-2.0
use std::collections::{HashMap, HashSet};
use std::error::Error;
use std::fs::File;
use std::io::Read;
use std::io::Write;
use std::process::Command;

use syn::visit::{self, Visit};
use syn::{Expr, ItemEnum, ItemStruct, Lit, Meta, Variant};

use convert_case::{Boundary, Case, Casing, Converter};

use clap::Parser;

use regex::RegexSet;

const OMITEMPTY: &str = "omitempty";

struct GolangEmitter {
    header: String,
    output: String,
}

struct RustVisitor {
    skip_structs: RegexSet,
    skip_variants: HashMap<&'static str, HashSet<&'static str>>,
    skip_fields: HashMap<&'static str, HashSet<&'static str>>,
    current_struct: Option<StructContext>,
    current_enum: Option<EnumContext>,
    ovs_bridge_interface: Option<StructContext>,
    linux_bridge_interface: Option<StructContext>,
    emitter: GolangEmitter,
}

#[derive(Default, Clone)]
struct FieldContext {
    name: String,
    is_optional: bool,
    is_number_or_string: bool,
    docs: String,
}

#[derive(Default, Clone)]
struct StructContext {
    name: String,
    serde_rename_all: Option<String>,
    docs: String,
}

#[derive(Default, Clone)]
struct EnumContext {
    name: String,
    serde_rename_all: Option<String>,
    repr: Option<String>,
    docs: String,
    variants: Vec<VariantContext>,
    is_number_or_string: bool,
    has_other_variant: bool,
}

#[derive(Default, Clone)]
struct VariantContext {
    enum_name: String,
    enum_serde_rename_all: Option<String>,
    enum_is_number_or_string: bool,
    name: String,
    serde_rename: Option<String>,
    serde_alias: Option<String>,
    docs: String,
    u8_discriminant: Option<u8>,
}

#[derive(Parser, Default, Debug)]
#[clap(
    author = "Enrique Llorente <ellorent@redhat.com>",
    about = "Golang api generator for nmstate"
)]
struct Arguments {
    input_dir: String,
    output_file: String,
    #[clap(long)]
    header_file: String,
}

fn main() -> Result<(), Box<dyn Error>> {
    let args = Arguments::parse();

    let mut visitor = RustVisitor {
        skip_structs: RegexSet::new([
            r"Merged.*",
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
                HashSet::from(["LinuxBridgePortConfig", "OVSBridgePortConfig"]),
            ),
            (
                "vlan",
                HashSet::from(["LinuxBridgePortConfig", "OVSBridgePortConfig"]),
            ),
            ("options", HashSet::from(["OVSBridgeConfig"])),
            ("ports", HashSet::from(["OVSBridgeConfig"])),
        ]),
        skip_variants: HashMap::from([
            ("LinuxBridge", HashSet::from(["Interface"])),
            ("OvsBridge", HashSet::from(["Interface"])),
            ("Dummy", HashSet::from(["Interface"])),
            ("Unknown", HashSet::from(["Interface"])),
            ("Loopback", HashSet::from(["Interface"])),
            ("Xfrm", HashSet::from(["Interface"])),
        ]),
        current_struct: None,
        current_enum: None,
        linux_bridge_interface: None,
        ovs_bridge_interface: None,
        emitter: GolangEmitter {
            header: std::fs::read_to_string(args.header_file)?,
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
            "ifaces/hsr.rs",
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
            name: rust_name_to_golang_name(node.ident.to_string().as_str()),
            serde_rename_all: self.parse_serde_rename_all(&node.attrs),
            docs: self.parse_docs(&node.attrs),
        };
        match visited_struct.name.as_str() {
            "LinuxBridgeInterface" => {
                self.linux_bridge_interface = Some(visited_struct.clone());
            }
            "OVSBridgeInterface" => {
                self.ovs_bridge_interface = Some(visited_struct.clone());
            }
            _ => {
                self.emitter.emit_struct_begin(&visited_struct);
                self.current_struct = Some(visited_struct.clone());

                visit::visit_item_struct(self, node);

                self.emitter.emit_struct_end();
                self.current_struct = None;
            }
        }
    }

    fn visit_item_enum(&mut self, node: &'ast ItemEnum) {
        let mut current_enum = EnumContext {
            name: rust_name_to_golang_name(&node.ident.to_string()),
            serde_rename_all: self.parse_serde_rename_all(&node.attrs),
            repr: self.parse_repr_attribute(&node.attrs),
            docs: self.parse_docs(&node.attrs),
            variants: Vec::<VariantContext>::new(),
            has_other_variant: false,
            is_number_or_string: node.ident.to_string().as_str()
                == "LinuxBridgeMulticastRouterType",
        };
        self.current_enum = Some(current_enum.clone());
        match current_enum.name.as_str() {
            "Interface" => {
                self.emitter.emit_struct_begin(&StructContext {
                    name: current_enum.name,
                    docs: current_enum.docs,
                    serde_rename_all: None,
                });

                self.emitter.output.push_str(
                    r#"
	BaseInterface        `json:",omitempty"`
	*BridgeInterface     `json:",omitempty"`
"#,
                );
                visit::visit_item_enum(self, node);
                self.emitter.emit_struct_end();
            }
            "BridgePortTrunkTag" | "LldpNeighborTlv" => {
                self.emitter.emit_struct_begin(&StructContext {
                    name: current_enum.name,
                    docs: current_enum.docs,
                    serde_rename_all: None,
                });
                visit::visit_item_enum(self, node);
                self.emitter.emit_struct_end();
            }
            _ => {
                // It needs to visit the enum variants first to recollect them
                // at current_enum.variants and compose the kubebuilder
                // enum validation annotation
                visit::visit_item_enum(self, node);
                // Update current_enum with latest changes, maybe this should
                // be handled by a reference or a Box or the like so we don't
                // have to copy it again.
                current_enum = self.current_enum.clone().unwrap();
                self.emitter.emit_enum_begin(&current_enum);
                if let Some(current_enum) = self.current_enum.clone() {
                    for variant in current_enum.variants {
                        self.emitter.emit_enum_variant(&variant);
                    }
                }
                self.emitter.emit_enum_end(current_enum.name);
            }
        }
        self.current_enum = None;
    }

    fn visit_variant(&mut self, node: &'ast Variant) {
        if self.should_skip_variant(node) {
            return;
        }
        if let Some(current_enum) = self.current_enum.clone() {
            let variant_ctx = &mut VariantContext {
                enum_name: current_enum.name.clone(),
                enum_serde_rename_all: current_enum.serde_rename_all.clone(),
                enum_is_number_or_string: current_enum.is_number_or_string,
                name: rust_name_to_golang_name(&node.ident.to_string()),
                serde_rename: self.parse_serde_rename(&node.attrs),
                serde_alias: self.parse_serde_alias(&node.attrs),
                docs: self.parse_docs(&node.attrs),
                u8_discriminant: None,
            };
            match current_enum.name.as_str() {
                "Interface" | "LldpNeighborTlv" => {
                    let json_name = "".to_string();
                    self.emit_variant_as_field(json_name, variant_ctx, node);
                }
                "BridgePortTrunkTag" => {
                    let json_name = to_kebab_case(&node.ident.to_string());
                    self.emit_variant_as_field(json_name, variant_ctx, node);
                }

                _ => {
                    if let Some(discriminant) = node.discriminant.clone() {
                        let (_, expr) = discriminant;
                        if let Expr::Lit(literal_discriminant) = expr {
                            if let Lit::Int(int_discriminant) =
                                literal_discriminant.lit
                            {
                                if let Ok(u8_discriminant) =
                                    int_discriminant.base10_parse::<u8>()
                                {
                                    variant_ctx.u8_discriminant =
                                        Some(u8_discriminant);
                                }
                            }
                        }
                    }
                    if let Some(enum_ctx) = &mut self.current_enum {
                        if variant_ctx.name == "Other" {
                            enum_ctx.has_other_variant = true
                        } else {
                            enum_ctx.variants.push(variant_ctx.clone());
                        }
                    }
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
                let mut field_context = FieldContext {
                    // Rename "IfaceType" to "Type" since the context
                    // is already the interface
                    name: if field_ident == "iface_type"
                        && current_struct.name == "BaseInterface"
                    {
                        "type".to_string()
                    } else {
                        field_ident.to_string()
                    },
                    is_number_or_string: self
                        .has_serde_deserialize_with_number_or_string(
                            &node.attrs,
                        ),
                    // Force optional if serde skip_serializating annotation
                    // is found, so fields are not passed to nmstate if not
                    // set
                    is_optional: self.has_serde_skip_serialization(&node.attrs)
                        || (current_struct.name != "LldpConfig"
                            && current_struct.name.starts_with("Lldp")),
                    docs: self.parse_docs(&node.attrs),
                };

                self.emitter.emit_field_begin(&field_context);
                self.parse_field_type(node.clone().ty, &mut field_context);

                if let Some(renamed_field_name) =
                    self.parse_serde_rename(&node.attrs)
                {
                    field_context.name = renamed_field_name;
                } else if let Some(struct_serde_rename_all) =
                    current_struct.serde_rename_all
                {
                    if struct_serde_rename_all == "kebab-case" {
                        field_context.name = to_kebab_case(&field_context.name);
                    } else if struct_serde_rename_all == "snake_case" {
                        field_context.name = to_snake_case(&field_context.name);
                    } else if struct_serde_rename_all == "lowercase" {
                        field_context.name = field_context.name.to_lowercase();
                    }
                }
                let mut json_tag = vec![field_context.name.clone()];
                if self
                    .parse_serde_skip_serialization_if(&node.attrs)
                    .is_some()
                    || field_context.is_optional
                    || field_context.name == "dns-resolver"
                    || field_context.name == "route-rules"
                    || field_context.name == "routes"
                    || field_context.name == "interfaces"
                    || field_context.name == "ovs-db"
                    || field_context.name == "ovn"
                    || field_context.name == "type"
                    || field_context.name == "state"
                    || field_context.name == "other"
                    || field_context.name == "allow-extra-address"
                    || field_context.name == "allow-extra-patch-ports"
                    || field_context.name == "route-table-id"
                    || field_context.name == "peer"
                    || (current_struct.name != "LldpConfig"
                        && current_struct.name.starts_with("Lldp"))
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
        self.emitter.emit_header();
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
        if let (Some(linux_bridge_interface), Some(ovs_bridge_interface)) = (
            self.linux_bridge_interface.clone(),
            self.ovs_bridge_interface.clone(),
        ) {
            // We have to conglomerate ovs and linux bridge into the same
            // structure to make k8s crd generator happy
            self.emitter.emit_bridge_interface(
                &linux_bridge_interface,
                &ovs_bridge_interface,
            );
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
        if self.parse_serde_attribute(&node.attrs, "skip").is_some() {
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
        variant_ctx: &VariantContext,
        node: &'ast Variant,
    ) {
        if !json_name.is_empty() {
            self.emitter.emit_field_begin(&FieldContext {
                name: variant_ctx.name.clone(),
                docs: variant_ctx.docs.clone(),
                is_number_or_string: false,
                is_optional: false,
            });
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
                        // The value of other_config and external_ids
                        // can be int or string
                        if matches!(
                            field_context.name.as_str(),
                            "other_config" | "external_ids"
                        ) {
                            field_context.is_number_or_string = true
                        }
                        self.parse_field_type(value.clone(), field_context);
                    }
                }
            } else {
                self.emitter
                    .emit_type_name(last_segment_name, field_context);
            }
        }
    }

    fn parse_serde_alias(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "alias")
    }

    fn parse_serde_rename(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "rename")
    }

    fn parse_serde_skip_serialization_if(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "skip_serializing_if")
    }

    fn has_serde_skip_serialization(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> bool {
        self.parse_serde_attribute(attributes, "skip_serializing")
            .is_some()
    }

    fn parse_serde_rename_all(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "rename_all")
    }

    fn parse_serde_deserialize_with(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_serde_attribute(attributes, "deserialize_with")
    }

    fn has_serde_deserialize_with_number_or_string(
        &mut self,
        attributes: &Vec<syn::Attribute>,
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
                    | "parse_ipsec_iface"
            ),
            _ => false,
        }
    }

    fn parse_serde_attribute(
        &mut self,
        attributes: &Vec<syn::Attribute>,
        attribute_name: &str,
    ) -> Option<String> {
        self.parse_attribute("serde", attributes, Some(attribute_name))
    }

    fn parse_repr_attribute(
        &mut self,
        attributes: &Vec<syn::Attribute>,
    ) -> Option<String> {
        self.parse_attribute("repr", attributes, None)
    }

    fn parse_attribute(
        &mut self,
        key: &str,
        attributes: &Vec<syn::Attribute>,
        attribute_name_op: Option<&str>,
    ) -> Option<String> {
        for attr in attributes {
            if let syn::Meta::List(list) = attr.clone().meta {
                if let Some(first_segment) = list.path.segments.first() {
                    if first_segment.ident == key {
                        let mut tokens_iter = list.tokens.into_iter();
                        while let Some(token) = tokens_iter.next() {
                            if let proc_macro2::TokenTree::Ident(iden_token) =
                                token
                            {
                                match attribute_name_op {
                                    Some(attribute_name) => {
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
                                    None => {
                                        return Some(iden_token.to_string());
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        None
    }

    fn parse_docs(&mut self, attributes: &Vec<syn::Attribute>) -> String {
        let mut docs = String::new();
        for attr in attributes {
            if let Meta::NameValue(meta) = attr.meta.clone() {
                if let Expr::Lit(lit) = meta.value {
                    if let Lit::Str(doc_str) = lit.lit {
                        docs.push_str(doc_str.value().as_str());
                        docs.push('\n');
                    }
                }
            }
        }
        docs
    }
}

impl GolangEmitter {
    fn emit_enum_begin(
        &mut self,
        enum_ctx: &EnumContext,
    ) -> &mut GolangEmitter {
        let enum_type = if enum_ctx.is_number_or_string {
            "intstr.IntOrString"
        } else if enum_ctx.repr == Some("u8".to_string()) {
            "uint8"
        } else {
            "string"
        };
        self.emit_docs(&enum_ctx.name, &enum_ctx.docs);
        if enum_ctx.is_number_or_string {
            self.emit_int_or_string_validation();
        }
        self.emit_enum_validation(enum_ctx);
        self.output.push_str("type ");
        self.output.push_str(&enum_ctx.name);
        self.output.push(' ');
        self.output.push_str(enum_type);
        self.output.push('\n');
        if enum_ctx.is_number_or_string {
            self.emit_enum_int_or_string_json_encoding(enum_ctx);
        }
        self
    }

    fn emit_enum_variant(
        &mut self,
        variant_ctx: &VariantContext,
    ) -> &mut GolangEmitter {
        let name = format!("{}{}", &variant_ctx.enum_name, &variant_ctx.name);
        self.emit_docs(&name, &variant_ctx.docs);
        if variant_ctx.enum_is_number_or_string {
            self.output.push_str("var ");
        } else {
            self.output.push_str("const ");
        }
        self.output.push_str(&name);
        self.output.push_str(" = ");
        self.output.push_str(&variant_ctx.enum_name);
        if !variant_ctx.enum_is_number_or_string
            && variant_ctx.u8_discriminant.is_some()
        {
            self.output.push('(');
            self.output.push_str(
                format!("{}", variant_ctx.u8_discriminant.unwrap()).as_str(),
            );
            self.output.push_str(")\n");
        } else {
            if variant_ctx.enum_is_number_or_string {
                self.output.push_str("(intstr.FromString(\"");
                self.emit_enum_variant_string(variant_ctx);
                self.output.push_str("\"))");
            } else {
                self.output.push('(');
                self.output.push('"');
                self.emit_enum_variant_string(variant_ctx);
                self.output.push('"');
                self.output.push(')');
            }
            self.output.push('\n');
        }
        self
    }
    fn emit_enum_variant_string(
        &mut self,
        variant_ctx: &VariantContext,
    ) -> &mut GolangEmitter {
        if let Some(variant_name) = variant_ctx.serde_rename.as_ref() {
            self.output.push_str(variant_name);
        } else if Some(String::from("kebab-case"))
            == variant_ctx.enum_serde_rename_all
        {
            self.output.push_str(&to_kebab_case(&variant_ctx.name));
        } else if Some(String::from("snake_case"))
            == variant_ctx.enum_serde_rename_all
        {
            self.output.push_str(&to_snake_case(&variant_ctx.name));
        } else if Some(String::from("lowercase"))
            == variant_ctx.enum_serde_rename_all
        {
            self.output.push_str(&variant_ctx.name.to_lowercase());
        } else {
            self.output.push_str(&variant_ctx.name);
        }
        self
    }
    fn emit_enum_end(&mut self, name: String) -> &mut GolangEmitter {
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
    fn emit_int_or_string_validation(&mut self) -> &mut GolangEmitter {
        self.output
            .push_str("// +kubebuilder:validation:XIntOrString\n");
        self
    }

    fn emit_enum_validation(
        &mut self,
        enum_ctx: &EnumContext,
    ) -> &mut GolangEmitter {
        // If the enum has "Other(String)" variant it means that
        // it can be everything so it should not be validated
        if enum_ctx.has_other_variant && enum_ctx.name != "InterfaceType" {
            return self;
        }
        self.output.push_str("// +kubebuilder:validation:Enum=");
        for variant in &enum_ctx.variants {
            if let Some(u8_discriminant) = variant.u8_discriminant {
                self.output
                    .push_str(format!("{}", u8_discriminant).as_str());
                self.output.push(';');
            }
            if variant.u8_discriminant.is_none()
                || variant.enum_is_number_or_string
            {
                self.output.push('"');
                self.emit_enum_variant_string(variant);
                self.output.push('"');
                self.output.push(';');
            }
            if let Some(alias) = &variant.serde_alias {
                self.output.push('"');
                self.output.push_str(alias);
                self.output.push('"');
                self.output.push(';');
            }
        }
        self.output.push('\n');
        self
    }

    fn emit_docs(&mut self, name: &str, docs: &str) -> &mut GolangEmitter {
        for (i, doc_line) in docs.lines().enumerate() {
            self.output.push_str("//");
            if i == 0 {
                self.output.push(' ');
                self.output.push_str(name);
                self.output.push(' ');
            }
            self.output.push_str(doc_line);
            self.output.push('\n');
        }
        self
    }

    fn emit_struct_begin(
        &mut self,
        struct_ctx: &StructContext,
    ) -> &mut GolangEmitter {
        self.emit_docs(&struct_ctx.name, &struct_ctx.docs);
        self.output.push_str("// +k8s:deepcopy-gen=true\n");
        self.output.push_str("type ");
        self.output.push_str(&struct_ctx.name);
        self.output.push_str(" struct {\n");
        self
    }

    fn emit_struct_end(&mut self) -> &mut GolangEmitter {
        self.output.push_str("}\n\n");
        self
    }

    fn emit_field_begin(
        &mut self,
        field_ctx: &FieldContext,
    ) -> &mut GolangEmitter {
        let golang_field_name = rust_name_to_golang_name(&field_ctx.name);
        self.emit_docs(&golang_field_name, &field_ctx.docs);
        self.output.push_str("  ");
        self.output.push_str(&golang_field_name);
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
        if (type_name == "String" && !field_ctx.is_number_or_string)
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
            self.output.push('*');
            self.output.push_str(&rust_name_to_golang_name(&type_name));
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
            self.output.push_str(&rust_name_to_golang_name(&type_name));
        } else if type_name == "InterfaceIpv4" || type_name == "InterfaceIpv6" {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            self.output.push_str("InterfaceIP");
        } else {
            if field_ctx.is_optional {
                self.emit_optional();
            }
            match type_name.as_str() {
                "bool" => {
                    self.output.push_str(&type_name);
                }
                _ => {
                    self.output.push_str(&rust_name_to_golang_name(&type_name));
                }
            }
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
    fn emit_header(&mut self) -> &mut GolangEmitter {
        //self.output.push_str("//go:build !ignore_autogenerated\n\n");
        self.output.push_str(&self.header);
        //self.output.push_str(
        //   "\n// Code generated by nmstate-go-apigen. DO NOT EDIT.\n",
        //);
        self
    }
    fn emit_enum_int_or_string_json_encoding(
        &mut self,
        enum_ctx: &EnumContext,
    ) -> &mut GolangEmitter {
        self.output.push_str(
            format!(
                r#"
func (o {enum_name}) MarshalJSON() ([]byte, error) {{
	return intstr.IntOrString(o).MarshalJSON()
}}

func (o *{enum_name}) UnmarshalJSON(data []byte) error {{
	oi := intstr.IntOrString(*o)
	if err := oi.UnmarshalJSON(data); err != nil {{
		return err
	}}
	*o = {enum_name}(oi)
	return nil
}}

"#,
                enum_name = enum_ctx.name
            )
            .as_str(),
        );
        self
    }
    fn emit_bridge_interface(
        &mut self,
        linux_bridge_interface: &StructContext,
        ovs_bridge_interface: &StructContext,
    ) -> &mut GolangEmitter {
        self.output.push_str(
            r#"
// +k8s:deepcopy-gen=true
type OVSBridgeStpOptions struct {
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
	*OVSBridgePortConfig     `json:",omitempty"`
	*LinuxBridgePortConfig   `json:",omitempty"`
}

// +k8s:deepcopy-gen=true
type BridgeOptions struct {
	*LinuxBridgeOptions `json:",omitempty"`
	*OVSBridgeOptions   `json:",omitempty"`
}
"#,
        );

        self.emit_docs("BridgeConfig", "Linux or OVS bridge configuration");
        self.emit_docs("", "    ");
        self.emit_docs("Linux bridge: ", &linux_bridge_interface.docs);
        self.emit_docs("", "    ");
        self.emit_docs("OVS bridge: ", &ovs_bridge_interface.docs);
        self.output.push_str(
            r#"// +k8s:deepcopy-gen=true
type BridgeConfig struct {
	*OVSBridgeConfig `json:",omitempty"`
	Options          *BridgeOptions      `json:"options,omitempty"`
	Ports            *[]BridgePortConfig `json:"port,omitempty"`
}
"#,
        );
        self.output.push_str(
            r#"// +k8s:deepcopy-gen=true
type BridgeInterface struct {
	*BridgeConfig `json:"bridge,omitempty"`
}
"#,
        );
        self
    }
}

pub fn to_kebab_case(s: &str) -> String {
    Converter::new()
        .remove_boundaries(&Boundary::digits())
        .to_case(Case::Kebab)
        .convert(s)
}

pub fn to_snake_case(s: &str) -> String {
    s.to_case(Case::Snake)
}

pub fn rust_name_to_golang_name(s: &str) -> String {
    let mut golang_name = String::new();
    // Convert everyting to snake case so we can easily split and
    // follow the golang naming conventin for Acronyms.
    for word in to_snake_case(s).split('_') {
        let golang_word = match word {
            "ovn" | "ovs" | "uuid" | "db" | "udp" | "tcp" | "ip" | "dns"
            | "id" => word.to_uppercase(),
            _ => capitalize(word),
        };
        golang_name.push_str(&golang_word);
    }
    golang_name
}

pub fn capitalize(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(f) => f.to_uppercase().collect::<String>() + c.as_str(),
    }
}
