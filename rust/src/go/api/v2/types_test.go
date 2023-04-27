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

package v2

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"sigs.k8s.io/yaml"

	"github.com/stretchr/testify/require"
)

func removeNullFields(originalState any) any {
	originalStateSlice, isSlice := originalState.([]any)
	if isSlice {
		modifiedState := []any{}
		for _, value := range originalStateSlice {
			modifiedState = append(modifiedState, removeNullFields(value))
		}
		return modifiedState
	}
	originalStateMap, isMap := originalState.(map[string]any)
	if isMap {
		modifiedState := map[string]any{}
		for key, value := range originalStateMap {
			if value != nil {
				modifiedState[key] = removeNullFields(value)
			}
		}
		return modifiedState
	}
	return originalState
}

func normalizeState(state map[string]any) map[string]any {
	ifaces, ok := state["interfaces"]
	if ok {
		if len(ifaces.([]any)) == 0 {
			delete(state, "interfaces")
		} else {
			state["interfaces"] = removeNullFields(ifaces)
		}
	}
	return state
}

func requireStateEq(t *testing.T, expected, obtained []byte) {
	var expectedYAMLAsInterface, obtainedYAMLAsInterface map[string]any
	err := yaml.Unmarshal(expected, &expectedYAMLAsInterface)
	require.NoError(t, err, "should success unmarshaling expected value\n%s", expected)

	err = yaml.Unmarshal(obtained, &obtainedYAMLAsInterface)
	require.NoError(t, err, "should success unmarshaling obtained value\n%s", obtained)
	require.Equal(t, normalizeState(expectedYAMLAsInterface),
		normalizeState(obtainedYAMLAsInterface),
		"unmarshaled expected and obtained states should be equal\n---> expected <--- \n%s\n ---> obtained <--- \n%s\n", expected, obtained)
}

func testNetworkState(t *testing.T, expectedState []byte) {
	netState := &NetworkState{}
	err := yaml.UnmarshalStrict(expectedState, netState)
	require.NoError(t, err, "must success unmarshaling the state\n%+v", string(expectedState))
	obtainedState, err := yaml.Marshal(netState)
	require.NoError(t, err, "must success marshaling back the state\n%+v", string(expectedState))

	requireStateEq(t, replaceDeprecatedNames(expectedState), obtainedState)
}

func testUnmarshalDir(t *testing.T, dir string) {
	states := map[string][]byte{}
	err := filepath.Walk(dir, func(path string, info fs.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if info.IsDir() && info.Name() == "policy" {
			return filepath.SkipDir
		}
		if info.IsDir() || filepath.Ext(info.Name()) != ".yml" || strings.Contains(info.Name(), "rollback") {
			return nil
		}
		state, err := os.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed reading state '%s': %w", info.Name(), err)
		}
		states[info.Name()] = state
		return nil
	})
	require.NoError(t, err, "must succeed reading states")
	require.NotEmpty(t, states, "missing test/integration output to test")
	for stateName, expectedState := range states {
		t.Run(stateName, func(t *testing.T) {
			testNetworkState(t, expectedState)
		})
	}
}

func TestAPI(t *testing.T) {
	tests := []struct {
		name, dir string
	}{
		{
			name: "examples",
			dir:  "../../../../../examples",
		},
		{
			name: "integration",
			dir:  "../../../../../tests/integration/.states/",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			testUnmarshalDir(t, tt.dir)
		})
	}
}
