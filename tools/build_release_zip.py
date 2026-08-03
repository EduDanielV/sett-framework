"""Build a deterministic source ZIP for the current SETT release."""
from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

FIXED_TIMESTAMP = (2026, 7, 29, 0, 0, 0)
EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def included_files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and not any(part in EXCLUDED_PARTS for part in path.parts)
            and path.suffix not in EXCLUDED_SUFFIXES
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def build(root: Path, output: Path) -> None:
    prefix = root.name
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in included_files(root):
            relative = path.relative_to(root).as_posix()
            info = ZipInfo(f"{prefix}/{relative}", FIXED_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


if __name__ == "__main__":
    source_root = Path(__file__).resolve().parents[1]
    destination = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else source_root.parent / "SETT_Framework_v0.11.0_AUDIT.zip"
    )
    build(source_root, destination)
    print(destination)
