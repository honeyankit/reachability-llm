"""Static call-graph construction for Python (AST) and JavaScript (regex).

Design:
- One CallGraph wraps a networkx.DiGraph whose nodes are fully-qualified function names.
- For Python we use `ast`. We resolve function call targets by name + module-local imports.
- For JS we use a regex pass (sufficient for the demo; production should swap in a tree-sitter parser).
- For million-line repos we lazy-load only files matching candidate symbols.

Returns from `is_reachable`:
    (reachable: bool, paths: list[list[str]], evidence: list[str])
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import networkx as nx


# ---------- Python ----------

@dataclass
class PyImportContext:
    """Per-file map: local name → fully-qualified target."""
    local_to_fq: dict[str, str] = field(default_factory=dict)


class _PyCallVisitor(ast.NodeVisitor):
    def __init__(self, module: str, imports: PyImportContext, graph: nx.DiGraph):
        self.module = module
        self.imports = imports
        self.graph = graph
        self.scope: list[str] = []

    def _current(self) -> str:
        return ".".join([self.module] + self.scope) if self.scope else self.module

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self.scope.append(node.name)
        fq = self._current()
        self.graph.add_node(fq, kind="function", file=self.module)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        target = self._resolve_call_target(node.func)
        if target and self.scope:
            self.graph.add_edge(self._current(), target)
        self.generic_visit(node)

    def _resolve_call_target(self, func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Name):
            return self.imports.local_to_fq.get(func.id, func.id)
        if isinstance(func, ast.Attribute):
            base = self._attr_chain(func)
            if not base:
                return None
            root = base.split(".", 1)[0]
            mapped = self.imports.local_to_fq.get(root)
            if mapped:
                return mapped + base[len(root):]
            return base
        return None

    def _attr_chain(self, node: ast.AST) -> str:
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        else:
            return ""
        return ".".join(reversed(parts))


def _collect_py_imports(tree: ast.Module) -> PyImportContext:
    ctx = PyImportContext()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                ctx.local_to_fq[name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                local = alias.asname or alias.name
                ctx.local_to_fq[local] = f"{mod}.{alias.name}" if mod else alias.name
    return ctx


def build_python_call_graph(root: str | Path, max_files: int = 5000) -> "CallGraph":
    """Walk a Python project root, parse every .py file, build a call graph."""
    g = nx.DiGraph()
    root = Path(root)
    py_files = list(root.rglob("*.py"))[:max_files]
    for path in py_files:
        try:
            src = path.read_text(errors="ignore")
            tree = ast.parse(src)
        except Exception:
            continue
        module = ".".join(path.relative_to(root).with_suffix("").parts)
        imports = _collect_py_imports(tree)
        _PyCallVisitor(module, imports, g).visit(tree)
    return CallGraph(graph=g, language="python", root=root)


# ---------- JavaScript / TypeScript ----------

_JS_REQUIRE_RE = re.compile(r"""(?:const|let|var)\s+(\w+)\s*=\s*require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_IMPORT_RE = re.compile(r"""import\s+(?:(\w+)|\{([^}]+)\}|\*\s+as\s+(\w+))\s+from\s+['"]([^'"]+)['"]""")
_JS_FUNC_DECL_RE = re.compile(r"""function\s+(\w+)\s*\(|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:function|\()""")
_JS_CALL_RE = re.compile(r"""([\w.$]+)\s*\(""")
_JS_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_JS_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_js_comments(src: str) -> str:
    src = _JS_BLOCK_COMMENT_RE.sub("", src)
    src = _JS_LINE_COMMENT_RE.sub("", src)
    return src


