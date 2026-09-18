#!/usr/bin/env python3
"""qt-sdk-run.py - unified execution CLI for the qt-sdk-forge agent skill.

Covers the whole Qt OHOS SDK lifecycle (Python replacement of the bash
scripts in skills/kb-init/scripts/ that used to own this domain):

    python tools/qt-sdk-run.py init
    python tools/qt-sdk-run.py env                     # SV0 check
    python tools/qt-sdk-run.py src-clone --method commercial|opensource \
        --version 5.15 --dest workspace/qt-src/qt5.15 [--user U --pass P]
    python tools/qt-sdk-run.py status                  # stage/patches/releases
    python tools/qt-sdk-run.py patch-import <proposal-dir>
    python tools/qt-sdk-run.py patch-apply P0001 | patch-list | patch-revert
    python tools/qt-sdk-run.py patch-export P0001 --dest <dir>
    python tools/qt-sdk-run.py configure --qt 5.15 --render gl --build-type release
    python tools/qt-sdk-run.py build | install         # incremental + install
    python tools/qt-sdk-run.py verify                  # gates SV0..SV8
    python tools/qt-sdk-run.py smoke-mark --result pass --note "..."
    python tools/qt-sdk-run.py release --note "..." [--type release|test]
    python tools/qt-sdk-run.py release-list | use <ver> | diff <v1> <v2>
    python tools/qt-sdk-run.py upstream-check
    python tools/qt-sdk-run.py forge <proposal-dir>    # one-shot pipeline
    python tools/qt-sdk-run.py config set qt_src <path>

Budget / timeout (Agent markers):
    QT_SDK_TASK_BUDGET_SEC    max seconds for this session
    QT_SDK_TASK_DEADLINE      HH:MM wall-clock deadline
    --timeout                 per-command timeout for configure/build/install

Exit codes: 0 = PASS, 1 = FAIL, 2 = budget exhausted, 3 = PARTIAL.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qt_sdk import (building, envcheck, patching, releasing, srctree,  # noqa: E402
                    verify)
from qt_sdk.state import (BudgetExhausted, STAGES,  # noqa: E402
                          init_state, load_state)

BUDGET_ENV_VARS = ("QT_SDK_TASK_BUDGET_SEC", "QT_SDK_TASK_DEADLINE")


# ---------------------------------------------------------------- helpers

def _state(args) -> ForgeState:
    home = getattr(args, "home", None)
    try:
        return load_state(Path(home) if home else None)
    except FileNotFoundError:
        print("[qt-sdk-run] no forge state - run `init` first")
        sys.exit(1)


def _ok_or_die(result: dict, what: str) -> None:
    if result.get("ok"):
        return
    print("[qt-sdk-run] FAIL: %s - %s" % (what, result.get("error", "")))
    sys.exit(1)


def _print_checks(report: dict) -> None:
    for chk in report["checks"]:
        mark = "PASS" if chk["ok"] else "FAIL"
        print("  [%s] %-16s %s" % (mark, chk["name"], chk["detail"]))
    print("  => SV0 %s" % ("PASS" if report["ok"] else "FAIL"))


def _maybe_switch_variant(args, st) -> None:
    """If --qt (with optional --render/--build-type) is given on build/
    install/verify/release, switch the active variant slot first."""
    qt = getattr(args, "qt", None)
    if not qt:
        return
    render = getattr(args, "render", None) or "gl"
    build_type = getattr(args, "build_type", None) or "release"
    ctx = building.set_active_variant(st, qt, render, build_type)
    print("[qt-sdk-run] active variant: %s" % building.variant_key(
        qt, render, build_type))
    if ctx.get("install_started"):
        print("  (installed %s)" % ctx["install_started"])


def _print_variants(st) -> None:
    building.ensure_variants(st)
    build = st.section("build")
    variants = build.get("variants") or {}
    if not variants:
        return
    print("variants:")
    for key in sorted(variants):
        ctx = variants[key]
        mark = "*" if key == build.get("active") else " "
        print("  %s %-20s Qt%-5s %-7s %-4s %s" % (
            mark, key, ctx.get("qt_version"), ctx.get("build_type"),
            ctx.get("render"), ctx.get("sdk_dir")))


def _print_gates(report: dict) -> None:
    print("\nqt-sdk-forge verification gates")
    print("==============================")
    for gate in report["gates"]:
        print("  %-4s %-8s %-24s %s" % (
            gate["gate"], gate["status"], gate["name"],
            str(gate.get("detail", ""))[:90]))
    print("\nResult: %s" % report["result"])
    if report["result"] == "PARTIAL":
        print("  (compiled + installed, but no smoke evidence - report "
              "'compile-level ready' only)")


def _print_patches(entries) -> None:
    if not entries:
        print("  (no patches registered)")
    for e in entries:
        refs = e.get("refs") or []
        if isinstance(refs, str):
            refs = [refs]
        files = e.get("files") or []
        if isinstance(files, str):
            files = [files]
        print("  %-6s %-10s %-9s %-24s refs=%s files=%d" % (
            e.get("id"), e.get("type"), e.get("status"),
            str(e.get("origin"))[:24],
            ",".join(str(r) for r in refs) or "-", len(files)))


# ---------------------------------------------------------------- commands

def cmd_init(args) -> int:
    st = init_state(Path(args.home) if args.home else None)
    # bridge ENV.local.md paths so the CLI works right after kb-init
    defaults = envcheck.default_paths()
    cfg = st.env()
    for key, val in defaults.items():
        if val and not cfg.get(key):
            st.env_set(key, val)
    print("[qt-sdk-run] forge state at %s" % st.state_dir)
    for key, val in st.env().items():
        print("  %-16s %s" % (key, val))
    return 0


def cmd_env(args) -> int:
    report = envcheck.check()
    _print_checks(report)
    return 0 if report["ok"] else 1


def cmd_config(args) -> int:
    st = _state(args)
    if args.action == "set":
        st.env_set(args.key, args.value)
        print("  %s = %s" % (args.key, args.value))
    elif args.action == "get":
        print(st.env().get(args.key, ""))
    else:
        for key, val in st.env().items():
            print("  %-16s %s" % (key, val))
    return 0


def cmd_src_clone(args) -> int:
    dest = Path(args.dest)
    result = srctree.clone(args.method, args.version, dest,
                           user=args.user, password=args.password)
    for step in result.get("steps", []):
        print("  %-10s rc=%s" % (step["step"], step["rc"]))
        if step["rc"] != 0:
            print("    %s" % step["tail"][:600])
    if result.get("ok"):
        print("[qt-sdk-run] source tree ready: %s" % dest)
        print("  next: config set qt_src %s" % dest)
        return 0
    print("[qt-sdk-run] FAIL: clone incomplete")
    return 1


def cmd_status(args) -> int:
    st = _state(args)
    data = st.data
    print("forge state : %s" % st.state_dir)
    print("stage       : %s (completed: %d/%d)" % (
        data.get("stage"), len(data.get("completed", [])), len(STAGES)))
    print("next        : %s" % data.get("next", {}).get("action"))
    _print_variants(st)
    src = st.section("src")
    if src.get("path"):
        print("source      : %s @ %s" % (src.get("path"),
                                          str(src.get("qtbase_commit"))[:10]))
    print("patches:")
    _print_patches(patching.entries(st))
    releases = releasing.list_releases(st)
    print("releases    : %d (latest: %s)" % (
        len(releases), releases[0].get("version") if releases else "-"))
    gate = st.section("gates")
    if gate.get("result"):
        print("last verify : %s" % gate.get("result"))
    budget = data.get("budget", {})
    if budget.get("exhausted"):
        print("budget      : EXHAUSTED (%s) - use `resume`" %
              budget.get("reason"))
    return 0


def cmd_patch_import(args) -> int:
    st = _state(args)
    result = patching.import_proposal(st, Path(args.dir))
    _ok_or_die(result, "patch-import")
    entry = result["entry"]
    print("[qt-sdk-run] imported %s (%s, from %s)" % (
        entry["id"], entry["type"], entry["origin"]))
    print("  files: %s" % ", ".join(entry["files"]))
    for hint in result["review_hints"]:
        print("  review: %s" % hint)
    return 0


def cmd_patch_apply(args) -> int:
    st = _state(args)
    result = patching.apply(st, args.id)
    _ok_or_die(result, "patch-apply")
    print("[qt-sdk-run] applied %s at qtbase@%s" % (
        args.id, str(result.get("base_commit"))[:10]))
    return 0


def cmd_patch_list(args) -> int:
    st = _state(args)
    _print_patches(patching.entries(st))
    return 0


def cmd_patch_revert(args) -> int:
    st = _state(args)
    result = patching.revert(st, args.id)
    _ok_or_die(result, "patch-revert")
    print("[qt-sdk-run] reverted %s" % args.id)
    return 0


def cmd_patch_export(args) -> int:
    st = _state(args)
    result = patching.export(st, args.id, Path(args.dest))
    _ok_or_die(result, "patch-export")
    for path in result["exported"]:
        print("  %s" % path)
    return 0


def cmd_patch_mark(args) -> int:
    st = _state(args)
    result = patching.mark_status(st, args.id, args.status)
    _ok_or_die(result, "patch-mark")
    print("[qt-sdk-run] %s -> %s" % (args.id, args.status))
    return 0


def cmd_configure(args) -> int:
    st = _state(args)
    result = building.configure(st, args.qt, render=args.render,
                                build_type=args.build_type,
                                timeout=args.timeout)
    if result.get("ok"):
        print("[qt-sdk-run] configured %s -> %s"
              % (result["build_dir"], result["sdk_dir"]))
        return 0
    _fail_result(result, "configure")


def _switch_or_die(args, st) -> None:
    try:
        _maybe_switch_variant(args, st)
    except RuntimeError as exc:
        print("[qt-sdk-run] FAIL: %s" % exc)
        sys.exit(1)


def cmd_build(args) -> int:
    st = _state(args)
    _switch_or_die(args, st)
    result = building.build(st, timeout=args.timeout)
    if result.get("ok"):
        print("[qt-sdk-run] build PASS (%ss)" % result["result"].duration)
        return 0
    _fail_result(result, "build")


def cmd_install(args) -> int:
    st = _state(args)
    _switch_or_die(args, st)
    result = building.install(st, timeout=args.timeout)
    if result.get("ok"):
        print("[qt-sdk-run] install PASS (%ss)" % result["result"].duration)
        return 0
    _fail_result(result, "install")


def _fail_result(result: dict, what: str):
    res = result.get("result")
    detail = result.get("error") or (
        "%s, log: %s" % (res.status, res.evidence) if res else "unknown")
    print("[qt-sdk-run] FAIL: %s - %s" % (what, detail))
    sys.exit(1)


def cmd_verify(args) -> int:
    st = _state(args)
    _switch_or_die(args, st)
    report = verify.run(st)
    _print_gates(report)
    if report["result"] == "PASS":
        return 0
    if report["result"] == "PARTIAL":
        return 3
    return 1


def cmd_smoke_mark(args) -> int:
    st = _state(args)
    verify.mark_smoke(st, args.result, args.note)
    print("[qt-sdk-run] SV7 recorded: %s" % args.result)
    return 0


def cmd_release(args) -> int:
    st = _state(args)
    _switch_or_die(args, st)
    result = releasing.release(st, note=args.note,
                               release_type=args.type,
                               allow_diagnostic=args.allow_diagnostic)
    _ok_or_die(result, "release")
    print("[qt-sdk-run] released %s (%s) with patches: %s" % (
        result["version"], args.type, ",".join(result["patches"]) or "none"))
    print("  manifest: %s" % result["manifest"])
    print("  next    : use %s   # switch ENV.local.md" % result["version"])
    return 0


def cmd_release_list(args) -> int:
    st = _state(args)
    releases = releasing.list_releases(st)
    if not releases:
        print("  (no releases yet)")
    for m in releases:
        print("  %-26s %-7s Qt%-5s patches=%s sdk=%s" % (
            m.get("version"), m.get("type"), m.get("qt_version"),
            ",".join(p.get("id", "?") for p in m.get("patches", [])) or "-",
            m.get("sdk_dir")))
    return 0


def cmd_use(args) -> int:
    st = _state(args)
    result = releasing.use(st, args.version,
                           env_local=Path(args.env_local)
                           if args.env_local else None)
    _ok_or_die(result, "use")
    print("[qt-sdk-run] ENV.local.md: %s -> %s (%s)"
          % (result["env_var"], result["sdk_dir"], result["version"]))
    return 0


def cmd_diff(args) -> int:
    st = _state(args)
    result = releasing.diff_versions(st, args.v1, args.v2)
    _ok_or_die(result, "diff")
    for key in ("added_patches", "removed_patches"):
        for p in result[key]:
            print("  %-8s %s (%s) %s" % (key.split("_")[0], p.get("id"),
                                         p.get("type"),
                                         ",".join(p.get("refs", []))))
    print("  unchanged: %s" % (",".join(result["same_patches"]) or "-"))
    for key, (a, b) in result["meta_diff"].items():
        print("  %-12s %s -> %s" % (key, a, b))
    return 0


def cmd_upstream_check(args) -> int:
    st = _state(args)
    src = Path(st.env().get("qt_src") or "")
    if not (src / "qtbase").is_dir():
        print("[qt-sdk-run] FAIL: qt_src not configured")
        return 1
    report = srctree.upstream_check(src, patching.applied_files(st), st=st)
    if report.get("error"):
        print("[qt-sdk-run] FAIL: %s" % report["error"])
        return 1
    if report.get("fetch", {}).get("status") != "PASS":
        print("[qt-sdk-run] FAIL: git fetch failed")
        return 1
    commits = report.get("new_commits", [])
    print("branch %s: %d new upstream commits" % (report.get("branch"),
                                                  len(commits)))
    for line in commits[:30]:
        print("  %s" % line)
    if len(commits) > 30:
        print("  ... %d more" % (len(commits) - 30))
    print("\nwatch-dir commits (ohos-specific):")
    for line in report.get("watch_dir_commits", [])[:30]:
        print("  %s" % line)
    overlap = report.get("patch_overlap", {})
    if overlap:
        print("\nPATCH OVERLAP (superseded candidates - LLM must verify):")
        for commit, files in overlap.items():
            print("  %s" % commit)
            for f in files:
                print("    touches %s" % f)
    else:
        print("\nno overlap with locally applied patches")
    print("\nnext: classify changes per SKILL.md §7 (capability/fix/"
          "breaking/conflict), then `faults-build.py review` for due tickets")
    return 0


def cmd_forge(args) -> int:
    """One-shot: import -> apply -> configure -> build -> install -> verify."""
    st = _state(args)
    try:
        st.check_budget()
        imported = patching.import_proposal(st, Path(args.dir))
        _ok_or_die(imported, "patch-import")
        patch_id = imported["id"]
        for hint in imported["review_hints"]:
            print("  review: %s" % hint)
        applied = patching.apply(st, patch_id)
        _ok_or_die(applied, "patch-apply")
        print("[qt-sdk-run] applied %s" % patch_id)

        try:
            ctx = building.build_ctx(st)
        except RuntimeError:
            ctx = None
        need_conf = args.qt and (
            not ctx or ctx.get("qt_version") != args.qt
            or ctx.get("render") != args.render
            or ctx.get("build_type") != args.build_type)
        if need_conf:
            conf = building.configure(st, args.qt, render=args.render,
                                      build_type=args.build_type,
                                      timeout=args.timeout)
            _ok_or_die(conf, "configure")
        elif not ctx:
            print("[qt-sdk-run] FAIL: no build context - pass --qt")
            return 1

        for step, fn in (("build", building.build),
                         ("install", building.install)):
            st.check_budget()
            result = fn(st, timeout=args.timeout)
            if not result.get("ok"):
                _fail_result(result, step)
            print("[qt-sdk-run] %s PASS" % step)

        report = verify.run(st)
        _print_gates(report)
        if args.release:
            rel = releasing.release(st, note=args.note or "",
                                    release_type=args.type)
            _ok_or_die(rel, "release")
            print("[qt-sdk-run] released %s" % rel["version"])
        return {"PASS": 0, "PARTIAL": 3}.get(report["result"], 1)
    except BudgetExhausted as exc:
        print("[qt-sdk-run] %s" % exc)
        return 2


def cmd_resume(args) -> int:
    st = _state(args)
    st.reset_budget_session()
    data = st.data
    if data.get("budget", {}).get("exhausted"):
        data["budget"]["exhausted"] = False
        st.save()
    next_action = data.get("next", {}).get("action")
    print("[qt-sdk-run] resuming at: %s" % next_action)
    if not args.run:
        print("  (dry view - pass --run to continue)")
        return 0
    handlers = {
        "configure": lambda: _resume_configure(st),
        "build": lambda: cmd_build(_ns()),
        "install": lambda: cmd_install(_ns()),
        "verify": lambda: cmd_verify(_ns()),
    }
    handler = handlers.get(next_action)
    if not handler:
        print("  manual step (%s) - run it explicitly" % next_action)
        return 0
    return handler()


def _resume_configure(st: ForgeState) -> int:
    try:
        ctx = building.build_ctx(st)
        args = _ns(qt=ctx.get("qt_version"), render=ctx.get("render"),
                   build_type=ctx.get("build_type"))
    except RuntimeError:
        print("  no build context to re-configure - run `configure --qt ...`")
        return 0
    return cmd_configure(args)


class _ns:
    """Minimal namespace shim for reusing cmd_* handlers in resume/forge."""

    def __init__(self, **kw):
        self.timeout = None
        self.render = "gl"
        self.build_type = "release"
        self.qt = None
        for key, val in kw.items():
            setattr(self, key, val)
        if not hasattr(self, "home"):
            self.home = None


# ---------------------------------------------------------------- parser

def _add_variant_args(p, required: bool) -> None:
    """--qt/--render/--build-type: on build/install/verify/release these
    are optional and switch the active variant slot (must be configured);
    on configure/forge they define the variant to configure."""
    p.add_argument("--qt", required=required, choices=["5.12", "5.15"],
                   help="Qt version (switch active variant)")
    p.add_argument("--render", default="gl", choices=["gl", "gles"])
    p.add_argument("--build-type", default="release",
                   choices=["release", "debug"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="qt-sdk-run.py",
        description="qt-sdk-forge execution CLI (Qt OHOS SDK lifecycle)")
    parser.add_argument("--home", help="forge home (default "
                        "workspace/qt-sdk, override QT_SDK_HOME)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create .qtsdk state (bridges "
                      "ENV.local.md)")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("env", help="SV0 environment check")
    p.set_defaults(func=cmd_env)

    p = sub.add_parser("config", help="manage .qtsdk/env.json")
    p.add_argument("action", choices=["set", "get", "show"])
    p.add_argument("key", nargs="?", default=None)
    p.add_argument("value", nargs="?", default=None)
    p.set_defaults(func=cmd_config)

    p = sub.add_parser("src-clone", help="clone Qt harmony branch + "
                       "submodules")
    p.add_argument("--method", required=True,
                   choices=["commercial", "opensource"])
    p.add_argument("--version", required=True, choices=["5.12", "5.15"])
    p.add_argument("--dest", required=True)
    p.add_argument("--user", default="")
    p.add_argument("--pass", dest="password", default="")
    p.set_defaults(func=cmd_src_clone)

    p = sub.add_parser("status", help="stage / patch stack / releases")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("patch-import", help="import external change proposal")
    p.add_argument("dir")
    p.set_defaults(func=cmd_patch_import)

    p = sub.add_parser("patch-apply", help="git apply a registered patch")
    p.add_argument("id")
    p.set_defaults(func=cmd_patch_apply)

    p = sub.add_parser("patch-list", help="patch stack overview")
    p.set_defaults(func=cmd_patch_list)

    p = sub.add_parser("patch-revert", help="git apply -R a patch")
    p.add_argument("id")
    p.set_defaults(func=cmd_patch_revert)

    p = sub.add_parser("patch-export", help="copy stored patch(es) to dest/")
    p.add_argument("id")
    p.add_argument("--dest", default=".")
    p.set_defaults(func=cmd_patch_export)

    p = sub.add_parser("patch-mark", help="advance patch status "
                       "(superseded/built/...)")
    p.add_argument("id")
    p.add_argument("status")
    p.set_defaults(func=cmd_patch_mark)

    p = sub.add_parser("configure", help="full configure for a variant")
    _add_variant_args(p, required=True)
    p.add_argument("--timeout", type=float, default=None)
    p.set_defaults(func=cmd_configure)

    for name, help_, fn in (
            ("build", "incremental compile (no install)", cmd_build),
            ("install", "make install into the SDK", cmd_install),
    ):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--timeout", type=float, default=None)
        _add_variant_args(p, required=False)
        p.set_defaults(func=fn)

    p = sub.add_parser("verify", help="run gates SV0..SV8")
    _add_variant_args(p, required=False)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("smoke-mark", help="record manual SV7 evidence")
    p.add_argument("--result", required=True, choices=["pass", "fail"])
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_smoke_mark)

    p = sub.add_parser("release", help="cut a version + manifest")
    p.add_argument("--note", default="")
    p.add_argument("--type", default="release", choices=["release", "test"])
    p.add_argument("--allow-diagnostic", action="store_true",
                   help="let diagnostic patches into a release build")
    _add_variant_args(p, required=False)
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("release-list", help="list released versions")
    p.set_defaults(func=cmd_release_list)

    p = sub.add_parser("use", help="switch ENV.local.md to a release")
    p.add_argument("version")
    p.add_argument("--env-local", default=None,
                   help="path to ENV.local.md (default KB_ROOT/ENV.local.md)")
    p.set_defaults(func=cmd_use)

    p = sub.add_parser("diff", help="compare two releases")
    p.add_argument("v1")
    p.add_argument("v2")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("upstream-check", help="fetch upstream + patch "
                       "overlap report")
    p.set_defaults(func=cmd_upstream_check)

    p = sub.add_parser("forge", help="one-shot: import -> apply -> build -> "
                       "install -> verify [--release]")
    p.add_argument("dir")
    _add_variant_args(p, required=False)
    p.add_argument("--timeout", type=float, default=None)
    p.add_argument("--release", action="store_true",
                   help="also cut a version after verify")
    p.add_argument("--type", default="test", choices=["release", "test"])
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_forge)

    p = sub.add_parser("resume", help="continue from checkpoint")
    p.add_argument("--run", action="store_true")
    p.set_defaults(func=cmd_resume)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
