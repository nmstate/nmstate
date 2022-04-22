ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
VERSION=$(shell cat $(ROOT_DIR)/VERSION)
VERSION_MAJOR=$(shell echo $(VERSION) | cut -f1 -d.)
VERSION_MINOR=$(shell echo $(VERSION) | cut -f2 -d.)
VERSION_MICRO=$(shell echo $(VERSION) | cut -f3 -d.)
GIT_COMMIT=$(shell git rev-parse --short HEAD)
TIMESTAMP=$(shell date +%Y%m%d)
TARBALL=nmstate-$(VERSION)-alpha.$(TIMESTAMP).$(GIT_COMMIT).tar.gz
VENDOR_TARBALL=nmstate-vendor-$(VERSION).$(TIMESTAMP).$(GIT_COMMIT).tar.xz
CLIB_SO_DEV=libnmstate.so
CLIB_SO_MAN=$(CLIB_SO_DEV).$(VERSION_MAJOR)
CLIB_SO_FULL=$(CLIB_SO_DEV).$(VERSION)
RUST_DEBUG_BIN_DIR=./target/debug
RUST_RELEASE_BIN_DIR=./target/release
CLI_EXEC=nmstatectl
CLI_EXEC2=nmstate-autoconf
CLIB_HEADER=rust/src/clib/nmstate.h
CLIB_SO_DEV_RELEASE=rust/target/release/$(CLIB_SO_DEV)
CLIB_SO_DEV_DEBUG=rust/target/debug/$(CLIB_SO_DEV)
CLIB_PKG_CONFIG=rust/src/clib/nmstate.pc
PYTHON_MODULE_NAME=libnmstate
PYTHON_MODULE_SRC=src/python/libnmstate
CLI_EXEC_RELEASE=rust/target/release/$(CLI_EXEC)
PREFIX ?= /usr/local
GO_MODULE_SRC ?= rust/src/go/nmstate
CLI_MANPAGE=doc/nmstatectl.8
CLI_MANPAGE2=doc/nmstate-autoconf.8
SPEC_FILE=packaging/nmstate.spec
RPM_DATA=$(shell date +"%a %b %d %Y")

#outdir is used by COPR as well: https://docs.pagure.org/copr.copr/user_documentation.html
outdir ?= $(ROOT_DIR)

CPU_BITS = $(shell getconf LONG_BIT)
ifeq ($(CPU_BITS), 32)
    LIBDIR ?= $(PREFIX)/lib
else
    LIBDIR ?= $(PREFIX)/lib$(CPU_BITS)
endif

INCLUDE_DIR ?= $(PREFIX)/include
PKG_CONFIG_LIBDIR ?= $(LIBDIR)/pkgconfig
MAN_DIR ?= $(PREFIX)/share/man

SKIP_PYTHON_INSTALL ?=0
SKIP_VENDOR_CREATION ?=0
RELEASE ?=0

PYTHON3_SITE_DIR ?=$(shell \
	python3 -c \
		"from distutils.sysconfig import get_python_lib; \
		 print(get_python_lib())")

$(CLI_EXEC_RELEASE) $(CLIB_SO_DEV_RELEASE):
	cd rust; cargo build --all --release

$(CLIB_SO_DEV_DEBUG):
	cd rust; cargo build --all

.PHONY: $(CLI_MANPAGE)
$(CLI_MANPAGE): $(CLI_MANPAGE).in
	cp $(CLI_MANPAGE).in $(CLI_MANPAGE)
	sed -i -e "s/@DATE@/$(shell date +'%B %d, %Y')/" $(CLI_MANPAGE)
	sed -i -e "s/@VERSION@/$(VERSION)/" $(CLI_MANPAGE)

.PHONY: $(CLI_MANPAGE2)
$(CLI_MANPAGE2): $(CLI_MANPAGE2).in
	cp $(CLI_MANPAGE2).in $(CLI_MANPAGE2)
	sed -i -e "s/@DATE@/$(shell date +'%B %d, %Y')/" $(CLI_MANPAGE2)
	sed -i -e "s/@VERSION@/$(VERSION)/" $(CLI_MANPAGE2)

manpage: $(CLI_MANPAGE) $(CLI_MANPAGE2)
clib: $(CLIB_HEADER) $(CLIB_SO_DEV_RELEASE) $(CLIB_PKG_CONFIG)

.PHONY: $(SPEC_FILE)
$(SPEC_FILE): $(SPEC_FILE).in
	cp $(SPEC_FILE).in $(SPEC_FILE)
	sed -i -e "s/@VERSION@/$(VERSION)/" $(SPEC_FILE)
	if [ $(RELEASE) == 1 ];then \
		sed -i -e "s/@RELEASE@/1/" $(SPEC_FILE); \
	else \
		sed -i -e "s/@RELEASE@/0.alpha.$(TIMESTAMP).$(GIT_COMMIT)/" \
			$(SPEC_FILE);\
		sed -i -e "s|^Source0:.\+|Source0: $(TARBALL)|" $(SPEC_FILE); \
	fi
	sed -i -e "s/@CHANGELOG@/* $(RPM_DATA) N. N. - $(VERSION)-1/" \
		$(SPEC_FILE)

