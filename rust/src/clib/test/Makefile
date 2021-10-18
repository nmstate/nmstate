TMPDIR := $(shell mktemp -d)
TOP_SRC_DIR:=$(shell dirname $(realpath $(firstword \
	$(MAKEFILE_LIST))))/../../../
DEBUG_NMSTATE_SO_FILE=$(TOP_SRC_DIR)/target/debug/libnmstate.so

include $(TOP_SRC_DIR)/Makefile.inc

CFLAGS =-g -Wall -Wextra -L$(TMPDIR)
LDFLAGS =-I$(TMPDIR)
LIBS =-lnmstate
CC ?=cc

all: check

HEADER_IN = $(TOP_SRC_DIR)/src/clib/nmstate.h.in

nmstate.h: $(HEADER_IN)
	install -p -v -D -m644 $(HEADER_IN) \
		$(TMPDIR)/nmstate.h
	sed -i -e 's/@_VERSION_MAJOR@/$(CLIB_VERSION_MAJOR)/' \
		$(TMPDIR)/nmstate.h
	sed -i -e 's/@_VERSION_MINOR@/$(CLIB_VERSION_MINOR)/' \
		$(TMPDIR)/nmstate.h
	sed -i -e 's/@_VERSION_MICRO@/$(CLIB_VERSION_MICRO)/' \
		$(TMPDIR)/nmstate.h

libnmstate.so: $(DEBUG_NMSTATE_SO_FILE)
	install -p -v -D -m755 $(DEBUG_NMSTATE_SO_FILE) \
		$(TMPDIR)/$(CLIB_SO_FULL)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_MAN)
	ln -sfv $(CLIB_SO_FULL) $(TMPDIR)/$(CLIB_SO_DEV)

nmstate_test: nmstate_test.c nmstate.h libnmstate.so
	$(CC) $(CFLAGS) $(LDFLAGS) -o nmstate_test nmstate_test.c $(LIBS)

check: nmstate_test
	LD_LIBRARY_PATH=$(TMPDIR) \
		valgrind --trace-children=yes --leak-check=full \
		--error-exitcode=1 \
		./nmstate_test 1>/dev/null
	rm -rf $(TMPDIR)

clean:
	rm -f nmstate_test.o nmstate_test
