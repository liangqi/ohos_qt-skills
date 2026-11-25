#!/usr/bin/env python3
"""portgraph.py - unified CLI for the portability graph of Qt apps ported to HarmonyOS.

    python tools/portgraph.py ingest harmonybrew   # parse Harmonybrew formulas into the DB
    python tools/portgraph.py ingest cmdpkgs       # clone + parse the cmd-pkgs README
    python tools/portgraph.py ingest kb            # Qt modules + interface allowlist seeds
    python tools/portgraph.py clone <git-url>      # shallow clone + scan into the DB
    python tools/portgraph.py scan <project-path>  # scan a Qt project to create an app node
    python tools/portgraph.py analyze <app-id|name># portability verdict + blockers
    python tools/portgraph.py deps <path|app>      # full dependency analysis (classification + version ranges)
    python tools/portgraph.py fetch "zlib,openssl@3"  # download HarmonyOS bottles for given packages
    python tools/portgraph.py fetch-deps corpus_a    # download all of an app's dependency artifacts in one go
    python tools/portgraph.py stats                # data statistics
    python tools/portgraph.py serve [--port 8000]  # FastAPI + frontend page
    python tools/portgraph.py export [out.json]    # export focus graph data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))

from port_graph import (cloner, cmdpkgs, db, engine, harmonybrew,  # noqa: E402
                        kb_seed, project_scanner)


def _emit(payload, args) -> None:
    print(json.dumps(payload, ensure_ascii=False,
                     indent=None if getattr(args, "compact", False) else 1))


def _resolve_app(conn, name: str) -> str:
    if db.get_node(conn, name):
        return name
    node = db.find_node_by_name(conn, name)
    if node and node["kind"] == "app":
        return node["id"]
    row = conn.execute(
        "SELECT id FROM nodes WHERE kind='app' AND id LIKE ?",
        ("app:%" + name.lower() + "%",)).fetchone()
    if row:
        return row["id"]
    print("[portgraph] app not found: %s (scan/clone it into the DB first; if you meant "
          "to pass a project path, check that the path exists)" % name)
    sys.exit(1)


def cmd_ingest(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    try:
        if args.source == "harmonybrew":
            _emit(harmonybrew.ingest(conn, pull=not args.offline), args)
        elif args.source == "cmdpkgs":
            _emit(cmdpkgs.ingest(conn, pull=not args.offline), args)
        elif args.source == "kb":
            _emit(kb_seed.ingest(conn), args)
        elif args.source == "all":
            out = {"kb": kb_seed.ingest(conn),
                   "harmonybrew": harmonybrew.ingest(
                       conn, pull=not args.offline),
                   "cmdpkgs": cmdpkgs.ingest(conn, pull=not args.offline)}
            _emit(out, args)
        else:
            print("unknown data source: %s" % args.source)
            sys.exit(1)
    finally:
        conn.close()


def cmd_clone(args) -> None:
    """Shallow-clone a git repository into workspace/ and scan it into the DB."""
    try:
        info = cloner.clone_repo(args.url, getattr(args, "name", None))
    except RuntimeError as exc:
        print("[portgraph] clone failed: %s" % exc)
        sys.exit(1)
    conn = db.connect()
    db.init_db(conn)
    try:
        scan = project_scanner.scan_project(conn, info["path"])
        _emit({"clone": info, "scan": scan}, args)
    finally:
        conn.close()


def cmd_scan(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    try:
        _emit(project_scanner.scan_project(conn, args.project), args)
    finally:
        conn.close()


def _print_links(art: Dict, indent: str = "      ") -> None:
    """Print a node's HarmonyOS artifact and source links (when present)."""
    if not art:
        return
    if art.get("artifact_url"):
        print("%sHarmonyOS artifact: %s" % (indent, art["artifact_url"]))
    elif art.get("artifact_cmd"):
        print("%sHarmonyOS artifact: %s" % (indent, art["artifact_cmd"]))
    elif art.get("artifact_local"):
        print("%sHarmonyOS artifact (local): %s" % (indent, art["artifact_local"]))
    elif art.get("provided"):
        print("%sHarmonyOS artifact: provided by Qt / the HarmonyOS framework, no separate download or porting needed" % indent)
    else:
        print("%sHarmonyOS artifact: none -> cross-compile it yourself; portability is decided recursively from dependencies"
              % indent)
    src = art.get("source_url")
    repo = art.get("repo_url")
    home = art.get("homepage")
    if src:
        print("%sSource download: %s" % (indent, src))
    if repo:
        print("%sSource repository: %s" % (indent, repo))
    if home:
        print("%sProject homepage: %s" % (indent, home))


