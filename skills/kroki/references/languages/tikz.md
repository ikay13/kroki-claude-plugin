# TikZ Reference

TikZ is the LaTeX figure-drawing system. Kroki accepts a **complete `\documentclass{standalone}` LaTeX document** containing a `tikzpicture` environment and renders via a containerized LaTeX toolchain. Use for academic figures or anything that must integrate with a LaTeX paper.

**Engine:** Companion container (large image, slow first start)
**File extensions:** `.tex`, `.tikz`
**Kroki type string:** `tikz`

## Basic node-and-arrow

```tex
\documentclass{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning}
\begin{document}
\begin{tikzpicture}[node distance=2cm]
  \node[draw, rectangle] (a) {Input};
  \node[draw, rectangle, right of=a] (b) {Process};
  \node[draw, rectangle, right of=b] (c) {Output};
  \draw[->] (a) -- (b);
  \draw[->] (b) -- (c);
\end{tikzpicture}
\end{document}
```

## With styled nodes

```tex
\documentclass{standalone}
\usepackage{tikz}
\usetikzlibrary{positioning}
\begin{document}
\begin{tikzpicture}[
  block/.style={draw, rectangle, fill=blue!20, minimum width=2cm, minimum height=1cm},
  arrow/.style={->, thick}
]
  \node[block] (a) {Encoder};
  \node[block, right=2cm of a] (b) {Decoder};
  \node[block, below=1cm of a] (loss) {Loss};
  \draw[arrow] (a) -- (b);
  \draw[arrow] (a) -- (loss);
  \draw[arrow] (b) -- (loss);
\end{tikzpicture}
\end{document}
```

## Plot from data

```tex
\documentclass{standalone}
\usepackage{tikz}
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}
\begin{document}
\begin{tikzpicture}
  \begin{axis}[xlabel=$x$, ylabel=$f(x)$, width=8cm, height=5cm]
    \addplot+ coordinates {(0,0) (1,1) (2,4) (3,9) (4,16)};
  \end{axis}
\end{tikzpicture}
\end{document}
```

## Legend Support

**Native** (LaTeX environment). Use `\matrix` or `pgfplots` `\legend{...}` for axis legends. For node-graph legends, draw a labeled box with sample shapes.

## Common Pitfalls

- **A complete LaTeX document is required** — `\documentclass{standalone}`, `\usepackage{tikz}`, `\begin{document}`, `\end{document}`. A bare `tikzpicture` snippet alone produces "! LaTeX Error: Missing \begin{document}." from the gateway.
- The `positioning` library (`\usetikzlibrary{positioning}`) is needed for `right of=`, `right=2cm of`, `below of=`, etc. — without it you get "Unknown operator `o' or `of'".
- First render after pod start is slow (LaTeX compile is multi-second). Subsequent renders are fast.
- pgfplots is bundled; load it with `\usepackage{pgfplots}` plus a `\pgfplotsset{compat=1.18}` declaration for current syntax.
- For other TikZ libraries (e.g. `tikz-cd` for category theory) verify support before relying on it — Kroki bundles a fixed set.
- TikZ errors are LaTeX errors and can be cryptic — start minimal, add complexity gradually.

## Upstream Docs

- https://tikz.dev/
- https://www.ctan.org/pkg/pgf
- https://tikz.dev/tikz-shapes (built-in shape library)
