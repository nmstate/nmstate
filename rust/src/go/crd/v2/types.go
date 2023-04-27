//go:generate ./controller-gen.sh object:headerFile="boilerplate.go.txt" paths="."
//go:generate ./controller-gen.sh crd paths="." output:crd:artifacts:config=.
package v2

import (
	nmstate "github.com/nmstate/nmstate/rust/src/go/api/v2"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// +genclient
// +kubebuilder:object:root=true
// +kubebuilder:resource:path=clusternetworkstate,shortName=cns,scope=Cluster
// +kubebuilder:storageversion

// ClusterNetworkState is the Schema for the nodenetworkconfigurationpolicies API
type ClusterNetworkState struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec ClusterNetworkStateSpec `json:"spec,omitempty"`
}

// +k8s:deepcopy-gen=true
type ClusterNetworkStateSpec struct {
	State nmstate.NetworkState `json:"state,omitempty"`
}

// +kubebuilder:object:root=true

type ClusterNetworkStateList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ClusterNetworkState `json:"items"`
}

func init() {
	SchemeBuilder.Register(&ClusterNetworkState{}, &ClusterNetworkStateList{})
}