def _print_dep_artifacts(conn, app_id: str) -> None:
    """Print the HarmonyOS artifact/source link list of all of an app's dependencies.

    ready      = can be downloaded and used directly, no porting needed
    provided   = provided by Qt / the HarmonyOS framework itself, e.g. Qt modules
    need port  = no artifact, cross-compile it yourself; portability comes from the recursive verdict
    """
    rows = conn.execute(
        "SELECT dst, type FROM edges WHERE src=? ORDER BY type, dst",
        (app_id,)).fetchall()
    if not rows:
        return
    groups = {"ready": [], "provided": [], "need_port": []}
    for r in rows:
        nd = db.get_node(conn, r["dst"])
        if nd is None:
            continue
        art = engine.artifact_info(nd)
        key = ("ready" if art["ready"]
               else "provided" if art["provided"] else "need_port")
        groups[key].append((nd, art, r["type"]))
    print("Dependency artifact list: %d dependencies (%d with HarmonyOS artifacts / %d framework-provided / "
          "%d need porting)" % (
              len(rows), len(groups["ready"]), len(groups["provided"]),
              len(groups["need_port"])))
    for key, label in (("ready", "ready"), ("provided", "provided"),
                       ("need_port", "need port")):
        for nd, art, etype in groups[key]:
            print("  [%s] %s v%s (%s) %s"
                  % (label, nd["name"], nd["version"] or "?", etype,
                     nd["port_status"]))
            _print_links(art)


