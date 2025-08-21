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
