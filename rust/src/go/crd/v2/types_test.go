package v2

import (
	"context"
	"fmt"
	"io/fs"
	"io/ioutil"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"go.uber.org/zap/zapcore"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/envtest"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	"sigs.k8s.io/yaml"
)

const yamlPathKey = "yaml-path"

func testUnmarshalDir(t *testing.T, dir string) ([]ClusterNetworkState, error) {
	states := []ClusterNetworkState{}
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
		state, err := ioutil.ReadFile(path)
		if err != nil {
			return fmt.Errorf("failed reading state '%s': %v", info.Name(), err)
		}
		clusterNetworkState := ClusterNetworkState{
			ObjectMeta: metav1.ObjectMeta{
				Name: strings.ReplaceAll(strings.ReplaceAll(info.Name(), ".", "-"), "_", "-"),
				Annotations: map[string]string{
					yamlPathKey: path,
				},
			},
		}
		err = yaml.Unmarshal(state, &clusterNetworkState.Spec.State)
		if err != nil {
			return err
		}
		states = append(states, clusterNetworkState)
		return nil
	})
	if err != nil {
		return nil, err
	}
	return states, nil
}
func TestCRD(t *testing.T) {
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
	logf.SetLogger(zap.New(zap.Level(zapcore.DebugLevel)))

	t.Log("Installing apiserver and etcd")
	output, err := exec.Command("./setup-testenv.sh").CombinedOutput()
	assert.NoError(t, err, output)

	// specify testEnv configuration
	testEnv := &envtest.Environment{
		BinaryAssetsDirectory: ".k8s/bin", CRDDirectoryPaths: []string{"."},
	}

	t.Log("Starting apiserver and etcd to deploy CRDs")
	cfg, err := testEnv.Start()
	defer func() {
		t.Log("Stoping apiserver and etcd")
		testEnv.Stop()
	}()
	assert.NoError(t, err)

	err = AddToScheme(testEnv.Scheme)
	assert.NoError(t, err)

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			states, err := testUnmarshalDir(t, tt.dir)
			assert.NoError(t, err)

			cli, err := client.New(cfg, client.Options{Scheme: testEnv.Scheme})
			assert.NoError(t, err)

			for _, state := range states {
				t.Run(state.Name, func(t *testing.T) {
					err = cli.Create(context.Background(), &state)
					assert.NoError(t, err, state.Annotations[yamlPathKey])
				})
			}
		})
	}
}