def cmd_analyze(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    try:
        app_id = _resolve_app(conn, args.app)
        result = engine.analyze(conn, app_id)
        if getattr(args, "summary", False):
            print("verdict: %s" % result["verdict"])
            print("blockers: %d" % len(result["blockers"]))
            for b in result["blockers"]:
                print("  [%s] %s: %s" % (b["kind"], b["node"], b["reason"]))
                _print_links(b.get("artifact"))
            print("unknowns: %d" % len(result["unknowns"]))
            for u in result["unknowns"]:
                print("  [%s] %s: %s" % (u["kind"], u["node"], u["reason"]))
                _print_links(u.get("artifact"))
            pe = result.get("platform_excluded", [])
            print("platform_excluded: %d" % len(pe))
            for p in pe:
                alts = ", ".join(a["name"] for a in p.get("alternatives", []))
                print("  [iface] %s (%s): %s"
                      " -> HarmonyOS alternatives: %s" % (
                          p["iface"], p.get("category"), p["reason"],
                          alts or "(no alternative interface in the same category, implement it yourself)"))
            _print_dep_artifacts(conn, app_id)
        else:
            _emit(result, args)
    finally:
        conn.close()


def cmd_stats(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    try:
        _emit(db.stats(conn), args)
    finally:
        conn.close()


def cmd_export(args) -> None:
    conn = db.connect()
    db.init_db(conn)
    try:
        nodes = db.all_nodes(conn)
        edges = db.all_edges(conn)
        data = {"nodes": nodes, "edges": edges,
                "clusters": db.all_clusters(conn),
                "interfaces": db.all_interfaces(conn)}
        out = Path(args.out) if args.out else Path("workspace/portgraph.json")
        out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print("exported %d nodes / %d edges -> %s" % (
            len(nodes), len(edges), out))
    finally:
        conn.close()


def cmd_fetch(args) -> None:
    """Download Harmonybrew bottles on any platform as cross-compilation dependencies."""
    from port_graph import OHOS_LIBS
    conn = db.connect()
    db.init_db(conn)
    try:
        out = Path(getattr(args, "out", None) or OHOS_LIBS)
        pkgs = [p.strip() for p in args.package.split(",") if p.strip()]
        results = []
        failures = []
        for name in pkgs:
            try:
                r = harmonybrew.fetch_bottle(conn, name, out,
                                             force=getattr(args, "force", False))
            except RuntimeError as exc:
                print("[portgraph] %s" % name)
                print("  %s" % exc)
                failures.append({"name": name, "error": str(exc)})
                continue
            results.append(r)
            if r.get("skipped"):
                print("[fetch] %s v%s already exists: %s"
                      % (r["package"], r["version"], r["installed"]))
            else:
                print("[fetch] %s v%s -> %s" % (
                    r["package"], r["version"], r["installed"]))
                print("  bottle : %s" % r["bottle_url"])
                print("  sha256 : %s" % r["sha256"])
                if r.get("symlinks_fixed"):
                    print("  links  : %d .so symlinks fixed (materialized as copies on NTFS)"
                          % len(r["symlinks_fixed"]))
                if r.get("libs"):
                    print("  libs   : %s" % ", ".join(r["libs"]))
                print("  CMake  : %s" % r["hints"]["cmake"].replace(
                    "\n", "\n           "))
                print("  qmake  : %s" % r["hints"]["qmake"])
                print("  deploy : %s" % r["hints"]["deploy"])
        if failures:
            print("\n[fetch] %d/%d succeeded, %d failed: %s" % (
                len(results), len(pkgs), len(failures),
                ", ".join(f["name"] for f in failures)))
            # all failed = 1 (retryable overall failure); partial success = 2 (something is usable,
            # but the caller must not treat it as "all ready")
            sys.exit(1 if not results else 2)
        if not results:
            sys.exit(1)
    finally:
        conn.close()


def cmd_fetch_deps(args) -> None:
    """Download the HarmonyOS artifacts of all of an app's dependencies in one go (agent tool, docs/fetch-deps.md)."""
    from port_graph import OHOS_LIBS, deps_fetch
    conn = db.connect()
    db.init_db(conn)
    try:
        app_id = _resolve_app(conn, args.app)
        out = Path(getattr(args, "out", None) or OHOS_LIBS)
        total = len(deps_fetch.dependency_closure(conn, app_id))
        done = {"n": 0}
        order = ["downloaded", "already_local", "failed", "covered",
                 "provided", "cmd_only", "need_port", "test",
                 "would_download", "target"]

        def on_entry(e):
            done["n"] += 1
            st = e["status"]
            if st in ("downloaded", "already_local", "would_download"):
                print("[%d/%d] %s v%s %s -> %s"
                      % (done["n"], total, e["name"], e["version"] or "?",
                         "to download" if st == "would_download" else "ready",
                         e.get("installed") or e.get("artifact_url")))
            elif st == "failed":
                print("[%d/%d] %s failed: %s (%s)"
                      % (done["n"], total, e["name"], e.get("error"),
                         e.get("artifact_url")))
            elif st == "covered":
                print("[%d/%d] %s same-named artifact already fetched: %s"
                      % (done["n"], total, e["name"], e["installed"]))
            elif st == "cmd_only":
                print("[%d/%d] %s obtain via command: %s"
                      % (done["n"], total, e["name"], e["artifact_cmd"]))
            elif st == "test":
                print("[%d/%d] %s test-only dependency (not shipped, skipped)"
                      % (done["n"], total, e["name"]))
            elif st == "need_port":
                src = (e.get("repo_url") or e.get("source_url")
                       or e.get("homepage"))
                if src:
                    print("[%d/%d] %s needs porting yourself (source: %s)"
                          % (done["n"], total, e["name"], src))
                elif e.get("note"):
                    print("[%d/%d] %s %s"
                          % (done["n"], total, e["name"], e["note"]))
                else:
                    print("[%d/%d] %s needs porting yourself (not in the DB, no source link: "
                          "check that the dependency name is correct, or look up the source manually)"
                          % (done["n"], total, e["name"]))

        m = deps_fetch.fetch_app_deps(
            conn, app_id, out, force=getattr(args, "force", False),
            dry_run=getattr(args, "dry_run", False),
            jobs=getattr(args, "jobs", 8),
            # with --json stdout carries only the manifest (progress output would break machine parsing)
            progress=None if getattr(args, "json", False) else on_entry)

        if getattr(args, "json", False):
            _emit(m, args)
            return
        s = m["summary"]
        print("\n[%s] dependency closure, %d items: %s" % (
            m["app"]["name"], m["closure_size"],
            " / ".join("%s %d" % (k, s.get(k, 0)) for k in order
                       if s.get(k))))
        if m["toolchain"]["cmake_prefix_path"]:
            print("\nCMake cross-compilation integration:")
            print("  " + m["toolchain"]["cmake"].replace("\n", "\n  "))
        if m.get("manifest_path"):
            print("\nmanifest: %s" % m["manifest_path"])
        if s.get("failed"):
            sys.exit(1)
    finally:
        conn.close()


def cmd_deps(args) -> None:
    """Full dependency analysis: link/build-tool/runtime/test/vendored classification + version ranges.

    See docs/deps-report.md. target is a project path or the name of a scanned app.
    """
    from port_graph import deps_report, qt_scanner
    conn = db.connect()
    db.init_db(conn)
    try:
        target = args.target
        p = Path(target)
        if p.is_dir():
            root = p
        elif p.exists() or "/" in target or "\\" in target \
                or target.startswith("."):
            # The user passed something path-shaped (contains separators / exists but is not a directory):
            # report it as a path error rather than a misleading "app not found"
            print("[portgraph] project path does not exist or is not a directory: %s"
                  " (to analyze a scanned app, pass the app name, e.g. corpus_a)" % target)
            sys.exit(1)
        else:
            app_id = _resolve_app(conn, target)
            root_path = db.get_meta(conn, "root_%s" % app_id)
            if not root_path or not Path(root_path).is_dir():
                print("[portgraph] project path for %s not found: scan/clone it into the DB first, "
                      "or pass the project path directly" % target)
                sys.exit(1)
            root = Path(root_path)
        info = qt_scanner.scan_project(root)
        # Ingest along the way (idempotent): lets analyze/fetch-deps use the same target afterwards
        project_scanner.scan_project(conn, root, info=info)
        report = deps_report.analyze_dependencies(conn, root, info=info)
        if getattr(args, "json", False):
            _emit(report, args)
        else:
            print(deps_report.render_text(report))
    finally:
        conn.close()


def cmd_serve(args) -> None:
    try:
        import uvicorn
        from port_graph.api import create_app
    except ImportError as exc:
        print("[portgraph] missing dependency: %s\nRun first: pip install fastapi uvicorn"
              % exc)
        sys.exit(1)
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="portgraph.py",
        description="Portability topology graph for porting Qt apps to HarmonyOS")
    parser.add_argument("--compact", action="store_true",
                        help="output compact JSON")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("ingest", help="collect data into the DB")
    p.add_argument("source", choices=["harmonybrew", "cmdpkgs", "kb", "all"])
    p.add_argument("--offline", action="store_true",
                   help="do not run git pull for cmdpkgs")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("clone", help="shallow clone + scan into the DB")
    p.add_argument("url", help="http(s) URL of the git repository")
    p.add_argument("--name", help="custom workspace directory name")
    p.set_defaults(func=cmd_clone)

    p = sub.add_parser("scan", help="scan a Qt project")
    p.add_argument("project")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("analyze", help="portability analysis")
    p.add_argument("app")
    p.add_argument("--summary", action="store_true")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser(
        "deps", help="full dependency analysis (link/build-tool/runtime/test/vendored "
                     "classification + version ranges + artifact sources, see docs/deps-report.md)")
    p.add_argument("target", help="project path or scanned app name (e.g. corpus_a)")
    p.add_argument("--json", action="store_true",
                   help="output the full report as JSON (machine-readable, for agents to parse)")
    p.set_defaults(func=cmd_deps)

    p = sub.add_parser("stats", help="data statistics")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("fetch", help="download Harmonybrew bottles (HarmonyOS dependencies usable on any platform, "
                      "for OHOS NDK cross-compilation)")
    p.add_argument("package",
                   help="package names (comma-separated for several; @ variants such as openssl@3)")
    p.add_argument("--out", help="extraction directory (default workspace/ohos-libs)")
    p.add_argument("--force", action="store_true", help="download again even if it already exists")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("fetch-deps",
                       help="download the HarmonyOS artifacts of all of an app's dependencies in one go (agent tool, "
                            "see docs/fetch-deps.md)")
    p.add_argument("app", help="app ID or name (e.g. corpus_a / app:corpus_a)")
    p.add_argument("--out", help="download/extraction directory (default workspace/ohos-libs, cache shared across apps)")
    p.add_argument("--force", action="store_true", help="download again even if it already exists")
    p.add_argument("--jobs", type=int, default=8,
                   help="number of parallel download threads (default 8; on a weak network serial downloads once timed out after 90 minutes, "
                        "parallel takes about 8 minutes at the same scale; 0/1 = disable parallel prefetch)")
    p.add_argument("--dry-run", action="store_true",
                   help="only output the classified list, no downloads, no disk writes")
    p.add_argument("--json", action="store_true",
                   help="output the full manifest as JSON (machine-readable, for agents to parse)")
    p.set_defaults(func=cmd_fetch_deps)

    p = sub.add_parser("export", help="export the full graph as JSON")
    p.add_argument("out", nargs="?")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("serve", help="start the web service")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1")
    p.set_defaults(func=cmd_serve)

    # Support a trailing --compact: the global --compact must come before the subcommand, but users tend to
    # write it after (e.g. `deps X --json --compact`), so add the flag to every subcommand
    # (argparse subparsers do not override namespace values already set by the main parser; both positions work)
    for p in sub.choices.values():
        p.add_argument("--compact", action="store_true",
                       help="output compact JSON (equivalent to the global --compact)")

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
