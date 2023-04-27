JUNIT_DIR ?= /tmp/
GO_JUNIT_REPORT=$(shell go env GOPATH)/bin/go-junit-report -set-exit-code

build-test:
	go install github.com/jstemmer/go-junit-report/v2@latest
	go test -c
check-examples:
	go test -v -run TestAPI/examples 2>&1 |  $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-api.examples.xml
check-integration:
	go test -v -run TestAPI/integration 2>&1 | $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-api.integration.xml
check:
	go test -v 2>&1 | $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-api.xml
generate:
	go generate
lint:
	go run github.com/golangci/golangci-lint/cmd/golangci-lint@v1.52.2 run
