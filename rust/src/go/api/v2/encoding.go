package v2

import (
	"bytes"
	"encoding/json"
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
		BridgePortConfigMetadata
		*LinuxBridgePortConfig
	}{}
	ovsBridgePortConfig := struct {
		BridgePortConfigMetadata
		*OvsBridgePortConfig
	}{}
	if err := strictDecoder(data).Decode(&linuxBridgePortConfig); err == nil {
		o.BridgePortConfigMetadata = linuxBridgePortConfig.BridgePortConfigMetadata
		o.LinuxBridgePortConfig = linuxBridgePortConfig.LinuxBridgePortConfig
	} else if err := strictDecoder(data).Decode(&ovsBridgePortConfig); err == nil {
		o.BridgePortConfigMetadata = ovsBridgePortConfig.BridgePortConfigMetadata
		o.OvsBridgePortConfig = ovsBridgePortConfig.OvsBridgePortConfig
	}
	return nil
}

func (o BridgePortConfig) MarshalJSON() ([]byte, error) {
	if o.LinuxBridgePortConfig != nil {
		return json.Marshal(struct {
			BridgePortConfigMetadata
			*LinuxBridgePortConfig
		}{
			o.BridgePortConfigMetadata,
			o.LinuxBridgePortConfig,
		})
	}
	if o.OvsBridgePortConfig != nil {
		return json.Marshal(struct {
			BridgePortConfigMetadata
			*OvsBridgePortConfig
		}{
			o.BridgePortConfigMetadata,
			o.OvsBridgePortConfig,
		})
	}
	return json.Marshal(o.BridgePortConfigMetadata)
}

func (o *OvsBridgeStpOptions) UnmarshalJSON(data []byte) error {
	if err := json.Unmarshal(data, &o.Enabled); err == nil {
		o.marshalNested = true
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
	if o.marshalNested {
		return json.Marshal(&o.Enabled)
	}
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
