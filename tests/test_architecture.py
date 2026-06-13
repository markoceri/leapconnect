"""Architecture rules for the hexagonal layout.

These tests keep the layering honest as the codebase evolves:

- the domain layer may import only the stdlib and other domain modules;
- the application layer must not import the API layer.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "leapconnect"

STDLIB = set(sys.stdlib_module_names)


def _module_imports(path: Path) -> set[str]:
    """Top-level (non-TYPE_CHECKING) imported root modules of a file."""
    tree = ast.parse(path.read_text())
    imports: set[str] = set()

    def visit(nodes, *, in_type_checking: bool):
        for node in nodes:
            if isinstance(node, ast.Import):
                if not in_type_checking:
                    for alias in node.names:
                        imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if not in_type_checking and node.module and node.level == 0:
                    imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.If):
                # Treat `if TYPE_CHECKING:` blocks as type-only imports.
                test = node.test
                is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                    isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
                )
                visit(node.body, in_type_checking=in_type_checking or is_tc)
                visit(node.orelse, in_type_checking=in_type_checking)
            elif isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                visit(node.body, in_type_checking=in_type_checking)

    visit(tree.body, in_type_checking=False)
    return imports


def _domain_submodule_imports(path: Path) -> set[str]:
    """Second-level imports for leapconnect.* (e.g. 'domain' for domain.x)."""
    tree = ast.parse(path.read_text())
    seconds: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if parts[0] == "leapconnect" and len(parts) > 1:
                seconds.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "leapconnect" and len(parts) > 1:
                    seconds.add(parts[1])
    return seconds


class TestDomainPurity:
    def test_domain_imports_only_stdlib_and_domain(self):
        """Domain modules must not import frameworks or other layers."""
        violations = []
        for path in sorted((PACKAGE / "domain").rglob("*.py")):
            for root in _module_imports(path):
                if root in STDLIB or root == "leapconnect":
                    continue
                violations.append(f"{path.relative_to(ROOT)}: imports '{root}'")
            for second in _domain_submodule_imports(path):
                if second != "domain":
                    violations.append(
                        f"{path.relative_to(ROOT)}: imports leapconnect.{second}"
                    )
        assert not violations, "Domain layer purity violations:\n" + "\n".join(
            violations
        )

    def test_application_does_not_import_api(self):
        """Use cases must not depend on the FastAPI driving adapter."""
        violations = []
        for path in sorted((PACKAGE / "application").rglob("*.py")):
            for second in _domain_submodule_imports(path):
                if second == "api":
                    violations.append(str(path.relative_to(ROOT)))
        assert not violations, "Application layer imports API layer:\n" + "\n".join(
            violations
        )
