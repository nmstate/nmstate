package v2

// #cgo CFLAGS: -g -Wall
// #cgo LDFLAGS: -lnmstate
// #include <nmstate.h>
// #include <stdlib.h>
import "C"
import (
	"encoding/json"
	"fmt"
	"io"
	"time"

	"sigs.k8s.io/yaml"

	nmstateapi "github.com/nmstate/nmstate/rust/src/go/api/v2"
)

type Nmstate struct {
	timeout    uint
	logsWriter io.Writer
	flags      byte
}

const (
	kernelOnly = 2 << iota
	noVerify
	includeStatusData
	includeSecrets
	noCommit
	memoryOnly
	runningConfigOnly
)

func New(options ...func(*Nmstate)) *Nmstate {
	nms := &Nmstate{}
	for _, option := range options {
		option(nms)
	}
	return nms
}

func WithTimeout(timeout time.Duration) func(*Nmstate) {
	return func(n *Nmstate) {
		n.timeout = uint(timeout.Seconds())
	}
}

func WithLogsWritter(logWriter io.Writer) func(*Nmstate) {
	return func(n *Nmstate) {
		n.logsWriter = logWriter
	}
}

func WithKernelOnly() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= kernelOnly
	}
}

func WithNoVerify() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= noVerify
	}
}

func WithIncludeStatusData() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= includeStatusData
	}
}

func WithIncludeSecrets() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= includeSecrets
	}
}

func WithNoCommit() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= noCommit
	}
}

func WithMemoryOnly() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= memoryOnly
	}
}

func WithRunningConfigOnly() func(*Nmstate) {
	return func(n *Nmstate) {
		n.flags |= runningConfigOnly
	}
}

// Retrieve the network state in json format. This function returns the current
// network state or an error.
func (n *Nmstate) RetrieveNetState() (string, error) {
	var (
		cState  *C.char
		log     *C.char
		errKind *C.char
		errMsg  *C.char
	)
	rc := C.nmstate_net_state_retrieve(C.uint(n.flags), &cState, &log, &errKind, &errMsg)
	defer func() {
		C.nmstate_cstring_free(cState)
		C.nmstate_cstring_free(errMsg)
		C.nmstate_cstring_free(errKind)
		C.nmstate_cstring_free(log)
	}()
	if rc != 0 {
		return "", fmt.Errorf("failed retrieving nmstate net state with rc: %d, errMsg: %s, errKind: %s", rc, C.GoString(errMsg), C.GoString(errKind))
	}
	if err := n.writeLog(log); err != nil {
		return "", fmt.Errorf("failed when retrieving state: %w", err)
	}
	return C.GoString(cState), nil
}

// Retrieve the network state in as golang struct. This function returns the current
// network state or an error.
func (n *Nmstate) RetrieveStructuredNetState() (*nmstateapi.NetworkState, error) {
	networkStateMarshaled, err := n.RetrieveNetState()
	if err != nil {
		return nil, err
	}
	networkState := &nmstateapi.NetworkState{}
	if err := yaml.Unmarshal([]byte(networkStateMarshaled), networkState); err != nil {
		return nil, err
	}
	return networkState, nil
}

// Apply the network state in json format. This function returns the applied
// network state or an error.
func (n *Nmstate) ApplyNetState(state string) (string, error) {
	var (
		cState  *C.char
		log     *C.char
		errKind *C.char
		errMsg  *C.char
	)
	cState = C.CString(state)
	rc := C.nmstate_net_state_apply(C.uint(n.flags), cState, C.uint(n.timeout), &log, &errKind, &errMsg)

	defer func() {
		C.nmstate_cstring_free(cState)
		C.nmstate_cstring_free(errMsg)
		C.nmstate_cstring_free(errKind)
		C.nmstate_cstring_free(log)
	}()
	if rc != 0 {
		return "", fmt.Errorf("failed applying nmstate net state %s with rc: %d, errMsg: %s, errKind: %s", state, rc, C.GoString(errMsg), C.GoString(errKind))
	}
	if err := n.writeLog(log); err != nil {
		return "", fmt.Errorf("failed when applying state: %w", err)
	}
	return state, nil
}

