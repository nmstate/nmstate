module github.com/nmstate/nmstate/rust/src/go/nmstate/v2

go 1.19

require (
	github.com/nmstate/nmstate/rust/src/go/api/v2 v2.0.8-0.20230718090709-d2bd8c924bd5
	github.com/stretchr/testify v1.8.1
	sigs.k8s.io/yaml v1.3.0
)

require (
	github.com/davecgh/go-spew v1.1.1 // indirect
	github.com/go-logr/logr v1.2.3 // indirect
	github.com/gogo/protobuf v1.3.2 // indirect
	github.com/google/gofuzz v1.1.0 // indirect
	github.com/pmezard/go-difflib v1.0.0 // indirect
	gopkg.in/yaml.v2 v2.4.0 // indirect
	gopkg.in/yaml.v3 v3.0.1 // indirect
	k8s.io/apimachinery v0.27.4 // indirect
	k8s.io/klog/v2 v2.90.1 // indirect
)

replace github.com/nmstate/nmstate/rust/src/go/api/v2 => ../../api/v2