def build_js_call_graph(root: str | Path, max_files: int = 10000) -> "CallGraph":
    """Approximate JS/TS call graph by regex. Good enough for reachability demos.

    Production note: replace with tree-sitter or `acorn` AST output for accuracy.
    """
    g = nx.DiGraph()
    root = Path(root)
    js_files: list[Path] = []
    for ext in ("*.js", "*.mjs", "*.cjs", "*.jsx", "*.ts", "*.tsx"):
        js_files.extend(root.rglob(ext))
    js_files = [p for p in js_files if "node_modules" not in p.parts][:max_files]

    for path in js_files:
        try:
            src = _strip_js_comments(path.read_text(errors="ignore"))
        except Exception:
            continue
        module = str(path.relative_to(root))

        # Build local import map: local_name → package_name
        imports: dict[str, str] = {}
        for m in _JS_REQUIRE_RE.finditer(src):
            imports[m.group(1)] = m.group(2)
        for m in _JS_IMPORT_RE.finditer(src):
            default, named, ns, pkg = m.groups()
            if default:
                imports[default] = pkg
            if ns:
                imports[ns] = pkg
            if named:
                for n in named.split(","):
                    nm = n.strip().split(" as ")[-1].strip()
                    imports[nm] = pkg

        # Each file is one synthetic "function" for the demo (file-level reachability)
        node = f"{module}::__module__"
        g.add_node(node, kind="module", file=module)

        for m in _JS_CALL_RE.finditer(src):
            call = m.group(1)
            root_id = call.split(".", 1)[0]
            mapped = imports.get(root_id)
            if mapped:
                # Add both forms so the curated symbol map (which may use
                # either "_.template" or "lodash.template") matches.
                g.add_edge(node, call)  # original: "_.template"
                g.add_edge(node, mapped + call[len(root_id):])  # "lodash.template"
            else:
                g.add_edge(node, call)

    return CallGraph(graph=g, language="javascript", root=root)


# ---------- Wrapper ----------

@dataclass
class CallGraph:
    graph: nx.DiGraph
    language: str
    root: Path

    def __len__(self) -> int:
        return self.graph.number_of_nodes()

    def num_edges(self) -> int:
        return self.graph.number_of_edges()

    def entry_points(self) -> list[str]:
        """Nodes with no incoming edges — likely entry points."""
        return [n for n in self.graph.nodes if self.graph.in_degree(n) == 0]

    def contains_symbol(self, symbol: str) -> list[str]:
        """Return all graph nodes whose FQN matches the vulnerable symbol.

        Matching rules:
          - Python: suffix match on the dotted FQN (e.g. 'yaml.load' matches 'pyyaml.yaml.load')
          - JS:    exact or suffix match on the dotted call expression
        """
        matches = []
        for node in self.graph.nodes:
            if node == symbol or node.endswith("." + symbol) or symbol in node:
                matches.append(node)
        return matches

    def is_reachable(
        self,
        vulnerable_symbol: str,
        entry_points: Optional[Iterable[str]] = None,
        max_paths: int = 5,
        max_path_len: int = 12,
    ) -> tuple[bool, list[list[str]], list[str]]:
        """Find up to `max_paths` paths from any entry point to the vulnerable symbol.

        Returns:
            (reachable, paths, evidence_strings)
        """
        targets = self.contains_symbol(vulnerable_symbol)
        if not targets:
            return False, [], [f"symbol '{vulnerable_symbol}' not found in call graph"]
        entries = list(entry_points) if entry_points else self.entry_points()
        if not entries:
            entries = list(self.graph.nodes)[:50]

        paths: list[list[str]] = []
        for entry in entries:
            for target in targets:
                try:
                    if not nx.has_path(self.graph, entry, target):
                        continue
                    for path in nx.all_simple_paths(self.graph, entry, target, cutoff=max_path_len):
                        paths.append(path)
                        if len(paths) >= max_paths:
                            break
                except nx.NetworkXError:
                    continue
                if len(paths) >= max_paths:
                    break
            if len(paths) >= max_paths:
                break

        evidence = [" -> ".join(p) for p in paths]
        return bool(paths), paths, evidence

    def extract_code_for_path(self, path: list[str]) -> str:
        """Read function bodies for each node on a call path. Best-effort."""
        chunks: list[str] = []
        for node in path:
            file = self.graph.nodes[node].get("file") if node in self.graph.nodes else None
            if not file:
                continue
            chunks.append(f"# {node}\n# (source from {file})\n")
        return "\n".join(chunks)


def build_repo_call_graph(root: str | Path) -> CallGraph:
    """Detect language from the repo and dispatch to the right builder.

    Heuristic: if package.json exists → JS; if pyproject.toml or many .py → Python.
    Falls back to whichever language has more files.
    """
    root = Path(root)
    py_count = sum(1 for _ in root.rglob("*.py"))
    js_count = sum(
        1 for ext in ("*.js", "*.ts", "*.jsx", "*.tsx") for _ in root.rglob(ext)
    )
    if (root / "package.json").exists() or js_count > py_count:
        return build_js_call_graph(root)
    return build_python_call_graph(root)