// Apply the network state as golang struct . This function returns the applied
// network state or an error.
func (n *Nmstate) ApplyStructuredNetState(state *nmstateapi.NetworkState) (*nmstateapi.NetworkState, error) {
	networkStateMarshaled, err := json.Marshal(state)
	if err != nil {
		return nil, err
	}
	appliedNetworkState, err := n.ApplyNetState(string(networkStateMarshaled))
	if err != nil {
		return nil, err
	}
	appliedNetworkStateUnmarshaled := &nmstateapi.NetworkState{}
	if err := yaml.Unmarshal([]byte(appliedNetworkState), appliedNetworkStateUnmarshaled); err != nil {
		return nil, err
	}
	return appliedNetworkStateUnmarshaled, err
}

// Commit the checkpoint path provided. This function returns the committed
// checkpoint path or an error.
func (n *Nmstate) CommitCheckpoint(checkpoint string) (string, error) {
	return n.handleCheckpoint(checkpoint, "commit", func(cCheckpoint *C.char, log, errKind, errMsg **C.char) C.int {
		return C.nmstate_checkpoint_commit(cCheckpoint, log, errKind, errMsg)
	})
}

// Rollback to the checkpoint provided. This function returns the checkpoint
// path used for rollback or an error.
func (n *Nmstate) RollbackCheckpoint(checkpoint string) (string, error) {
	return n.handleCheckpoint(checkpoint, "rollback", func(cCheckpoint *C.char, log, errKind, errMsg **C.char) C.int {
		return C.nmstate_checkpoint_rollback(cCheckpoint, log, errKind, errMsg)
	})
}

// Commit the checkpoint path provided. This function returns the committed
// checkpoint path or an error.
func (n *Nmstate) handleCheckpoint(checkpoint, opType string, checkpointFn func(*C.char, **C.char, **C.char, **C.char) C.int) (string, error) {
	var (
		cCheckpoint *C.char
		log         *C.char
		errKind     *C.char
		errMsg      *C.char
	)
	cCheckpoint = C.CString(checkpoint)
	rc := checkpointFn(cCheckpoint, &log, &errKind, &errMsg)

	defer func() {
		C.nmstate_cstring_free(cCheckpoint)
		C.nmstate_cstring_free(errMsg)
		C.nmstate_cstring_free(errKind)
		C.nmstate_cstring_free(log)
	}()
	if rc != 0 {
		return "", fmt.Errorf("failed %s checkpoint %s with rc: %d, errMsg: %s, errKind: %s", opType, checkpoint, rc, C.GoString(errMsg), C.GoString(errKind))
	}
	if err := n.writeLog(log); err != nil {
		return "", fmt.Errorf("failed at %s transaction: %w", opType, err)
	}
	return checkpoint, nil
}

func (n *Nmstate) writeLog(log *C.char) error {
	if n.logsWriter == nil {
		return nil
	}
	_, err := io.WriteString(n.logsWriter, C.GoString(log))
	if err != nil {
		return fmt.Errorf("failed writting logs: %w", err)
	}
	return nil
}

// GenerateConfiguration generates the configuration for the state provided.
// This function returns the configuration files for the state provided.
func (n *Nmstate) GenerateConfiguration(state string) (string, error) {
	var (
		cState  *C.char
		config  *C.char
		log     *C.char
		errKind *C.char
		errMsg  *C.char
	)
	cState = C.CString(state)
	rc := C.nmstate_generate_configurations(cState, &config, &log, &errKind, &errMsg)

	defer func() {
		C.nmstate_cstring_free(cState)
		C.nmstate_cstring_free(config)
		C.nmstate_cstring_free(errMsg)
		C.nmstate_cstring_free(errKind)
		C.nmstate_cstring_free(log)
	}()
	if rc != 0 {
		return "", fmt.Errorf("failed when generating the configuration %s with rc: %d, errMsg: %s, errKind: %s", state, rc, C.GoString(errMsg), C.GoString(errKind))
	}
	if err := n.writeLog(log); err != nil {
		return "", fmt.Errorf("failed when generating the configuration: %w", err)
	}
	return C.GoString(config), nil
}
