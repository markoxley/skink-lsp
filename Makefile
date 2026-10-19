# Makefile for skink-lsp (Language Server Protocol implementation in Skink)
#
# Usage:
#   make          - build the skink-lsp binary
#   make install  - install skink-lsp to $(BINDIR)
#   make run      - run the LSP server (for testing)
#   make clean    - remove build artifacts
#   make help     - show this help message

# Installation directories
PREFIX      ?= /usr/local
BINDIR      ?= $(PREFIX)/bin

# Compiler and tool settings
LSP_BIN     := skink-lsp
FMT_BIN     := skinkfmt
SKINK       ?= skink
# Point SKINK_HOME at the Skink standard library directory (containing std/
# sources and the runtime/ C files). The compiler repo's std/ dir works.
SKINK_HOME  ?= $(abspath ../../skink/std)

# LSP source files
LSP_MAIN    := lsp.skink
FMT_MAIN    := skinkfmt.skink
LSP_MODULES := $(wildcard lsp/*.skink)
VERSION_SK  := version.skink

# Helper: use sudo if not running as root
SUDO        := $(shell if [ `id -u` -ne 0 ]; then echo sudo; fi)

.DEFAULT_GOAL := all

.PHONY: all build install uninstall run clean help

all: build

build: $(LSP_BIN) $(FMT_BIN)

$(LSP_BIN): $(LSP_MAIN) $(LSP_MODULES) $(VERSION_SK)
	@echo "Building skink-lsp..."
	SKINK_HOME=$(SKINK_HOME) $(SKINK) -o $(LSP_BIN) $(LSP_MAIN)
	@echo "Built: $(LSP_BIN)"

$(FMT_BIN): $(FMT_MAIN) $(LSP_MODULES)
	@echo "Building skinkfmt..."
	SKINK_HOME=$(SKINK_HOME) $(SKINK) -o $(FMT_BIN) $(FMT_MAIN)
	@echo "Built: $(FMT_BIN)"

# Type-check only (no codegen, faster)
check:
	@echo "Type-checking skink-lsp..."
	SKINK_HOME=$(SKINK_HOME) $(SKINK) -check $(LSP_MAIN)

# LSP regression tests (drives the built binary over stdio)
test: build
	@echo "Running LSP regression tests..."
	SKINK_LSP=$(abspath $(LSP_BIN)) SKINK_HOME=$(SKINK_HOME) python3 tests/lsp_test.py

install: build
	@echo "Installing skink-lsp and skinkfmt to $(BINDIR)..."
	$(SUDO) install -d $(BINDIR)
	$(SUDO) cp -f $(LSP_BIN) $(FMT_BIN) $(BINDIR)/
	$(SUDO) chmod 755 $(BINDIR)/$(LSP_BIN) $(BINDIR)/$(FMT_BIN)
	@echo "Installation complete: $(BINDIR)/$(LSP_BIN) $(BINDIR)/$(FMT_BIN)"

uninstall:
	@echo "Removing $(BINDIR)/$(LSP_BIN) and $(BINDIR)/$(FMT_BIN)..."
	$(SUDO) rm -f $(BINDIR)/$(LSP_BIN) $(BINDIR)/$(FMT_BIN)
	@echo "Uninstall complete."

run: build
	@echo "Starting skink-lsp (reading from stdin)..."
	./$(LSP_BIN)

clean:
	@echo "Cleaning build artifacts..."
	rm -f $(LSP_BIN) $(FMT_BIN) *.ll *.o

help:
	@echo "Skink-LSP Build System"
	@echo "Targets:"
	@echo "  make          - Build the skink-lsp and skinkfmt binaries"
	@echo "  make skinkfmt - Build only the skinkfmt formatter CLI"
	@echo "  make check    - Type-check only (no codegen)"
	@echo "  make test     - Run LSP regression tests"
	@echo "  make install  - Install to $(BINDIR)"
	@echo "  make uninstall- Remove from $(BINDIR)"
	@echo "  make run      - Build and run the LSP server"
	@echo "  make clean    - Remove build artifacts"
