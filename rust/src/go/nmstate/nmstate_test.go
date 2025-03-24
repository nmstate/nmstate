// SPDX-License-Identifier: Apache-2.0

package nmstate

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRetrieveNetState(t *testing.T) {
	f, err := os.Create("file.txt")
	if err != nil {
		panic(err)
	}
	defer f.Close()
	nms := New(WithLogsWritter(f))
	netState, err := nms.RetrieveNetState()
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
}

func TestRetrieveNetStateKernelOnly(t *testing.T) {
	f, err := os.Create("file.txt")
	if err != nil {
		panic(err)
	}
	defer f.Close()
	nms := New(WithLogsWritter(f), WithKernelOnly())
	netState, err := nms.RetrieveNetState()
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
}

func TestApplyNetState(t *testing.T) {
	nms := New()
	netState, err := nms.ApplyNetState(`{
"interfaces": [{
  "name": "dummy1",
  "state": "up",
  "type": "dummy"
}]}
`)
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
}

func TestApplyNetStateWithCommit(t *testing.T) {
	nms := New(WithNoCommit())
	netState, err := nms.ApplyNetState(`{
"interfaces": [{
  "name": "dummy1",
  "state": "up",
  "type": "dummy"
}]}
`)
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")

	_, err = nms.CommitCheckpoint("")
	assert.NoError(t, err, "must succeed commiting last active checkpoint")
}

func TestGenerateConfiguration(t *testing.T) {
	nms := New()
	config, err := nms.GenerateConfiguration(`{
"interfaces": [{
  "name": "dummy1",
  "state": "up",
  "type": "dummy"
}]}
`)
	assert.NoError(t, err, "must succeed calling nmstate_generate_configurations c binding")
	assert.NotEmpty(t, config, "config should not be empty")
}

func TestGenerateStateFromPolicy(t *testing.T) {
	nms := New()
	// Define a sample policy and current state
	policy := `{
		"capture": {
			"ethernets": "interfaces.type==\"ethernet\"",
			"ethernets-up": "capture.ethernets.interfaces.state==\"up\"",
			"ethernets-lldp": "capture.ethernets-up | interfaces.lldp.enabled:=true"
		},
		"desiredState": {
			"interfaces": "{{ capture.ethernets-lldp.interfaces }}"
		}
	}`

	currentState := `{
		"interfaces": [
			{
				"name": "eth0",
				"type": "ethernet",
				"state": "up",
				"mac-address": "52:55:00:D1:55:01",
				"accept-all-mac-addresses": false,
				"lldp": {
					"enabled": false
				}
			},
			{
				"name": "eth1",
				"type": "ethernet",
				"state": "down",
				"mac-address": "52:55:00:D1:56:02",
				"accept-all-mac-addresses": false,
				"lldp": {
					"enabled": false
				}
			},
			{
				"name": "eth2",
				"type": "ethernet",
				"state": "down",
				"mac-address": "52:55:00:D1:56:04",
				"accept-all-mac-addresses": false
			},
			{
				"name": "eth4",
				"type": "ethernet",
				"state": "up",
				"mac-address": "52:55:00:D1:57:03",
				"accept-all-mac-addresses": false
			}
		]
	}`

	state, err := nms.GenerateStateFromPolicy(policy, currentState)
	assert.NoError(t, err, "must succeed calling nmstate_net_state_from_policy c binding")
	assert.NotEmpty(t, state, "state should not be empty")
}
