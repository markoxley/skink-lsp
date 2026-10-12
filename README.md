# skink-lsp

A Language Server Protocol (LSP) implementation for the [Skink](https://github.com/markoxley/skink) programming language, written in Skink itself.

## Features

- **Diagnostics** — Real-time type-checking and error reporting via the in-process resolver and checker
- **Completion** — Keyword, identifier, and snippet completion
- **Hover** — Type information and documentation for symbols
- **Document Symbols** — Outline view of functions, structs, enums, and constants
- **Go-to-Definition** — Jump to symbol definitions within the project
- **Document Highlight** — Highlight occurrences of the symbol under the cursor
- **References** — Find all references to a symbol
- **Formatting** — Basic code formatting (indentation, spacing)
- **Semantic Tokens** — Syntax highlighting via LSP semantic tokens
- **Rename** — Rename symbols across the project

## Building

```bash
make
```

This requires the Skink compiler (`skink`) to be installed and the Skink standard library to be available at `../skink/std` (the `std` directory inside the `skink` compiler repository). Override `SKINK_HOME` if your standard library is elsewhere:

```bash
make SKINK_HOME=/usr/local/lib/skink/std
```

## Installing

```bash
make install
```

This installs the `skink-lsp` binary to `/usr/local/bin/`.

## Editor Configuration

### VS Code

The `skink-vscode` extension (v0.5.0+) bundles LSP support. Configure it in your VS Code settings (`settings.json`):

```json
{
  "skink.lspPath": "/usr/local/bin/skink-lsp",
  "skink.enableLSP": true
}
```

If `skink.lspPath` is not set, the extension will search for `skink-lsp` on your `PATH`.

Or configure it manually in `clients.json` for editors that support LSP:

```json
{
  "languages": {
    "skink": {
      "command": "skink-lsp",
      "rootPatterns": ["Makefile", ".git"],
      "filetypes": ["skink"]
    }
  }
}
```

### Neovim (nvim-lspconfig)

```lua
local lspconfig = require('lspconfig')
lspconfig.skink.setup {
  cmd = { 'skink-lsp' },
  filetypes = { 'skink' },
  root_dir = lspconfig.util.root_pattern('Makefile', '.git'),
}
```

### Vim (coc.nvim)

```json
{
  "languageserver": {
    "skink": {
      "command": "skink-lsp",
      "filetypes": ["skink"],
      "rootPatterns": ["Makefile", ".git"]
    }
  }
}
```

### Emacs (eglot/lsp-mode)

```elisp
(add-to-list 'eglot-server-programs
             '(skink-mode . ("skink-lsp")))
```

## Architecture

```
skink-lsp/
├── Makefile              Build system
├── lsp.skink             Main entry point, server loop, stdio transport
├── version.skink         Version module
└── lsp/
    ├── documents.skink   Text document manager (tracks open files)
    ├── diagnostics.skink Diagnostics provider (uses skink checker)
    ├── completion.skink  Completion provider (keywords, identifiers, snippets)
    ├── symbols.skink     Document symbol provider (uses parser AST)
    ├── hover.skink       Hover provider (type/declaration info)
    ├── definition.skink  Go-to-definition provider
    ├── formatting.skink  Document formatter
    └── utils.skink       Shared helpers (word extraction, ident chars)
```

The LSP communicates over stdio using the standard LSP framing format (`Content-Length: N\r\n\r\n` + JSON body). It uses the Skink standard library's `json` module for JSON-RPC serialization and the `lexer`, `parser`, `resolver`, `checker`, and `ast` modules for language analysis.

## License

MIT
