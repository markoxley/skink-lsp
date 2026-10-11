# Compiler bugs found via skink-lsp

**Status (Sep 18, repo build `~/Documents/GitHub/skink`):** all four
compiler issues verified FIXED — function-body locals released (body
now emitted inside its own scope), owned expression temporaries
scope-tracked and released, return-value retain/release balanced
(callers consistently own +1), and private cross-module name
collisions resolved (module-qualified lookup prefers own module).
Runtime check: `Skink_rc_live_objects()` returns to baseline across
all three leak scenarios. skink-lsp builds and serves with the
fixed compiler.

Discovered while investigating a memory leak in skink-lsp (2026-09-17).
Measured on the running server: ~6KB RSS per incoming message on the
no-op path, ~19KB of live RC objects per `diagnostics.check` call
(lexer+resolver+checker pipeline), ~1.4MB RSS per `didChange`
notification, ~1.6MB per `completion` request. The server is unusable
for long sessions; every code path leaks.

## 1. Function-body top-level locals are never released

- **Severity:** critical — leaks memory in every function of every
  program.
- **Symptom:** a variable declared at the top level of a function body
  (`s := str.Concat("a", "b")`) is still live per
  `Skink_rc_live_objects()` after the function returns.
- **Root cause:** `emitFnDecl` (std/emitter.skink ~11480) resets
  `cg.scopeVars` to a single scope at depth 0, registers parameters there
  (marked `borrowed`), then emits the body with `emitBlockStmtRaw` —
  **without `pushScope`**. Body locals therefore land in scope 0.
  `emitAllDeallocations` (~1223) intentionally skips scope 0
  ("parameters are borrowed"), so all top-level locals leak on every
  return path (explicit `return`, named returns, fall-through, and the
  error-propagation label).
- **Expected:** body should be emitted inside its own scope so locals
  land in scope >= 1 and are released by `emitAllDeallocations` at each
  exit point. Named-return slots registered before the push stay in
  scope 0, which is correct (their values are moved to the caller).
- **Verified via IR:** `fn f() { s := str.Concat("a","b"); io.PrintLine(s) }`
  emits `ret void` with zero `Skink_rc_release` calls.
- **Risk when fixing:** releasing previously-leaked locals can expose
  missing retains elsewhere (e.g. values stored into globals/structs
  without retain become dangling). Needs a full `run_tests.sh` pass plus
  ASan runs.

## 2. Expression temporaries are never released

- **Severity:** high.
- **Symptom:** `io.PrintLine(str.Concat("a", "b"))` leaks the concat
  result — it is an SSA register never stored in a variable, so no
  `Skink_rc_release` is ever emitted for it.
- **Root cause:** the emitter has no tracking for heap-typed temporaries
  produced inside expressions (call results, `str.Concat` chains,
  `json.MarshalValue`, etc.) that are consumed directly as call args or
  operands. Only named variables are scope-tracked.
- **Expected:** heap temporaries should be released after the enclosing
  statement completes (or the callee should consume the reference —
  but parameters are currently borrowed, so release must happen
  caller-side after the call).

## 3. Return-value retain/release imbalance

- **Severity:** high.
- **Symptom:** `fn mk() -> string { r := str.Concat("a","b"); return r }`
  called in a loop leaks the returned string once per call even though
  the caller's variable is released per iteration (verified in IR).
- **Root cause:** return paths emit `Skink_rc_retain` on the returned
  heap value (e.g. `io.Sprintf1`: `%r61 = call i8* @Skink_rc_retain(i8*
  %r60)` before `ret`), but caller-side storage of the result is
  inconsistent — `s := str.Concat(...)` in a loop body stores the call
  result with **no** retain, while other call-result stores do retain.
  The extra reference from the callee's retain is never released.
- **Expected:** a single ownership convention — either the callee
  returns a +0 reference (no retain on return; callee's local release is
  skipped for the returned value) or returns +1 with every caller store
  consistently non-retaining.

## 4. Private function names collide across modules

- **Severity:** medium.
- **Symptom:** compiling a program whose `main` module defines
  `fn report(tag: string)` (1 arg) produced hundreds of
  "wrong number of arguments: expected 1, got 2" errors *inside*
  `std/checker.skink`, which calls its own private `report(c, msg)`
  (2 args). Renaming the main-module function fixed the build.
- **Root cause:** unqualified function resolution in a module appears to
  search a global scope polluted by other modules' private functions.
- **Expected:** unqualified names resolve to the current module's own
  declarations first; private symbols of other modules must not be
  visible.
- **Workaround:** avoid naming functions `report` (and presumably other
  common names used privately in std) in user code.

## Application-level notes (skink-lsp itself)

- `readMessage` in lsp.skink leaked `ch` (a 1-byte `libc.malloc` plus its
  RC-registry entry) per message — fixed by freeing it after the header
  loop.
- The outdated comments in `lsp/documents.skink` /
  `lsp/diagnostics.skink` claiming `libc.free` on an RC string "corrupts
  the heap" are wrong for the current runtime: `Skink_mem_free`
  dispatches on the pointer registry and performs a proper RC release.
  The real danger is *premature* release if the compiler also releases
  the same variable at scope exit.
- ✅ FIXED: `documents.close` now rebuilds `dm.docs` without the closed
  document so the `Document` struct and its URI string are released instead
  of accumulating for the lifetime of the server. Regression test added in
  `tests/lsp_test.py` (document lifecycle open/close/reopen checks).
- ✅ FIXED (skink-vscode): the test controller's `runAll()`/`runFile()`
  created `vscode.CancellationTokenSource` instances and never disposed them,
  and `runTestFile()` registered a cancellation listener without disposing
  it. Each test run leaked the source plus the listener. Both leaks are now
  fixed and a regression test was added in
  `skink-vscode/src/extension.controller.test.ts`.
