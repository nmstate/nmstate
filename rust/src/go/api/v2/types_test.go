package v2

import (
	"fmt"
	"io/fs"
	"io/ioutil"
	"path/filepath"
	"strings"
	"testing"

	"sigs.k8s.io/yaml"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func removeNullFields(originalState interface{}) interface{} {
	originalStateSlice, isSlice := originalState.([]interface{})
	if isSlice {
		modifiedState := []interface{}{}
		for _, value := range originalStateSlice {
			modifiedState = append(modifiedState, removeNullFields(value))
		}
		return modifiedState
	}
	originalStateMap, isMap := originalState.(map[string]interface{})
	if isMap {
		modifiedState := map[string]interface{}{}
		for key, value := range originalStateMap {
			if value != nil {
				modifiedState[key] = removeNullFields(value)
			}
		}
		return modifiedState
	}
	return originalState
}

func normalizeState(state map[string]interface{}) map[string]interface{} {
	ifaces, ok := state["interfaces"]
	if ok {
		if len(ifaces.([]interface{})) == 0 {
			delete(state, "interfaces")
		} else {
			state["interfaces"] = removeNullFields(ifaces)
		}
	}
	return state
}

func assertStateEq(t *testing.T, expected string, actual string, msgAndArgs ...interface{}) bool {
	var expectedYAMLAsInterface, actualYAMLAsInterface map[string]interface{}

	if err := yaml.Unmarshal([]byte(expected), &expectedYAMLAsInterface); err != nil {
		return assert.Fail(t, fmt.Sprintf("Expected value ('%s') is not valid yaml.\nYAML parsing error: '%s'", expected, err.Error()), msgAndArgs...)
	}

	if err := yaml.Unmarshal([]byte(actual), &actualYAMLAsInterface); err != nil {
		return assert.Fail(t, fmt.Sprintf("Input ('%s') needs to be valid yaml.\nYAML error: '%s'", actual, err.Error()), msgAndArgs...)
	}

	return assert.Equal(t, normalizeState(expectedYAMLAsInterface), normalizeState(actualYAMLAsInterface), msgAndArgs...)
}

func testNetworkState(t *testing.T, expectedState []byte) {
	netState := &NetworkState{}
	err := yaml.UnmarshalStrict(expectedState, netState)
	assert.NoError(t, err, "must success unmarshaling state")

	obtainedState, err := yaml.Marshal(netState)
	assert.NoError(t, err, "must success marshaling state")

	assertStateEq(t, string(expectedState), string(obtainedState), "---> expected <--- \n%s\n ---> obtained <--- \n%s\n", expectedState, obtainedState)
}

func testUnmarshalDir(t *testing.T, dir string) {
	states := map[string][]byte{}
	err := filepath.Walk(dir, func(path string, info fs.FileInfo, err error) error {
		if info.IsDir() && info.Name() == "policy" {
			return filepath.SkipDir
		}
		if info.IsDir() || filepath.Ext(info.Name()) != ".yml" || strings.Contains(info.Name(), "rollback") {
			return nil
		}
		state, err := ioutil.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed reading state '%s': %v", info.Name(), err)
		}
		states[info.Name()] = state
		return nil
	})
	require.NoError(t, err, "must succeed reading states")
	for stateName, expectedState := range states {
		t.Run(stateName, func(t *testing.T) {
			testNetworkState(t, expectedState)
		})
	}
}

func TestUnmarshallingExamples(t *testing.T) {
	testUnmarshalDir(t, "../../../../../examples")
}

func TestUnmarshallingIntegrationTests(t *testing.T) {
	testUnmarshalDir(t, "../../../../../tests/integration/.states/")
}
