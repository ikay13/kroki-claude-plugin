# Kroki CLI Cheatsheet

The Kroki Go CLI lives at `~/go/bin/kroki`. It POSTs source to the running Kroki gateway and writes the response to a file.

## Common invocations

```bash
# Render plantuml file to SVG (output to <name>.svg in same dir)
~/go/bin/kroki convert diagram.puml --format svg --out-file diagram.svg

# Render with explicit type (extension is ambiguous)
~/go/bin/kroki convert input.txt --type d2 --format svg --out-file out.svg

# Render to PNG
~/go/bin/kroki convert diagram.puml --format png --out-file diagram.png

# Render to PDF
~/go/bin/kroki convert diagram.puml --format pdf --out-file diagram.pdf

# Use a non-default config file (endpoint, timeout, etc. live in YAML)
~/go/bin/kroki convert diagram.puml -c /path/to/kroki.yml --format svg --out-file diagram.svg

# Pipe source from stdin (use --type since there's no extension)
echo '@startuml\nA -> B\n@enduml' | ~/go/bin/kroki convert - --type plantuml --format svg --out-file out.svg
```

## Important flags

| Flag | Effect | Default |
|------|--------|---------|
| `-t, --type <name>` | Diagram language. Gateway accepts ~29; CLI's `--help` lists 25 by name but extras (e.g. `dbml`, `wireviz`, `tikz`) work too. See `skills/kroki/references/languages/` for the full set. | Inferred from file extension. |
| `-f, --format <fmt>` | Output format: `svg`, `png`, `pdf`, `jpeg`, `base64`. | Inferred from `--out-file` extension; otherwise `svg`. |
| `-o, --out-file <path>` | Output destination. Use `-` for stdout. | Inferred from input path; required for stdin input. |
| `-c, --config <file>` | YAML config (endpoint, timeout, headers). The standard config is `~/kroki.yml` and is read automatically — pass `-c` only to use a different file. There is NO `--endpoint` flag — endpoint is set via the config file. | `~/kroki.yml` (or `KROKI_CONFIG` env var). |
| `--help` | Print full flag list. | — |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Render succeeded. |
| `1` | Network/server error or invalid arguments. |
| (other) | Surface stderr — usually contains the gateway's syntax-error response. |

## Type inference

The CLI infers `--type` from extension when the input has one of these:

| Extension | Inferred type |
|-----------|--------------|
| `.puml`, `.plantuml`, `.pu`, `.iuml` | `plantuml` |
| `.dot`, `.gv` | `graphviz` |
| `.mmd`, `.mermaid` | `mermaid` |
| `.d2` | `d2` |
| `.adia` | `actdiag` |
| `.bdia` | `blockdiag` |
| `.ndia` | `nwdiag` |
| `.pdia` | `packetdiag` |
| `.rdia` | `rackdiag` |
| `.sdia` | `seqdiag` |
| `.erd` | `erd` |
| `.nml` | `nomnoml` |
| `.pik` | `pikchr` |
| `.sbob` | `svgbob` |
| `.dbml` | `dbml` |
| `.bpmn` | `bpmn` |

For `.txt`, `.md`, or any extension not listed, you MUST pass `--type` explicitly.

## Plugin wrapper vs raw CLI

Prefer `~/kroki-claude-plugin/scripts/render.sh`. It runs `pod-health.sh` first, writes atomically (temp + mv), and surfaces useful errors. Use raw `~/go/bin/kroki` only when you need a flag the wrapper doesn't pass through (e.g., `-c` to point at a different config file, or to render against a different endpoint by writing a one-off config).

## Upstream docs

- https://github.com/yuzutech/kroki/tree/main/cli
- `~/go/bin/kroki convert --help` for the live flag list on this host.
