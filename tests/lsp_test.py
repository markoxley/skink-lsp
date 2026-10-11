#!/usr/bin/env python3
"""Regression tests for skink-lsp: capabilities, completion, formatting.

Drives the server over stdio with raw JSON-RPC and asserts on responses.
Exits nonzero on the first failing check. Run via 'make test' or:

    SKINK_LSP=./skink-lsp python3 tests/lsp_test.py

Regressions guarded:
  * Completion used the whole trimmed line as the match prefix, so
    'y := New' and 'str.Con' returned zero items.
  * No member completion after '.' (module members, struct fields/
    methods, enum variants, constructor-inferred types).
  * Private members of externally resolved types leaked into completion.
  * Server did not advertise range/on-type formatting providers, so VS
    Code's formatOnSaveMode=modifications, formatOnPaste, formatOnType,
    and Format Selection silently no-oped.
  * The gofmt-style formatter must emit '[]int{', 'chan<int>',
    'a[i-1]', 's[lo+1 : hi-1]', 'if x { stmt }', aligned struct fields
    and const blocks, and preserve string/raw literals verbatim.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKINK_LSP = os.environ.get("SKINK_LSP", os.path.join(HERE, "..", "skink-lsp"))

env = dict(os.environ)
env["SKINK_HOME"] = os.environ.get("SKINK_HOME", "/usr/local/lib/skink/std")

p = subprocess.Popen(
    [SKINK_LSP],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
)

failures = []


def check(name, cond, extra=""):
    tag = "ok " if cond else "FAIL"
    print(f"  [{tag}] {name}{(' — ' + extra) if extra and not cond else ''}")
    if not cond:
        failures.append(name)


def send(obj):
    body = json.dumps(obj).encode()
    p.stdin.write(b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
    p.stdin.flush()


def recv():
    headers = {}
    while True:
        line = p.stdout.readline().strip()
        if not line:
            break
        k, v = line.decode().split(":", 1)
        headers[k.strip()] = v.strip()
    return json.loads(p.stdout.read(int(headers["Content-Length"])))


def request(i, method, params):
    send({"jsonrpc": "2.0", "id": i, "method": method, "params": params})
    while True:
        m = recv()
        if m.get("id") == i:
            return m


def notify(method, params):
    send({"jsonrpc": "2.0", "method": method, "params": params})


workdir = tempfile.mkdtemp(prefix="skink_lsp_test_")

# ---- initialize / capabilities ------------------------------------------
r = request(1, "initialize", {
    "processId": None,
    "rootUri": "file://" + workdir,
    "capabilities": {},
})
caps = (r.get("result") or {}).get("capabilities") or {}
print("== capabilities ==")
check("completion provider present", "completionProvider" in caps)
check("full-document formatting", caps.get("documentFormattingProvider") is True)
check("range formatting", caps.get("documentRangeFormattingProvider") is True)
otf = caps.get("documentOnTypeFormattingProvider") or {}
check("on-type formatting trigger '}'", otf.get("firstTriggerCharacter") == "}")
notify("initialized", {})

# ---- completion ----------------------------------------------------------
DOC = """module main

import "std/str"
import "std/io"

struct Point {
    x: int
    y: int
    pub fn Sum(self: Point) -> int {
        return self.x + self.y
    }
}

enum Color {
    Red
    Green
    Blue
}

fn NewPoint(a: int, b: int) -> Point {
    return Point{x: a, y: b}
}

