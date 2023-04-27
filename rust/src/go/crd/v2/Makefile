JUNIT_DIR ?= /tmp/
GO_JUNIT_REPORT=$(shell go env GOPATH)/bin/go-junit-report -set-exit-code

build-test:
	go install github.com/jstemmer/go-junit-report/v2@latest
	go test -c
check-examples:
	go test -v -run TestCRD/examples 2>&1 | $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-crd.examples.xml
check-integration:
	go test -v -run TestCRD/integration 2>&1 | $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-crd.integration.xml
check:
	go test -v 2>&1 | $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-crd.xml
generate:
	go generate
