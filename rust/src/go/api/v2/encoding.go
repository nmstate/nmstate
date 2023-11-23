//go:generate cargo run --bin nmstate-go-apigen ../../../lib zz_generated.types.go
//go:generate ./controller-gen.sh object:headerFile="boilerplate.go.txt" paths="."
package v2

import (
	"bytes"
	"encoding/json"
	"fmt"
)

func (o *BridgeOptions) UnmarshalJSON(data []byte) error {
	linuxBridgeOptions := LinuxBridgeOptions{}
	ovsBridgeOptions := OvsBridgeOptions{}
	if err := strictDecoder(data).Decode(&linuxBridgeOptions); err == nil {
		o.LinuxBridgeOptions = &linuxBridgeOptions
	} else if err := strictDecoder(data).Decode(&ovsBridgeOptions); err == nil {
		o.OvsBridgeOptions = &ovsBridgeOptions
	}
	return nil
}

func (o BridgeOptions) MarshalJSON() ([]byte, error) {
	if o.LinuxBridgeOptions != nil {
		return json.Marshal(o.LinuxBridgeOptions)
	}
	if o.OvsBridgeOptions != nil {
		return json.Marshal(o.OvsBridgeOptions)
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
		*OvsBridgePortConfig
	}{}
	var linuxErr, ovsErr error
	if linuxErr = strictDecoder(data).Decode(&linuxBridgePortConfig); linuxErr == nil {
		o.BridgePortConfigMetaData = linuxBridgePortConfig.BridgePortConfigMetaData
		o.LinuxBridgePortConfig = linuxBridgePortConfig.LinuxBridgePortConfig
	} else if ovsErr = strictDecoder(data).Decode(&ovsBridgePortConfig); ovsErr == nil {
		o.BridgePortConfigMetaData = ovsBridgePortConfig.BridgePortConfigMetaData
		o.OvsBridgePortConfig = ovsBridgePortConfig.OvsBridgePortConfig
	} else {
		return fmt.Errorf("failed unmarshaling bridge port, linux: %v, ovs: %v", linuxErr, ovsErr)
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
	if o.OvsBridgePortConfig != nil {
		return json.Marshal(struct {
			BridgePortConfigMetaData
			*OvsBridgePortConfig
		}{
			o.BridgePortConfigMetaData,
			o.OvsBridgePortConfig,
		})
	}
	return json.Marshal(o.BridgePortConfigMetaData)
}

func (o *OvsBridgeStpOptions) UnmarshalJSON(data []byte) error {
	if err := json.Unmarshal(data, &o.Enabled); err == nil {
		return nil
	}
	type ovsBridgeStpOptions OvsBridgeStpOptions
	stp := ovsBridgeStpOptions{}
	if err := json.Unmarshal(data, &stp); err != nil {
		return err
	}
	o.Enabled = stp.Enabled
	return nil
}

func (o OvsBridgeStpOptions) MarshalJSON() ([]byte, error) {
	type ovsBridgeStpOptions OvsBridgeStpOptions
	stp := ovsBridgeStpOptions{}
	stp.Enabled = o.Enabled
	return json.Marshal(&stp)
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
