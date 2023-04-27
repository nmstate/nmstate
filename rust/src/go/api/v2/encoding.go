/*
Copyright The NMState Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

//go:generate cargo run --bin nmstate-go-apigen ../../../lib zz_generated.types.go --header-file=boilerplate.go.txt
//go:generate ./controller-gen.sh object:headerFile="boilerplate.go.txt" paths="."
package v2

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

func replaceDeprecatedNames(data []byte) []byte {
	data = []byte(strings.ReplaceAll(string(data), `"slaves"`, `"port"`))
	data = []byte(strings.ReplaceAll(string(data), "slaves:", "port:"))
	return data
}

func (i *Interface) UnmarshalJSON(data []byte) error {
	type InterfaceInternal Interface
	var interfaceInternal InterfaceInternal
	if err := strictDecoder(replaceDeprecatedNames(data)).Decode(&interfaceInternal); err != nil {
		return err
	}
	*i = Interface(interfaceInternal)
	return nil
}

func (o *BridgeOptions) UnmarshalJSON(data []byte) error {
	linuxBridgeOptions := LinuxBridgeOptions{}
	ovsBridgeOptions := OVSBridgeOptions{}

	var linuxErr, ovsErr error
	if linuxErr = strictDecoder(data).Decode(&linuxBridgeOptions); linuxErr == nil {
		o.LinuxBridgeOptions = &linuxBridgeOptions
	} else if ovsErr = strictDecoder(data).Decode(&ovsBridgeOptions); ovsErr == nil {
		o.OVSBridgeOptions = &ovsBridgeOptions
	} else {
		return errors.Join(linuxErr, ovsErr)
	}
	return nil
}

func (o BridgeOptions) MarshalJSON() ([]byte, error) {
	if o.LinuxBridgeOptions != nil {
		return json.Marshal(o.LinuxBridgeOptions)
	}
	if o.OVSBridgeOptions != nil {
		return json.Marshal(o.OVSBridgeOptions)
	}
	return nil, nil
}

func (o *BridgePortConfig) UnmarshalJSON(data []byte) error {
	linuxBridgePortConfig := struct {
		BridgePortConfigMetaData
		*LinuxBridgePortConfig
	}{}
	ovsBridgePortConfig := struct {
		BridgePortConfigMetaData
		*OVSBridgePortConfig
	}{}
	var linuxErr, ovsErr error
	if linuxErr = strictDecoder(data).Decode(&linuxBridgePortConfig); linuxErr == nil {
		o.BridgePortConfigMetaData = linuxBridgePortConfig.BridgePortConfigMetaData
		o.LinuxBridgePortConfig = linuxBridgePortConfig.LinuxBridgePortConfig
	} else if ovsErr = strictDecoder(data).Decode(&ovsBridgePortConfig); ovsErr == nil {
		o.BridgePortConfigMetaData = ovsBridgePortConfig.BridgePortConfigMetaData
		o.OVSBridgePortConfig = ovsBridgePortConfig.OVSBridgePortConfig
	} else {
		return errors.Join(linuxErr, ovsErr)
	}
	return nil
}

func (o BridgePortConfig) MarshalJSON() ([]byte, error) {
	if o.LinuxBridgePortConfig != nil {
		return json.Marshal(struct {
			BridgePortConfigMetaData
			*LinuxBridgePortConfig
		}{
			o.BridgePortConfigMetaData,
			o.LinuxBridgePortConfig,
		})
	}
	if o.OVSBridgePortConfig != nil {
		return json.Marshal(struct {
			BridgePortConfigMetaData
			*OVSBridgePortConfig
		}{
			o.BridgePortConfigMetaData,
			o.OVSBridgePortConfig,
		})
	}
	return json.Marshal(o.BridgePortConfigMetaData)
}

func (o *OVSBridgeStpOptions) UnmarshalJSON(data []byte) error {
	if err := json.Unmarshal(data, &o.Enabled); err == nil {
		return nil
	}
	type ovsBridgeStpOptions OVSBridgeStpOptions
	stp := ovsBridgeStpOptions{}
	if err := json.Unmarshal(data, &stp); err != nil {
		return err
	}
	o.Enabled = stp.Enabled
	return nil
}

func (o OVSBridgeStpOptions) MarshalJSON() ([]byte, error) {
	type ovsBridgeStpOptions OVSBridgeStpOptions
	stp := ovsBridgeStpOptions{}
	stp.Enabled = o.Enabled
	return json.Marshal(&stp)
}

func (o *LldpNeighborTlv) MarshalJSON() ([]byte, error) {
	if o.LldpSystemName != nil {
		return json.Marshal(o.LldpSystemName)
	} else if o.LldpSystemDescription != nil {
		return json.Marshal(o.LldpSystemDescription)
	} else if o.LldpSystemCapabilities != nil {
		return json.Marshal(o.LldpSystemCapabilities)
	} else if o.LldpChassisID != nil {
		return json.Marshal(o.LldpChassisID)
	} else if o.LldpPortID != nil {
		return json.Marshal(o.LldpPortID)
	} else if o.LldpVlans != nil {
		return json.Marshal(o.LldpVlans)
	} else if o.LldpMacPhy != nil {
		return json.Marshal(o.LldpMacPhy)
	} else if o.LldpPpvids != nil {
		return json.Marshal(o.LldpPpvids)
	} else if o.LldpMgmtAddrs != nil {
		return json.Marshal(o.LldpMgmtAddrs)
	} else if o.LldpMaxFrameSize != nil {
		return json.Marshal(o.LldpMaxFrameSize)
	} else {
		return nil, fmt.Errorf("unexpected LldpNeighborTlv: %+v", o)
	}
}

func (o *LldpNeighborTlv) UnmarshalJSON(data []byte) error {
	neighbor := struct {
		Type    LldpNeighborTlvType
		Subtype *LldpOrgSubtype
	}{}
	if err := json.Unmarshal(data, &neighbor); err != nil {
		return fmt.Errorf("failed unmarshaling type and subtype: %w", err)
	}
	switch neighbor.Type {
	case LldpNeighborTlvTypeSystemName:
		o.LldpSystemName = &LldpSystemName{}
		return strictDecoder(data).Decode(o.LldpSystemName)
	case LldpNeighborTlvTypeSystemDescription:
		o.LldpSystemDescription = &LldpSystemDescription{}
		return strictDecoder(data).Decode(o.LldpSystemDescription)
	case LldpNeighborTlvTypeSystemCapabilities:
		o.LldpSystemCapabilities = &LldpSystemCapabilities{}
		return strictDecoder(data).Decode(o.LldpSystemCapabilities)
	case LldpNeighborTlvTypeChassisID:
		o.LldpChassisID = &LldpChassisID{}
		return strictDecoder(data).Decode(o.LldpChassisID)
	case LldpNeighborTlvTypePort:
		o.LldpPortID = &LldpPortID{}
		return strictDecoder(data).Decode(o.LldpPortID)
	case LldpNeighborTlvTypeManagementAddress:
		o.LldpMgmtAddrs = &LldpMgmtAddrs{}
		return strictDecoder(data).Decode(o.LldpMgmtAddrs)
	case LldpNeighborTlvTypeOrganizationSpecific:
		if neighbor.Subtype == nil {
			return fmt.Errorf("missing lldp neighbor org subtype")
		}
		switch *neighbor.Subtype {
		case LldpOrgSubtypeVlan:
			o.LldpVlans = &LldpVlans{}
			return strictDecoder(data).Decode(o.LldpVlans)
		case LldpOrgSubtypePpvids:
			o.LldpPpvids = &LldpPpvids{}
			return strictDecoder(data).Decode(o.LldpPpvids)
		case LldpOrgSubtypeMacPhyConf:
			o.LldpMacPhy = &LldpMacPhy{}
			return strictDecoder(data).Decode(o.LldpMacPhy)
		case LldpOrgSubtypeMaxFrameSize:
			o.LldpMaxFrameSize = &LldpMaxFrameSize{}
			return strictDecoder(data).Decode(o.LldpMaxFrameSize)
		default:
			return fmt.Errorf("unknown lldp neighbor org subtype: %+v", neighbor.Subtype)
		}
	default:
		return fmt.Errorf("unknown lldp neighbor type: %+v", neighbor.Type)
	}
}

func strictDecoder(data []byte) *json.Decoder {
	decoder := json.NewDecoder(bytes.NewBuffer(data))
	decoder.DisallowUnknownFields()
	return decoder
}

func (s NetworkState) String() string {
	raw, err := json.Marshal(&s)
	if err != nil {
		return ""
	}
	return string(raw)
}