fn main() {
    p := Point{x: 1, y: 2}
    q := NewPoint(3, 4)
    col := Color.Red
    s := str.NewBuilder(64)
    y := New
    p.
    q.
    str.
    Color.
    s.
}
"""

doc_path = os.path.join(workdir, "test.skink")
with open(doc_path, "w") as f:
    f.write(DOC)
uri = "file://" + doc_path
notify("textDocument/didOpen", {"textDocument": {
    "uri": uri, "languageId": "skink", "version": 1, "text": DOC}})

lines = DOC.split("\n")


def complete(substr, label):
    ln = next(i for i, l in enumerate(lines) if l.strip() == substr)
    ch = len(lines[ln])
    r = request(100 + ln, "textDocument/completion", {
        "textDocument": {"uri": uri},
        "position": {"line": ln, "character": ch}})
    items = r["result"]["items"] if r.get("result") else []
    return [i["label"] for i in items]


print("== completion ==")
labels = complete("y := New", "word after :=")
check("'y := New' offers NewPoint/New/NewBuilder",
      "NewPoint" in labels and "New" in labels and "NewBuilder" in labels,
      str(labels))
labels = complete("p.", "struct instance")
check("'p.' offers x, y, Sum",
      all(m in labels for m in ("x", "y", "Sum")), str(labels))
labels = complete("q.", "ctor-inferred")
check("'q.' offers x, y, Sum",
      all(m in labels for m in ("x", "y", "Sum")), str(labels))
labels = complete("str.", "imported module")
check("'str.' offers module members",
      len(labels) > 5 and "Builder" in labels, str(labels))
labels = complete("Color.", "enum")
check("'Color.' offers variants",
      all(m in labels for m in ("Red", "Green", "Blue")), str(labels))
labels = complete("s.", "str.NewBuilder() inferred")
check("'s.' offers public Builder methods",
      "Write" in labels and "String" in labels, str(labels))
check("'s.' does not leak private 'ensure'", "ensure" not in labels,
      str(labels))

# ---- formatting -----------------------------------------------------------
SLOPPY = """module main

struct Foo {
    x:int
    longerName:string // comment
    y:int // note
}

fn main() {
	x:=1+2*3
	if x<5 { y=x } else { y=0 }


	arr:=[]int{1,2,3}
	m:=map[string]int{"a":1,"bb":2}
	ch:=chan<int>(0)
	a := b < c
	for i:=0;i<10;i=i+1 {
		println(i)
	}
}
"""

EXPECTED = """module main

struct Foo {
    x:          int
    longerName: string // comment
    y:          int    // note
}

fn main() {
    x := 1 + 2 * 3
    if x < 5 { y = x } else { y = 0 }

    arr := []int{1, 2, 3}
    m := map[string]int{"a": 1, "bb": 2}
    ch := chan<int>(0)
    a := b < c
    for i := 0; i < 10; i = i + 1 {
        println(i)
    }
}
"""

fpath = os.path.join(workdir, "fmt.skink")
furi = "file://" + fpath
notify("textDocument/didOpen", {"textDocument": {
    "uri": furi, "languageId": "skink", "version": 1, "text": SLOPPY}})

print("== formatting ==")
r = request(300, "textDocument/formatting", {
    "textDocument": {"uri": furi},
    "options": {"tabSize": 4, "insertSpaces": True}})
edits = r.get("result") or []
check("whole-document format returns edits", len(edits) > 0)
if edits:
    check("whole-document format output", edits[0]["newText"] == EXPECTED,
          "\n" + edits[0]["newText"])

r = request(301, "textDocument/rangeFormatting", {
    "textDocument": {"uri": furi},
    "range": {"start": {"line": 9, "character": 0},
              "end": {"line": 12, "character": 30}},
    "options": {"tabSize": 4, "insertSpaces": True}})
edits = r.get("result") or []
check("range formatting returns edits", len(edits) > 0)
if edits:
    check("range formatting covers the sloppy lines",
          "arr := []int{1, 2, 3}" in edits[0]["newText"],
          "\n" + edits[0]["newText"])

r = request(302, "textDocument/onTypeFormatting", {
    "textDocument": {"uri": furi},
    "position": {"line": 18, "character": 2}, "ch": "}",
    "options": {"tabSize": 4, "insertSpaces": True}})
edits = r.get("result") or []
check("on-type formatting returns edits", len(edits) > 0)

# ---- formatter edge cases --------------------------------------------------
EDGE = """fn f(x:int,y:int)->int{
s:="has {brace} and \\"quotes\\" // not comment"
raw:=`raw {brace} str`
c:=/* inline */5
arr:=[]int{1,2,3}
grid:=[][]int{{1,2},{3,4}}
v:=arr[i - 1]+grid[0][j + 1]
sl:=arr[lo+1:hi-1]
sl2:=arr[1:2]
ch:=make(chan<int>,10)
m:=map[string][]int{"k":arr,"kk":{1,2}}
if x<0{return -x}else if x==0{return 0}else{return x}
cmp:=x<1||x>len(arr)
}
const(
A=1
BBB=2
)
"""

epath = os.path.join(workdir, "edge.skink")
euri = "file://" + epath
notify("textDocument/didOpen", {"textDocument": {
    "uri": euri, "languageId": "skink", "version": 1, "text": EDGE}})
r = request(303, "textDocument/formatting", {
    "textDocument": {"uri": euri},
    "options": {"tabSize": 4, "insertSpaces": True}})
out = (r.get("result") or [{}])[0].get("newText", "")

print("== formatter edge cases ==")
check("string literal preserved",
      '"has {brace} and \\"quotes\\" // not comment"' in out, out)
check("raw string preserved", '`raw {brace} str`' in out, out)
check("[]int{ literal tight", "[]int{1, 2, 3}" in out, out)
check("[][]int nested literal", "[][]int{{1, 2}, {3, 4}}" in out, out)
check("index arithmetic tight", "arr[i-1]" in out and "j+1" in out, out)
check("compound slice colon spaced", "arr[lo+1 : hi-1]" in out, out)
check("simple slice colon tight", "arr[1:2]" in out, out)
check("generic type tight", "chan<int>" in out, out)
check("map generic literal", 'map[string][]int{"k": arr, "kk": {1, 2}}' in out, out)
check("else joined and one-line blocks spaced",
      "else if x == 0 { return 0 } else { return x }" in out, out)
check("comparisons spaced not generic", "x < 1 || x > len(arr)" in out, out)
check("const block '=' aligned", "A   = 1" in out and "BBB = 2" in out, out)
check("no space before block brace", "-> int {" in out, out)

# ---- document open/close lifecycle -----------------------------------------
# Regression: documents.close used to keep the Document entry in the manager
# forever (isOpen=false, text=""). Verify that closing a document removes it
# and that it can be reopened with fresh content.
print("== document lifecycle ==")

LIFECYCLE_SRC = """module main

