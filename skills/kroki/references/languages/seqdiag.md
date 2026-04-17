# seqdiag Reference

seqdiag is the BlockDiag-family sequence-diagram DSL — terser than PlantUML, no async/alt/loop primitives. Good for short, linear interactions.

**Engine:** Companion container (`kroki-blockdiag`)
**File extensions:** `.sdia`
**Kroki type string:** `seqdiag`

## Basic interaction

```seqdiag
seqdiag {
  browser  -> webserver [label = "GET /index.html"];
  browser <-- webserver;
  browser  -> webserver [label = "POST /blog/comment"];
  webserver  -> database [label = "INSERT comment"];
  webserver <-- database;
  browser <-- webserver;
}
```

## With note

```seqdiag
seqdiag {
  user -> auth_service [label = "POST /login"];
  auth_service -> database [label = "SELECT user"];
  auth_service <-- database;
  auth_service -> token_store [label = "STORE session"];
  user <-- auth_service [label = "200 + token", note = "JWT, 1h TTL"];
}
```

## Legend Support

**Stitch required.** No native legend syntax.

## Common Pitfalls

- Wrapper keyword `seqdiag` is required.
- Arrows: `->` (sync request), `-->` (sync response), `<-` and `<--` reverse the direction.
- No native support for activation bars, alt, opt, loop, par — use PlantUML if you need any of those.
- Notes attach via `note = "..."` on the edge.

## Upstream Docs

- http://blockdiag.com/en/seqdiag/
