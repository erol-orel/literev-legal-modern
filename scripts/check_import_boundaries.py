from __future__ import annotations

import ast
import sys

from pathlib import Path

FORBIDDEN_ROOTS = {
    "django",
    "rest_framework",
    "asgiref",
    "django_stubs_ext",
    "literev",
    "config",
}


def iter_library_source_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "libs").glob("*/src/**/*.py"))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    offending_imports: list[str] = []
    for path in iter_library_source_files(repo_root):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                root = module.split(".")[0]
                if root in FORBIDDEN_ROOTS:
                    offending_imports.append(
                        f"{path.relative_to(repo_root)} -> {module}"
                    )
    if offending_imports:
        for entry in offending_imports:
            print(entry)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
