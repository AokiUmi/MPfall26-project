"""Conservative AST inspection. Never imports or executes inspected code."""

import ast
from pathlib import Path


SCHEMA_VERSION = "1.0"
PATCH = {"unittest.mock.patch", "mock.patch"}
MOCKER_FIXTURES = {"mocker", "class_mocker", "module_mocker", "package_mocker", "session_mocker"}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return parent + "." + node.attr if parent else None
    return None


def qualify(name, aliases):
    if not name:
        return None
    first, *rest = name.split(".")
    return ".".join([aliases.get(first, first)] + rest)


def imports(tree, module=None):
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                result[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level and module:
                parts = module.split(".")[:-node.level]
                base = ".".join(parts + ([base] if base else []))
            elif node.level:
                continue
            for alias in node.names:
                if alias.name != "*":
                    result[alias.asname or alias.name] = ".".join(filter(None, [base, alias.name]))
    return result


def source_index(root):
    """Map importable module names to ASTs; source root is the import root."""
    index = {}
    if root is None:
        return index
    for path in sorted(Path(root).rglob("*.py")):
        if any(p.startswith(".") or p in {"__pycache__", "venv", "node_modules"} for p in path.relative_to(root).parts):
            continue
        parts = list(path.relative_to(root).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if not parts:
            continue
        try:
            index[".".join(parts)] = ast.parse(path.read_bytes(), filename=str(path))
        except (SyntaxError, ValueError):
            continue
    return index


def canonical(target, index):
    """Follow explicit import bindings, including where-used patch locations."""
    seen = set()
    while target and target not in seen:
        seen.add(target)
        parts = target.split(".")
        replacement = target
        for cut in range(len(parts) - 1, 0, -1):
            module = ".".join(parts[:cut])
            if module in index:
                aliases = imports(index[module], module)
                suffix = ".".join(parts[cut:])
                replacement = qualify(suffix, aliases)
                if replacement == suffix:
                    replacement = target
                break
        if replacement == target:
            break
        target = replacement
    return target


def analyze(path, targets=(), source_root=None, boundaries=()):
    """Return all patch instances. Only OM001 claims a direct target match.

    boundaries are explicit user-supplied dotted prefixes, never guessed from
    package names. Unknown and boundary instances remain in the output.
    """
    path = Path(path)
    tree = ast.parse(path.read_bytes(), filename=str(path))
    index = source_index(source_root)
    normalized_targets = {canonical(t, index) for t in targets}
    findings = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.scopes = [imports(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))], type_ignores=[]))]
            self.context = []
            self.fixtures = set()

        def visit_ClassDef(self, node):
            self.context.append(node.name)
            self.generic_visit(node)
            self.context.pop()

        def visit_FunctionDef(self, node):
            previous = self.fixtures
            self.fixtures = previous | ({a.arg for a in node.args.args + node.args.kwonlyargs} & MOCKER_FIXTURES)
            # Function imports apply throughout its body; control flow is not evaluated.
            self.scopes.append({**self.scopes[-1], **imports(node)})
            self.context.append(node.name)
            self.generic_visit(node)
            self.context.pop()
            self.scopes.pop()
            self.fixtures = previous

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node):
            raw = dotted(node.func)
            resolved = qualify(raw, self.scopes[-1])
            is_mocker = raw and raw.split(".")[0] in self.fixtures
            kind = None
            if resolved in PATCH or (is_mocker and raw.endswith(".patch") and raw.count(".") == 1):
                kind = "patch"
            elif resolved in {p + ".object" for p in PATCH} or (is_mocker and raw.endswith(".patch.object") and raw.count(".") == 2):
                kind = "object"
            elif resolved in {p + ".multiple" for p in PATCH} or (is_mocker and raw.endswith(".patch.multiple") and raw.count(".") == 2):
                kind = "multiple"
            elif resolved in {p + ".dict" for p in PATCH} or (is_mocker and raw.endswith(".patch.dict") and raw.count(".") == 2):
                kind = "dict"
            if kind:
                kwargs = {k.arg: k.value for k in node.keywords if k.arg}
                first = node.args[0] if node.args else kwargs.get("target" if kind != "dict" else "in_dict")
                literal = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
                if kind in {"patch", "dict"}:
                    candidates = [literal]
                else:
                    base = literal if kind == "multiple" else None
                    base = base or qualify(dotted(first), self.scopes[-1])
                    # A local variable is not an import-resolved object.
                    if not literal and (not dotted(first) or dotted(first).split(".")[0] not in self.scopes[-1]):
                        base = None
                    if kind == "object":
                        attr = node.args[1] if len(node.args) > 1 else kwargs.get("attribute")
                        attr = attr.value if isinstance(attr, ast.Constant) and isinstance(attr.value, str) else None
                        candidates = [base + "." + attr if base and attr else None]
                    else:
                        controls = {"spec", "create", "spec_set", "autospec", "new_callable"}
                        candidates = [base + "." + name if base else None for name in kwargs if name not in controls]
                        if any(k.arg is None for k in node.keywords) or not candidates:
                            candidates.append(None)
                for target in candidates:
                    self.record(node, kind, target)
            self.generic_visit(node)

        def record(self, node, kind, target):
            actual = canonical(target, index)
            if actual and actual in normalized_targets and kind != "dict":
                rule, status, severity = "OM001", "warning", "high"
                reason = "The declared function under test is replaced; assertions may only verify the configured mock."
                suggestion = "Call the real function under test and mock only necessary external interactions."
            elif target and any(target == b or target.startswith(b + ".") or actual == b or actual.startswith(b + ".") for b in boundaries):
                rule, status, severity = "BOUNDARY", "allowed", "info"
                reason = "Target matches an explicitly configured boundary prefix."
                suggestion = "Check that assertions still exercise the intended application logic."
            elif kind == "dict":
                rule, status, severity = "STATE_PATCH", "review", "info"
                reason = "Dictionary state is patched; this does not directly replace a callable."
                suggestion = "Review whether the patched state is appropriate for this test."
            elif actual and any(actual == m or actual.startswith(m + ".") for m in index):
                rule, status, severity = "OM002", "review", "medium"
                reason = "A project-internal target is mocked; static analysis cannot establish whether bypassing it is harmful."
                suggestion = "Review whether this helper contains logic the test should exercise; retain legitimate boundary mocks."
            else:
                rule, status, severity = "UNRESOLVED", "unknown", "info"
                reason = "Target is dynamic or its role cannot be established from the supplied source and configuration."
                suggestion = "Supply the source import root and target metadata, or review this instance manually."
            findings.append(dict(file=str(path), line=node.lineno, column=node.col_offset + 1,
                                 test=".".join(self.context) or None, syntax=kind, target=target,
                                 resolved_target=actual, rule_id=rule, status=status, severity=severity,
                                 message=reason, suggestion=suggestion))

    Visitor().visit(tree)
    return sorted(findings, key=lambda f: (f["line"], f["column"], f["target"] or ""))