.PHONY: $(CLIB_HEADER)
$(CLIB_HEADER): $(CLIB_HEADER).in
	cp $(CLIB_HEADER).in $(CLIB_HEADER)
	sed -i -e 's/@_VERSION_MAJOR@/$(VERSION_MAJOR)/' \
		$(CLIB_HEADER)
	sed -i -e 's/@_VERSION_MINOR@/$(VERSION_MINOR)/' \
		$(CLIB_HEADER)
	sed -i -e 's/@_VERSION_MICRO@/$(VERSION_MICRO)/' \
		$(CLIB_HEADER)

.PHONY: $(CLIB_PKG_CONFIG)
$(CLIB_PKG_CONFIG): $(CLIB_PKG_CONFIG).in
	cp $(CLIB_PKG_CONFIG).in $(CLIB_PKG_CONFIG)
	sed -i -e 's|@VERSION@|$(VERSION)|' $(CLIB_PKG_CONFIG)
	sed -i -e 's|@PREFIX@|$(PREFIX)|' $(CLIB_PKG_CONFIG)
	sed -i -e 's|@LIBDIR@|$(LIBDIR)|' $(CLIB_PKG_CONFIG)
	sed -i -e 's|@INCLUDE_DIR@|$(INCLUDE_DIR)|' $(CLIB_PKG_CONFIG)

.PHONY: dist
dist: manpage $(SPEC_FILE) $(CLIB_HEADER)
	$(eval TMPDIR := $(shell mktemp -d))
	git archive --prefix=nmstate-$(VERSION)/ --format=tar HEAD | \
		tar x -C $(TMPDIR)
	cp $(CLI_MANPAGE) $(TMPDIR)/nmstate-$(VERSION)/doc/
	cp $(CLI_MANPAGE2) $(TMPDIR)/nmstate-$(VERSION)/doc/
	cp $(SPEC_FILE) $(TMPDIR)/nmstate-$(VERSION)/packaging/
	cp $(CLIB_HEADER) $(TMPDIR)/nmstate-$(VERSION)/rust/src/clib/
	cd $(TMPDIR) && tar cfz $(TARBALL) nmstate-$(VERSION)/
	mv $(TMPDIR)/$(TARBALL) ./
	if [ $(SKIP_VENDOR_CREATION) == 0 ];then \
		cd rust; \
		mkdir $(TMPDIR)/vendor; \
		cargo vendor $(TMPDIR)/vendor; \
		cd $(TMPDIR); \
		find vendor/ -type f -name \*.a  -exec rm {} \; ; \
		tar cfJ $(ROOT_DIR)/$(VENDOR_TARBALL) vendor ; \
	fi
	rm -rf $(TMPDIR)
	echo $(TARBALL)

release: dist
	$(eval NEW_TARBALL=nmstate-$(VERSION).tar.gz)
	if [ $(RELEASE) == 1 ];then \
		mv $(TARBALL) $(NEW_TARBALL); \
		if [ $(SKIP_VENDOR_CREATION) == 0 ];then \
			mv $(VENDOR_TARBALL) \
			$(ROOT_DIR)/nmstate-vendor-$(VERSION).tar.xz; \
		fi; \
		gpg2 --armor --detach-sign $(NEW_TARBALL); \
	else \
		gpg2 --armor --detach-sign $(TARBALL); \
	fi

.PHONY: srpm
srpm: dist
	rpmbuild --define "_srcrpmdir $(outdir)/" -ts $(TARBALL)
	rm -f $(TARBALL)
	rm -f $(VENDOR_TARBALL)

.PHONY: rpm
rpm: dist
	$(eval TMPDIR := $(shell mktemp -d))
	rpmbuild --define "_rpmdir $(TMPDIR)/" -tb $(TARBALL)
	find $(TMPDIR) -type f -exec mv -v {} $(ROOT_DIR) \;
	rm -rf $(TMPDIR)
	rm -f $(TARBALL)
	rm -f $(VENDOR_TARBALL)

.PHONY: clib_check
clib_check: $(CLIB_SO_DEV_DEBUG) $(CLIB_HEADER)
	$(eval TMPDIR := $(shell mktemp -d))
	cp $(CLIB_SO_DEV_DEBUG) $(TMPDIR)/$(CLIB_SO_FULL)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_MAN)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_DEV)
	cp $(CLIB_HEADER) $(TMPDIR)/$(shell basename $(CLIB_HEADER))
	cc -g -Wall -Wextra -L$(TMPDIR) -I$(TMPDIR) -lnmstate \
		-o $(TMPDIR)/nmstate_test rust/src/clib/test/nmstate_test.c
	LD_LIBRARY_PATH=$(TMPDIR) \
		valgrind --trace-children=yes --leak-check=full \
		--error-exitcode=1 \
		$(TMPDIR)/nmstate_test 1>/dev/null
	rm -rf $(TMPDIR)

