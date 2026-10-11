#!/bin/bash
# Debug wrapper for skink-lsp: logs raw LSP traffic to /tmp for inspection.
# stdin  (client -> server) -> /tmp/lsp_in.log
# stdout (server -> client) -> /tmp/lsp_out.log
# stderr                   -> /tmp/lsp_err.log
tee -a /tmp/lsp_in.log | /home/mark/Documents/GitHub/skink-lsp/skink-lsp "$@" 2>>/tmp/lsp_err.log | tee -a /tmp/lsp_out.log
