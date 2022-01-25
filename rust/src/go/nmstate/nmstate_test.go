package nmstate

import (
	"os"
	"strings"
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
	nmstateLog := strings.Builder{}
	nms := New(WithLogsWritter(&nmstateLog))
	netState, err := nms.ApplyNetState(`{
"interfaces": [{
  "name": "dummy1",
  "state": "up",
  "type": "dummy"
}]}
`)
	assert.NoError(t, err, "must succeed calling retrieve_net_state c binding")
	assert.NotEmpty(t, netState, "net state should not be empty")
	assert.NotEmpty(t, nmstateLog.String(), "should dump info logs")
}
