"""A minimal working pkg-config implementation + `.pc` prefix relocation.

Why it is needed: the `.pc` files inside HarmonyOS prebuilt artifacts (Harmonybrew bottle /
cmd-pkgs tarball) contain **absolute paths from the machine that built the artifact**, e.g.

    prefix=/storage/Users/currentUser/.harmonybrew/Cellar/opus/1.6.1_1

A Windows host has no pkg-config (CMake's `pkg_check_modules` fails outright), and even if
one is installed, these absolute paths do not exist. Measured (tdesktop 7.4.4, second review
round D-09): many of the 377 `.pc` files have cross-package references such as
`-L.../Cellar/libvpx/1.17.0_2/lib`, all of them broken.

This module does two things, each callable on its own:

1. `relocate_tree()`: rewrites the absolute paths of every `.pc` under `ohos-libs/` to their
   actual local locations (the package root is derived from the `.pc`'s directory; cross-package
   references are resolved by directory name to the same-named package under the local
   `ohos-libs/`). Idempotent, safe to re-run.
2. `main()`: implements the common pkg-config queries (`--cflags` / `--libs` /
   `--modversion` / `--exists` / `--variable=` / `--list-all`), recursively expands
   `Requires` / `Requires.private`, and always outputs forward slashes - used as
   `pkg-config` for CMake on Windows.

Usage (as a pkg-config stand-in):

    python tools/qt_ohos/pkgconfig.py --cflags --libs opus
    python tools/qt_ohos/pkgconfig.py --relocate ohos-libs   # relocate
    python tools/qt_ohos/pkgconfig.py --write-shim .qt-ohos/bin \\
        --libdir ohos-libs

Environment variable: `PKG_CONFIG_LIBDIR` (replaces the default search path; separate multiple entries with `os.pathsep`).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

_VAR_RE = re.compile(r"\$\{([^}]+)\}")
_ASSIGN_RE = re.compile(r"^(\w+)\s*=\s*(.*)$")
_FIELD_RE = re.compile(r"^([A-Za-z0-9_.]+)\s*:\s*(.*)$")
_ABS_PATH_RE = re.compile(r"(?<![\w.-])(/[^\s;:]+)")


def _split_list(text: str) -> List[str]:
    return [t for t in re.split(r"\s+", (text or "").strip()) if t]


def _expand(value: str, variables: Dict[str, str], depth: int = 0) -> str:
    """Expand `${var}`; unknown variables are kept as-is (pkg-config behavior)."""
    if depth > 8 or "${" not in value:
        return value

    def repl(m):
        key = m.group(1)
        if key in variables:
            return _expand(variables[key], variables, depth + 1)
        return m.group(0)

    return _VAR_RE.sub(repl, value)


def parse_pc(text: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Parse `.pc` text -> (variables, fields); variables are already expanded."""
    raw_vars: Dict[str, str] = {}
    fields: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _ASSIGN_RE.match(line)
        if m and ":" not in m.group(1):
            raw_vars[m.group(1)] = m.group(2).strip()
            continue
        m = _FIELD_RE.match(line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    variables: Dict[str, str] = {}
    # variables may reference each other: expand twice in order of appearance to cover "used before defined"
    for _ in range(2):
        for key, val in raw_vars.items():
            variables[key] = _expand(val, {**raw_vars, **variables})
    return variables, fields


def read_pc(path: Path) -> Dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    variables, fields = parse_pc(text)
    return {
        "path": str(path),
        "name": fields.get("Name") or path.stem,
        "version": fields.get("Version") or "",
        "variables": variables,
        "requires": _split_list(fields.get("Requires")),
        "requires_private": _split_list(fields.get("Requires.private")),
        "libs": _split_list(_expand(fields.get("Libs", ""), variables)),
        "libs_private": _split_list(
            _expand(fields.get("Libs.private", ""), variables)),
        "cflags": _split_list(_expand(fields.get("Cflags", ""), variables)),
        "conflicts": _split_list(fields.get("Conflicts")),
    }


def search_dirs(libdir: Optional[Path] = None) -> List[Path]:
    if libdir is None:
        env = os.environ.get("PKG_CONFIG_LIBDIR") or os.environ.get(
            "PKG_CONFIG_PATH")
        if env:
            return [Path(p) for p in env.split(os.pathsep) if p.strip()]
        return []
    libdir = Path(libdir)
    dirs = [libdir / "lib" / "pkgconfig", libdir / "lib64" / "pkgconfig",
            libdir / "share" / "pkgconfig"]
    # ohos-libs/<pkg>/<ver>/lib/pkgconfig: expand per package
    if libdir.is_dir():
        for pkg in sorted(libdir.iterdir()):
            if not pkg.is_dir():
                continue
            dirs.extend(sorted(pkg.glob("*/lib/pkgconfig")))
            dirs.extend(sorted(pkg.glob("*/*/lib/pkgconfig")))
    return [d for d in dirs if d.is_dir()]


def build_index(dirs: Iterable[Path]) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    for d in dirs:
        for pc in sorted(Path(d).glob("*.pc")):
            index.setdefault(pc.stem, pc)
    return index


def _pkg_root(pc_path: Path) -> Path:
    """Package root of a `.pc`: `<root>/lib/pkgconfig/foo.pc` -> `<root>`."""
    parent = pc_path.parent
    if parent.name == "pkgconfig":
        libdir = parent.parent
        if libdir.name in ("lib", "lib64", "share"):
            return libdir.parent
        return libdir
    return parent


def _real_local_dirs(libs_dir: Path) -> Dict[str, Path]:
    """Package directories under the local `ohos-libs/`: directory name -> version directory (the first one)."""
    out: Dict[str, Path] = {}
    libs_dir = Path(libs_dir)
    if not libs_dir.is_dir():
        return out
    for pkg in libs_dir.iterdir():
        if not pkg.is_dir():
            continue
        for ver in sorted(pkg.iterdir()):
            if ver.is_dir():
                out[pkg.name.lower()] = ver
                break
    return out


def _rewrite_path(token: str, root: Path, local_dirs: Dict[str, Path]) -> str:
    """Rewrite an absolute path from the artifact build machine to the local machine.

    - exists -> unchanged
    - `<...>/Cellar/<pkg>/<ver>/lib` and a same-named local package exists -> local `<pkg>/<ver>/lib`
    - otherwise -> join onto the package root (relative segments such as `lib`/`include`)
    """
    if not token.startswith("/"):
        return token
    if Path(token).exists():
        return token
    parts = [p for p in token.split("/") if p]
    for i, seg in enumerate(parts[:-1]):
        key = seg.lower()
        if key in local_dirs:
            tail = parts[i + 1:]
            cand = local_dirs[key]
            for j in range(len(tail)):
                probe = cand.joinpath(*tail[j:])
                if probe.exists():
                    return probe.as_posix()
            return cand.as_posix()
    # fallback: keep relative tail segments such as lib/include
    for i, seg in enumerate(parts):
        if seg in ("lib", "lib64", "include", "share", "bin"):
            return root.joinpath(*parts[i:]).as_posix()
    return root.as_posix()


def _rewrite_value(value: str, root: Path, local_dirs: Dict[str, Path],
                   notes: List[str], label: str) -> str:
    """Rewrite the absolute paths in a line, token by token.

    Only paths that "look like a build-machine prefix" (>= 3 segments) are handled; relative
    forms such as `${prefix}/lib` are kept as-is - they get rewritten along with `prefix=`.
    """
    out: List[str] = []
    for tok in value.split():
        prefix, path = "", tok
        m = re.match(r"^(-[LI])(/.*)$", tok)
        if m:
            prefix, path = m.group(1), m.group(2)
        elif not tok.startswith("/"):
            out.append(tok)
            continue
        if path.count("/") < 3:
            out.append(tok)          # /lib, /include and the like
            continue
        tail = "/" if path.endswith("/") else ""
        new_path = _rewrite_path(path.rstrip("/"), root, local_dirs) + tail
        if new_path != path:
            notes.append("%s: %s -> %s" % (label, path, new_path))
        out.append(prefix + new_path)
    return " ".join(out)


def relocate_text(text: str, pc_path: Path,
                  local_dirs: Optional[Dict[str, Path]] = None) -> Tuple[str, List[str]]:
    """Rewrite the absolute paths of one `.pc`; returns (new text, change notes)."""
    local_dirs = local_dirs or {}
    root = _pkg_root(pc_path)
    notes: List[str] = []
    out_lines: List[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        if "=" in line and ":" not in line.split("=", 1)[0]:
            key, sep, val = line.partition("=")
            lead = val[:len(val) - len(val.lstrip())]
            new_val = _rewrite_value(val.lstrip(), root, local_dirs, notes,
                                     key.strip())
            out_lines.append("%s%s%s%s" % (key, sep, lead, new_val))
        elif ":" in line:
            field, sep, val = line.partition(":")
            lead = val[:len(val) - len(val.lstrip())]
            new_val = _rewrite_value(val.lstrip(), root, local_dirs, notes,
                                     field.strip())
            out_lines.append("%s%s%s%s" % (field, sep, lead, new_val))
        else:
            out_lines.append(line)
    new_text = "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")
    return new_text, notes


def relocate_tree(libs_dir: Path, dry_run: bool = False) -> Dict:
    """Relocate every `.pc` under `ohos-libs/`. Returns statistics and per-file changes."""
    libs_dir = Path(libs_dir)
    local_dirs = _real_local_dirs(libs_dir)
    changed: List[Dict] = []
    scanned = 0
    for d in search_dirs(libs_dir):
        for pc in sorted(d.glob("*.pc")):
            scanned += 1
            text = pc.read_text(encoding="utf-8", errors="replace")
            new_text, notes = relocate_text(text, pc, local_dirs)
            if not notes or new_text == text:
                continue
            changed.append({"path": pc.relative_to(libs_dir).as_posix()
                            if libs_dir in pc.parents else str(pc),
                            "notes": notes})
            if not dry_run:
                pc.write_text(new_text, encoding="utf-8")
    return {"scanned": scanned, "changed": changed,
            "local_packages": sorted(local_dirs)}


def _resolve_pkg(name: str, index: Dict[str, Path],
                 seen: Optional[set] = None, private: bool = False) -> Dict:
    """Recursively resolve packages and their Requires (including Requires.private; private ones are used for cflags only)."""
    seen = seen or set()
    if name in seen:
        return {"cflags": [], "libs": []}
    seen.add(name)
    pc = index.get(name)
    if pc is None:
        return {"cflags": [], "libs": [], "missing": [name]}
    info = read_pc(pc)
    out = {"cflags": list(info["cflags"]), "libs": list(info["libs"]),
           "missing": [], "version": info["version"]}
    for req in info["requires"] + (info["requires_private"] if private else []):
        sub = _resolve_pkg(req, index, seen, private=private)
        out["cflags"].extend(sub.get("cflags", []))
        out["libs"].extend(sub.get("libs", []))
        out["missing"].extend(sub.get("missing", []))
    return out


def query(names: List[str], libdir: Optional[Path], want_cflags: bool,
          want_libs: bool, private: bool = False) -> Dict:
    index = build_index(search_dirs(libdir))
    cflags: List[str] = []
    libs: List[str] = []
    missing: List[str] = []
    versions: Dict[str, str] = {}
    for name in names:
        res = _resolve_pkg(name, index, private=private)
        missing.extend(res.get("missing", []))
        if not res.get("missing"):
            versions[name] = res.get("version", "")
        cflags.extend(res.get("cflags", []))
        libs.extend(res.get("libs", []))
    def _dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out = []
        for tok in seq:
            if tok in seen:
                continue
            seen.add(tok)
            out.append(tok.replace("\\", "/"))
        return out
    return {"cflags": _dedupe(cflags), "libs": _dedupe(libs),
            "missing": _dedupe(missing), "versions": versions,
            "packages": sorted(index)}


SHIM_POSIX = """#!/bin/sh
# Generated by tools/qt-ohos-run.py pkgconfig --write-shim: pkg-config stand-in
exec "{python}" "{script}" "$@"
"""

SHIM_BAT = """@echo off
rem Generated by tools/qt-ohos-run.py pkgconfig --write-shim: pkg-config stand-in
"{python}" "{script}" %*
"""


def write_shim(bin_dir: Path, script: Optional[Path] = None) -> Dict:
    """Write `pkg-config` / `pkg-config.bat` stand-ins (pointing at this module).

    Returns {written: [...], python, script}; the caller is responsible for adding bin_dir to PATH.
    """
    bin_dir = Path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = Path(script or __file__).resolve()
    python = sys.executable or "python3"
    written = []
    sh = bin_dir / "pkg-config"
    sh.write_text(SHIM_POSIX.format(python=python, script=script),
                  encoding="utf-8")
    sh.chmod(0o755)
    written.append(str(sh))
    bat = bin_dir / "pkg-config.bat"
    bat.write_text(SHIM_BAT.format(python=python, script=script),
                   encoding="utf-8")
    written.append(str(bat))
    return {"written": written, "python": python, "script": str(script)}


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv = ["--help"]
    if "--relocate" in argv:
        i = argv.index("--relocate")
        target = argv[i + 1] if len(argv) > i + 1 else None
        if not target:
            print("--relocate requires a directory argument (usually ohos-libs)", file=sys.stderr)
            return 2
        out = relocate_tree(Path(target), dry_run="--dry-run" in argv)
        for c in out["changed"]:
            print("relocated %s (%d change(s))" % (c["path"], len(c["notes"])))
            for note in c["notes"][:5]:
                print("  %s" % note)
        print("pkgconfig: scanned %d .pc, rewrote %d, local packages %d"
              % (out["scanned"], len(out["changed"]),
                 len(out["local_packages"])))
        return 0
    if "--write-shim" in argv:
        i = argv.index("--write-shim")
        bin_dir = Path(argv[i + 1]) if len(argv) > i + 1 else Path(
            ".qt-ohos/bin")
        libdir = _flag_value(argv, "--libdir")
        out = write_shim(bin_dir)
        for w in out["written"]:
            print("wrote %s" % w)
        if libdir:
            print("Set PKG_CONFIG_LIBDIR to the lib/pkgconfig of each package under %s"
                  % libdir)
        return 0
    if "--list-all" in argv:
        index = build_index(search_dirs(_flag_value(argv, "--libdir")))
        for name in sorted(index):
            info = read_pc(index[name])
            print("%-28s %s" % (name, info["version"]))
        return 0
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0

    want_cflags = "--cflags" in argv
    want_libs = "--libs" in argv or not want_cflags
    private = "--static" in argv or "--with-private" in argv
    libdir = _flag_value(argv, "--libdir")
    var = None
    for tok in argv:
        if tok.startswith("--variable="):
            var = tok.split("=", 1)[1]
    names = _positional_names(argv)
    res = query(names, libdir, want_cflags, want_libs, private)
    if "--exists" in argv:
        return 1 if res["missing"] else 0
    if var:
        index = build_index(search_dirs(libdir))
        for name in names:
            pc = index.get(name)
            if pc is None:
                print("", file=sys.stderr)
                return 1
            print(read_pc(pc)["variables"].get(var, ""))
        return 0
    if "--modversion" in argv:
        for name in names:
            if name in res["versions"]:
                print(res["versions"][name])
        return 1 if res["missing"] else 0
    out: List[str] = []
    if want_cflags:
        out.extend(res["cflags"])
    if want_libs:
        out.extend(res["libs"])
    if out:
        print(" ".join(out))
    if res["missing"]:
        print("packages not found: %s" % ", ".join(res["missing"]), file=sys.stderr)
        return 1
    return 0


def _positional_names(argv: List[str]) -> List[str]:
    """Extract package names: skip options, and also skip the arguments of options that take a value.

    In `--libdir /path`, `/path` does not start with `-`; filtering naively by "anything that
    is not an option is a package name" would look it up as a package (observed:
    `packages not found: /var/folders/...`).
    """
    out: List[str] = []
    skip = False
    for tok in argv:
        if skip:
            skip = False
            continue
        if tok in ("--libdir", "--define-variable"):
            skip = True
            continue
        if tok.startswith("-"):
            continue
        out.append(tok)
    return out


def _flag_value(argv: List[str], flag: str) -> Optional[Path]:
    for i, tok in enumerate(argv):
        if tok == flag and i + 1 < len(argv):
            return Path(argv[i + 1])
        if tok.startswith(flag + "="):
            return Path(tok.split("=", 1)[1])
    return None


if __name__ == "__main__":
    raise SystemExit(main())
