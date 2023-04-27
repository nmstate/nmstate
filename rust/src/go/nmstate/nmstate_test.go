package nmstate

import (
	"os"
	"testing"

	"github.com/stretchr/testify/assert"

	nmstateapi "github.com/nmstate/nmstate/rust/src/go/api/v2"
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

func TestRetrieveStructuredNetState(t *testing.T) {
	f, err := os.Create("file.txt")
	if err != nil {
		panic(err)
	}
	defer f.Close()
	nms := New(WithLogsWritter(f))
	netState, err := nms.RetrieveStructuredNetState()
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

func TestRetrieveStructuredNetStateKernelOnly(t *testing.T) {
	f, err := os.Create("file.txt")
	if err != nil {
		panic(err)
	}
	defer f.Close()
	nms := New(WithLogsWritter(f), WithKernelOnly())
	netState, err := nms.RetrieveStructuredNetState()
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

func TestApplyStructuredNetState(t *testing.T) {
	nms := New()
	netState := &nmstateapi.NetworkState{
		Interfaces: []nmstateapi.Interface{{
			BaseInterface: nmstateapi.BaseInterface{
				Name:  "dummy",
				Type:  nmstateapi.InterfaceTypeDummy,
				State: nmstateapi.InterfaceStateUp,
			},
		}},
	}
	netState, err := nms.ApplyStructuredNetState(netState)
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

func TestApplyStructuredNetStateWithCommit(t *testing.T) {
	nms := New(WithNoCommit())
	netState := &nmstateapi.NetworkState{
		Interfaces: []nmstateapi.Interface{{
			BaseInterface: nmstateapi.BaseInterface{
				Name:  "dummy",
				State: nmstateapi.InterfaceStateUp,
				Type:  nmstateapi.InterfaceTypeDummy,
			},
		}},
	}
	netState, err := nms.ApplyStructuredNetState(netState)
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