fn greet() {
    return "hello"
}

fn farewell() {
    return "goodbye"
}

fn main() {
    g := greet()
    f := fare
}
"""

lifecycle_path = os.path.join(workdir, "lifecycle.skink")
with open(lifecycle_path, "w") as f:
    f.write(LIFECYCLE_SRC)
luri = "file://" + lifecycle_path

notify("textDocument/didOpen", {"textDocument": {
    "uri": luri, "languageId": "skink", "version": 1, "text": LIFECYCLE_SRC}})

lr = request(400, "textDocument/completion", {
    "textDocument": {"uri": luri},
    "position": {"line": 13, "character": len("    f := fare")}})
litems = (lr.get("result") or {}).get("items", [])
llabels = [i["label"] for i in litems]
check("open doc offers 'farewell' completion", "farewell" in llabels, str(llabels))

notify("textDocument/didClose", {"textDocument": {"uri": luri}})

lr = request(401, "textDocument/completion", {
    "textDocument": {"uri": luri},
    "position": {"line": 13, "character": len("    f := fare")}})
litems = (lr.get("result") or {}).get("items", [])
check("closed doc returns empty completion", litems == [], str(litems))

REOPEN_SRC = """module main

fn reopened() {
    return "fresh"
}

fn main() {
    r := reo
}
"""

notify("textDocument/didOpen", {"textDocument": {
    "uri": luri, "languageId": "skink", "version": 2, "text": REOPEN_SRC}})

lr = request(402, "textDocument/completion", {
    "textDocument": {"uri": luri},
    "position": {"line": 7, "character": len("    r := reo")}})
litems = (lr.get("result") or {}).get("items", [])
llabels = [i["label"] for i in litems]
check("reopened doc offers new completions", "reopened" in llabels, str(llabels))

# ---- shutdown --------------------------------------------------------------
send({"jsonrpc": "2.0", "method": "exit"})
p.wait(timeout=10)

print()
if failures:
    print(f"FAILED: {len(failures)} check(s)")
    sys.exit(1)
print("all checks passed")
