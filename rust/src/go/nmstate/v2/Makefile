JUNIT_DIR ?= /tmp/
GO_JUNIT_REPORT=$(shell go env GOPATH)/bin/go-junit-report -set-exit-code

check:
	$(eval TMPDIR := $(shell mktemp -d))
	cp $(CLIB_SO_DEV_DEBUG) $(TMPDIR)/$(CLIB_SO_FULL)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_MAN)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_DEV)
	cp $(CLIB_HEADER) $(TMPDIR)/$(shell basename $(CLIB_HEADER))
	LD_LIBRARY_PATH=$(TMPDIR) \
		CGO_CFLAGS="-I$(TMPDIR)" \
		CGO_LDFLAGS="-L$(TMPDIR)" \
		go test -v $(WHAT)
	rm -rf $(TMPDIR)
	go install github.com/jstemmer/go-junit-report/v2@latest
	go test -v 2>&1 | $(GO_JUNIT_REPORT) -set-exit-code -iocopy -out $(JUNIT_DIR)/junit.go-api.xml
generate:
	go generate
lint:
	go run github.com/golangci/golangci-lint/cmd/golangci-lint@v1.52.2 run
