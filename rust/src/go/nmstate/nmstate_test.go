package nmstate

import (
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestRetrieveNetState(t *testing.T) {
	log := &strings.Builder{}
	nms := New(WithLogsWritter(log))
	netState, err := nms.RetrieveNetState()
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
	assert.NotEmpty(t, log.String(), "log should not be empty")
}

func TestRetrieveNetStateKernelOnly(t *testing.T) {
	log := &strings.Builder{}
	nms := New(WithLogsWritter(log), WithKernelOnly())
	netState, err := nms.RetrieveNetState()
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
	assert.NotEmpty(t, log.String(), "log should not be empty")
}

func TestApplyNetState(t *testing.T) {
	log := &strings.Builder{}
	nms := New(WithLogsWritter(log))
	netState, err := nms.ApplyNetState(`{
"interfaces": [{
  "name": "dummy1",
  "state": "up",
  "type": "dummy"
}]}
`)
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
	assert.NotEmpty(t, log.String(), "log should not be empty")
}

func TestApplyNetStateWithCommit(t *testing.T) {
	log := &strings.Builder{}
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
	assert.NotEmpty(t, log.String(), "log should not be empty")
}