.PHONY: go_check
go_check: $(CLIB_SO_DEV_DEBUG) $(CLIB_HEADER)
	$(eval TMPDIR := $(shell mktemp -d))
	cp $(CLIB_SO_DEV_DEBUG) $(TMPDIR)/$(CLIB_SO_FULL)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_MAN)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_DEV)
	cp $(CLIB_HEADER) $(TMPDIR)/$(shell basename $(CLIB_HEADER))
	cd rust/src/go/nmstate; LD_LIBRARY_PATH=$(TMPDIR) \
		CGO_CFLAGS="-I$(TMPDIR)" \
		CGO_LDFLAGS="-L$(TMPDIR)" \
		go test $(WHAT)
	rm -rf $(TMPDIR)

rust_check:
	cd rust; cargo test -- --test-threads=1 --show-output;
	if [ "CHK$(CI)" != "CHKtrue" ]; then \
		cd rust; cargo test -- --test-threads=1 \
			--show-output --ignored; \
	fi

check: rust_check clib_check go_check

clean:
	rm -f $(CLI_MANPAGE)
	rm -f $(CLI_MANPAGE2)
	rm -f $(SPEC_FILE)
	rm -f $(TARBALL)
	cd rust && cargo clean || true
	cd rust/src/go/nmstate && go clean || true
	rm -f nmstate-*.tar.gz
	rm -f nmstate-*.tar.xz
	rm -f nmstate-*.tar.gz.asc
	rm -f *nmstate-*.rpm

install: $(CLI_EXEC_RELEASE) manpage clib
	install -p -v -D -m755 $(CLI_EXEC_RELEASE) \
		$(DESTDIR)$(PREFIX)/bin/$(CLI_EXEC)
	ln -sfv $(CLI_EXEC) $(DESTDIR)$(PREFIX)/bin/$(CLI_EXEC2)
	install -p -D -m755 $(CLIB_SO_DEV_RELEASE) \
		$(DESTDIR)$(LIBDIR)/$(CLIB_SO_FULL)
	ln -sfv $(CLIB_SO_FULL) $(DESTDIR)$(LIBDIR)/$(CLIB_SO_MAN)
	ln -sfv $(CLIB_SO_FULL) $(DESTDIR)$(LIBDIR)/$(CLIB_SO_DEV)
	if [ $(SKIP_PYTHON_INSTALL) != 1 ];then \
		cd rust/src/python; python3 setup.py install; \
	fi
	install -p -v -D -m644 $(CLIB_HEADER) \
		$(DESTDIR)$(INCLUDE_DIR)/$(shell basename $(CLIB_HEADER))
	install -p -v -D -m644 $(CLIB_PKG_CONFIG) \
		$(DESTDIR)$(PKG_CONFIG_LIBDIR)/$(shell basename $(CLIB_PKG_CONFIG))
	install -p -v -D -m644 $(CLI_MANPAGE) \
		$(DESTDIR)$(MAN_DIR)/man8/$(shell basename $(CLI_MANPAGE))
	gzip $(DESTDIR)$(MAN_DIR)/man8/$(shell basename $(CLI_MANPAGE))
	install -p -v -D -m644 $(CLI_MANPAGE2) \
		$(DESTDIR)$(MAN_DIR)/man8/$(shell basename $(CLI_MANPAGE2))
	gzip $(DESTDIR)$(MAN_DIR)/man8/$(shell basename $(CLI_MANPAGE2))


uninstall:
	- rm -fv $(DESTDIR)$(PREFIX)/bin/$(CLI_EXEC)
	- rm -fv $(DESTDIR)$(PREFIX)/bin/$(CLI_EXEC2)
	- rm -fv $(DESTDIR)$(LIBDIR)/$(CLIB_SO_DEV)
	- rm -fv $(DESTDIR)$(LIBDIR)/$(CLIB_SO_MAN)
	- rm -fv $(DESTDIR)$(LIBDIR)/$(CLIB_SO_FULL)
	- rm -fv $(DESTDIR)$(INCLUDE_DIR)/$(shell basename $(CLIB_HEADER))
	- rm -fv $(DESTDIR)$(INCLUDE_DIR)/$(shell basename $(CLIB_PKG_CONFIG))
	- rm -fv $(DESTDIR)$(MAN_DIR)/man8/$(shell basename $(CLI_MANPAGE))
	- rm -fv $(DESTDIR)$(MAN_DIR)/man8/$(shell basename $(CLI_MANPAGE2))
	- if [ $(SKIP_PYTHON_INSTALL) != 1 ];then \
		rm -rfv $(DESTDIR)$(PYTHON3_SITE_DIR)/$(PYTHON_MODULE_NAME); \
	fi
