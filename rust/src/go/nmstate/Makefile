# This Makefile is handling the go build, install, test and clean. It is needed
# to avoid isues with the GOROOT and GOPATH.

TOP_SRC_DIR:=$(shell dirname $(realpath $(firstword \
	$(MAKEFILE_LIST))))/../../../

all: build check install

build:
	go build;

check: TMPDIR:=$(shell mktemp -d)
check:
	DESTDIR=$(TMPDIR) make -C $(TOP_SRC_DIR) install
	sudo RUST_LOG=info \
		LD_LIBRARY_PATH=$(TMPDIR)/usr/local/lib64 \
		CGO_CFLAGS="-I$(TMPDIR)/usr/local/include" \
		CGO_LDFLAGS="-L$(TMPDIR)/usr/local/lib64" \
		go test $(WHAT);
	rm -rf $(TMPDIR)
clean:
	go clean;
