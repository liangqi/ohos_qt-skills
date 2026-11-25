#!/usr/bin/env python3
"""qt-ohos-run.py - unified execution CLI for Qt -> HarmonyOS porting.

Turns the ohos_qt-skills knowledge base into an executable workflow:

    python tools/qt-ohos-run.py init     <project>
    python tools/qt-ohos-run.py scan     <project>      # pre-scan + risk report
    python tools/qt-ohos-run.py assess   <project>      # feasibility verdict
                                                      # (portable/blocked/uncertain)
    python tools/qt-ohos-run.py plan                      # migration plan
    python tools/qt-ohos-run.py patch                     # tracked auto fixes
    python tools/qt-ohos-run.py build | package | install | launch | smoke
    python tools/qt-ohos-run.py verify                    # gates G0..G12
    python tools/qt-ohos-run.py analyze-log <log>         # error pattern engine
    python tools/qt-ohos-run.py status | resume --run | migrate <project> | finish
    python tools/qt-ohos-run.py draft "<title>" | promote QOHxxx | recipes
    python tools/qt-ohos-run.py rollback                  # restore originals/
    python tools/qt-ohos-run.py mark-gate G10|G11|G12 --result pass --note "..."
    python tools/qt-ohos-run.py mark-ui                   # manual G9 evidence
    python tools/qt-ohos-run.py config set <key> <value> | config show

Budget / timeout (production Agent markers):
    QT_OHOS_TASK_BUDGET_SEC   max seconds for this session
    QT_OHOS_TASK_DEADLINE     HH:MM wall-clock deadline
    --timeout                 per-command timeout (default 600s)

Exit codes: 0 = PASS, 1 = FAIL, 2 = budget exhausted, 3 = PARTIAL.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qt_ohos import (assessor, builder, dependency, error_engine, knowledge,
                     migration, report, rule_engine, scanner,
                     state as state_mod, verifier)
from qt_ohos.patch import ChangeTracker
from qt_ohos.state import BudgetExhausted, MigrationState, find_hdc

KB_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- helpers

def _resolve_project(args, required: bool) -> Path:
    project = Path(getattr(args, "project", None) or ".").resolve()
    if not project.is_dir():
        print("[qt-ohos-run] project directory not found: %s" % project)
        sys.exit(1)
    if required or (project / state_mod.STATE_DIR_NAME).exists():
        return project
    print("[qt-ohos-run] no migration state in %s" % project)
    print("[qt-ohos-run] use `--project <project dir>` to point at a project that has been scanned"
          " (e.g. `qt-ohos-run --project ~/app scan` followed by `--project ~/app plan`),"
          " or run `init` in that project first")
    sys.exit(1)


def _require_explicit_project(args, command: str) -> None:
    """init/scan/migrate/assess need an explicit project: otherwise .qt-ohos would be created in the repo root or cwd."""
    if not ((getattr(args, "path", None)) or getattr(args, "project", None)):
        print("[qt-ohos-run] %s needs a project directory: `%s <project dir>` or "
              "`--project <project dir> %s`" % (command, command, command))
        sys.exit(2)


def _apply_positional(args) -> None:
    """Merge the optional positional project argument into args.project so `cmd <dir>` and `--project <dir> cmd` are equivalent."""
    path = getattr(args, "path", None)
    if path:
        args.project = path


def _state(args) -> MigrationState:
    project = _resolve_project(args, required=False)
    return state_mod.load_state(project)


def _say(args, message=""):
    """Human-readable output. With `--json` it goes to stderr - stdout must be directly parseable JSON."""
    print(message, file=sys.stderr if getattr(args, "json", False) else sys.stdout)


def _emit(payload, args):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_risk_report(risk: dict, args=None) -> None:
    say = (lambda text: _say(args, text)) if args is not None else print
    summary = risk.get("summary") or {}
    say("\nQt HarmonyOS Porting Risk Report")
    say("================================")
    for sev in ("critical", "high", "medium", "low"):
        count = summary.get(sev, 0)
        if count:
            say("%-8s : %d" % (sev.upper(), count))
    for finding in risk.get("findings", [])[:40]:
        say("  %-5s %-7s %-22s %s:%s%s" % (
            finding["severity"][:4].upper(), finding["rule"],
            str(finding.get("name"))[:22], finding.get("file"),
            finding.get("line"),
            ("  [%s]" % finding["scope"]) if finding.get("scope") else ""))
        if finding.get("snippet"):
            say("        %s" % finding["snippet"][:100])
    if len(risk.get("findings", [])) > 40:
        say("  ... %d more findings in scan.json" %
              (len(risk["findings"]) - 40))


def _import_env_local(st) -> bool:
    """Bridge KB_ROOT/ENV.local.md (kb-init product) into .qt-ohos/env.json.

    PROC7 fix: G0 consumed env.json only, while kb-init writes ENV.local.md.
    Picks the first Qt SDK prefix that actually exists on this machine (WSL
    vs Windows paths), plus the template / native SDK hints.
    """
    env_local = KB_ROOT / "ENV.local.md"
    if not env_local.is_file():
        return False
    env = builder.env_of(st)
    if env.get("qt_sdk_prefix") or env.get("build_command"):
        return False                      # already configured; do not override
    values = {}
    for match in re.finditer(
            r"\|\s*`([A-Z0-9_]+)`\s*\|\s*`([^`]*)`\s*\|",
            env_local.read_text(encoding="utf-8", errors="replace")):
        key, val = match.group(1), match.group(2).strip()
        if val:
            values[key] = val
    candidates = [values.get("QT6_OHOS_SDK"), values.get("QT5_15_OHOS_SDK"),
                  values.get("QT5_12_OHOS_SDK")]
    prefix = next((c for c in candidates if c and Path(c).exists()), None)
    if not prefix:
        return False
    env["qt_sdk_prefix"] = prefix
    for src, dst in (("QT5_15_OHOS_SDK", "qt5_sdk_prefix"),
                     ("QT6_OHOS_SDK", "qt6_sdk_prefix"),
                     ("OHOS_SDK_NATIVE", "ohos_sdk_native"),
                     ("OHOS_TEMPLATE_SRC", "ohos_template_src"),
                     ("DEVECO_PATH", "deveco_path")):
        if values.get(src):
            env[dst] = values[src]
    env["env_source"] = "ENV.local.md"
    st.write_json("env.json", env)
    print("[qt-ohos-run] env bridged from ENV.local.md: qt_sdk_prefix=%s"
          % prefix)
    return True


def _generate_shell_project(st, project: Path) -> bool:
    """INIT3 fix: materialize the HarmonyOS shell project from the KB template.

    Preference: env.json ohos_template_src (Qt source / SDK templates), then
    the bundled templates/qt-ohos-app (same content, committed with the KB).
    Renders CMakeLists.txt.tpl (golden rules B1/B2/B10) with the app name and
    the project's own C++ sources, and bridges bundle_name into env.json.
    """
    env = builder.env_of(st)
    candidates = [env.get("ohos_template_src"),
                  str(KB_ROOT / "templates" / "qt-ohos-app")]
    src_dir = next((c for c in candidates if c and Path(c).is_dir()), None)
    tpl = KB_ROOT / "templates" / "qt-ohos-app" / "CMakeLists.txt.tpl"
    if not src_dir or not tpl.is_file():
        return False
    shutil.copytree(src_dir, project, dirs_exist_ok=True)

    info = st.read_json("scan.json", default={}) or {}
    app_name = re.sub(r"[^A-Za-z0-9_-]", "", info.get("name") or "qtapp") or "qtapp"
    sources = [s["path"] for s in info.get("sources", [])
               if s.get("ext") in (".cpp", ".cc", ".cxx")
               and not s["path"].startswith(("entry/", "qEmbedded",
                                             "AppScope/", "hvigor/"))][:40]
    if not sources:
        sources = ["entry/src/main/cpp/hello.cpp"]
    cmake = tpl.read_text(encoding="utf-8")
    cmake = cmake.replace("{{APP_NAME}}", app_name).replace(
        "{{SOURCES}}", "\n    ".join(sources))
    cmake_dir = project / "entry" / "src" / "main" / "cpp"
    cmake_dir.mkdir(parents=True, exist_ok=True)
    (cmake_dir / "CMakeLists.txt").write_text(cmake, encoding="utf-8")

    if not env.get("bundle_name"):
        app_json = project / "AppScope" / "app.json5"
        if app_json.is_file():
            match = re.search(r'"bundleName"\s*:\s*"([^"]+)"',
                              app_json.read_text(encoding="utf-8",
                                                 errors="replace"))
            if match:
                env["bundle_name"] = match.group(1)
                st.write_json("env.json", env)
    print("[qt-ohos-run] shell project generated from %s (app=%s, %d source(s))"
          % (src_dir, app_name, len(sources)))
    if str(info.get("qt_version_hint") or "").startswith("6"):
        print("[qt-ohos-run] note: Qt6 target - review entry CMakeLists "
              "(qt_add_executable / libqohos differ, see "
              "procedural/qt6-ohos-windows-cli-deploy.md)")
    return True


# ---------------------------------------------------------------- commands

def cmd_init(args):
    _apply_positional(args)
    _require_explicit_project(args, "init")
    project = _resolve_project(args, required=True)
    st = state_mod.init_state(project)
    print("[qt-ohos-run] initialized migration state: %s" % st.state_dir)
    print("[qt-ohos-run] next: qt-ohos-run scan %s" % project)
    return 0


_QT_VERSION_UNDETERMINED = ("could not determine the qt major version",
                            "未能从构建文件判定 Qt 主版本")


def _scan_with_env(st, project) -> dict:
    """Scan the project and apply the env.json qt_version override (assess --force used to drop this override)."""
    info = scanner.scan_project(project)
    override = str((builder.env_of(st) or {}).get("qt_version") or "").strip()
    if override:
        info["qt_version_hint"] = override
        info["qt_version_evidence"] = "config set qt_version %s" % override
        # Match both the current English scanner warning and the legacy Chinese one.
        info["warnings"] = [w for w in info.get("warnings", [])
                            if not any(m in w.lower() for m in _QT_VERSION_UNDETERMINED)]
    return info


def cmd_scan(args):
    _apply_positional(args)
    _require_explicit_project(args, "scan")
    project = _resolve_project(args, required=True)
    st = state_mod.init_state(project) if not (
        project / state_mod.STATE_DIR_NAME / "state.json").exists() else \
        state_mod.load_state(project)
    ran = []
    try:
        for stage in ("env_check", "project_scan", "qt_scan", "risk_scan",
                      "dependency_scan"):
            if stage in st.data.get("completed", []) and not args.force:
                continue
            ran.append(stage)
            st.check_budget()
            st.begin_stage(stage)
            if stage == "env_check":
                env = builder.env_of(st)
                if not env:
                    if _import_env_local(st):
                        pass
                    else:
                        print("[qt-ohos-run] env.json empty - configure via "
                              "`config set <key> <value>` or run kb-init "
                              "(ENV.local.md bridges automatically, G0 will "
                              "FAIL until configured)")
                st.complete_stage(stage, next_action="scan")
            elif stage in ("project_scan", "qt_scan"):
                info = _scan_with_env(st, project)
                existing = st.read_json("scan.json", default={}) or {}
                existing.update({k: v for k, v in info.items() if k != "risk"})
                st.write_json("scan.json", existing)
                if stage == "project_scan":
                    version = info.get("qt_version_hint") or "undetermined"
                    evidence = info.get("qt_version_evidence") or ""
                    print("[qt-ohos-run] build system: %s | qt: %s%s | "
                          "modules: %s | sources: %d" % (
                              info["build_system"], version,
                              (" (%s)" % evidence) if evidence else "",
                              ", ".join(info["qt_modules"]) or "-",
                              len(info["sources"])))
                    for warning in info.get("warnings", []):
                        print("[qt-ohos-run] WARNING: %s" % warning)
                st.complete_stage(stage, next_action="scan")
            elif stage == "risk_scan":
                info = st.read_json("scan.json", default={}) or {}
                engine = rule_engine.RuleEngine(KB_ROOT)
                risk = engine.scan(info, project)
                info["risk"] = risk
                st.write_json("scan.json", info)
                _print_risk_report(risk, args)
                st.complete_stage(stage, next_action="plan")
            elif stage == "dependency_scan":
                info = st.read_json("scan.json", default={}) or {}
                deps = dependency.analyze_dependencies(info, st)
                info["dependencies"] = deps
                st.write_json("scan.json", info)
                for dep in deps:
                    print("  dep %-10s %-16s %s" % (dep["name"], dep["status"],
                                                    dep["note"][:60]))
                st.complete_stage(stage, next_action="plan")
    except BudgetExhausted as exc:
        print("[qt-ohos-run] %s" % exc)
        return 2
    if not ran:
        # When all stages were done the old code exited silently: after changing code, a scan
        # that "did nothing" looks like it rescanned. Say clearly that it didn't, and how to.
        print("[qt-ohos-run] all scan stages already completed, not rescanned this time (last %s)"
              % (st.data.get("updated") or "?"))
        print("[qt-ohos-run] to rescan after code changes: add --force; if only config changed, "
              "`config set` invalidates the affected stages automatically")
        _emit(st.read_json("scan.json"), args)
        return 0
    # Every scan round leaves a trace: the old code overwrote everything, so when findings went from 237 to 766 between rounds there was no way to trace it.
    info = st.read_json("scan.json", default={}) or {}
    info["scan_round"] = int(info.get("scan_round") or 0) + 1
    info["scan_config_hash"] = _scan_config_hash(st, project)
    info["scanned_at"] = datetime.datetime.now().astimezone().isoformat(
        timespec="seconds")
    st.write_json("scan.json", info)
    if st.data.pop("scan_invalidated", None) is not None:
        st.save()
    _emit(info, args)
    return 0


def _scan_config_hash(st, project) -> str:
    """Hash the inputs that affect scan results into a fingerprint, to tell whether "what you see is the same round"."""
    import hashlib
    env = builder.env_of(st) or {}
    keys = ("qt_version", "qt_sdk_prefix", "build_cwd", "build_dir",
            "ohos_sdk_native", "ohos_arch", "cmake_args")
    payload = {"project": str(project), "env": {k: env.get(k) for k in keys},
               "kb": str(KB_ROOT)}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def cmd_plan(args):
    st = _state(args)
    st.check_budget()
    st.begin_stage("plan")
    info = st.read_json("scan.json", default={}) or {}
    if not info:
        print("[qt-ohos-run] run `scan` first")
        return 1
    plan = migration.build_plan(info, info.get("risk") or {},
                                info.get("dependencies") or [], kb_root=KB_ROOT,
                                env=builder.env_of(st))
    st.write_json("migration-plan.json", plan)
    st.complete_stage("plan", next_action="patch")
    info = st.read_json("scan.json", default={}) or {}
    if not info.get("qt_modules"):
        print("[qt-ohos-run] WARNING: the scan found no Qt modules (%s); "
              "the plan below may not apply - first check the project root is correct" %
              (info.get("build_system") or "no build files"))
    print("[qt-ohos-run] plan: %d steps (auto=%d assisted=%d manual=%d)" % (
        plan["counts"]["total"], plan["counts"]["auto"],
        plan["counts"]["assisted"], plan["counts"]["manual"]))
    for step in plan["steps"]:
        print("  [%s][%-8s] %s" % (step["id"], step["action"], step["title"]))
    _emit(plan, args)
    return 0


def cmd_patch(args):
    st = _state(args)
    st.check_budget()
    st.begin_stage("source_patch")
    info = st.read_json("scan.json", default={}) or {}
    tracker = ChangeTracker(st)
    applied = migration.apply_auto_fixes(info, st.project_root, tracker)
    patches = tracker.generate_patches()
    st.data["patches"] = patches
    st.complete_stage("source_patch", next_action="build")
    if applied:
        for fix in applied:
            print("[qt-ohos-run] applied %s -> %s (golden rule %s)" % (
                fix["fix"], fix["file"], fix["golden_rule"]))
    candidates = migration.fix_candidates(info, st.project_root)
    if not applied:
        print("[qt-ohos-run] no automatic fixes applicable")
    if candidates:
        print("[qt-ohos-run] candidate fixes (need human/agent judgment, not applied automatically):")
        for cand in candidates:
            print("  - [%s] %s" % (cand["rule"], cand["why"]))
            print("    fix: %s" % cand["fix"])
            if cand.get("evidence"):
                print("    evidence: %s" % cand["evidence"])
            for hit in cand["hits"][:3]:
                print("    location: %s:%d  %s" % (hit["file"], hit["line"],
                                              hit["snippet"]))
        st.data["fix_candidates"] = candidates
    else:
        st.data.pop("fix_candidates", None)
    st.save()
    if patches:
        print("[qt-ohos-run] patches: %s" % ", ".join(patches))
    _emit({"applied": applied, "patches": patches,
           "candidates": candidates}, args)
    return 0


def _record_external_package(st, args):
    """Record an external packaging result (HAP already produced by another process)."""
    project = Path(st.project_root)
    if not args.hap:
        print("[qt-ohos-run] package --record-only needs --hap <path>")
        return 2
    hap = Path(args.hap)
    if not hap.is_absolute():
        hap = project / hap
    build_json = st.read_json("build.json", default={}) or {}
    if not hap.is_file() or hap.stat().st_size == 0:
        build_json["package"] = {
            "command": "record-only (external package)", "status": "FAIL",
            "exit_code": 1, "stdout": "", "start_time": _now_iso(),
            "stderr": "HAP missing or empty: %s" % args.hap}
        st.write_json("build.json", build_json)
        st.fail_stage("package", error="record-only", next_action="package")
        print("[qt-ohos-run] recorded external package: FAIL (HAP missing or empty: %s)" % args.hap)
        return 1
    build_json["hap"] = hap.relative_to(project).as_posix() \
        if hap.is_relative_to(project) else str(hap)
    build_json["package"] = {
        "command": "record-only (external package)", "label": "package-recorded",
        "status": "PASS", "exit_code": 0, "stdout": "",
        "stderr": "", "evidence": str(hap), "start_time": _now_iso()}
    st.write_json("build.json", build_json)
    st.complete_stage("package", next_action="install")
    print("[qt-ohos-run] recorded external package: PASS (%s)" % build_json["hap"])
    return 0


def _record_external_build(st, args):
    """Record an external build result: don't rerun the build, just write the facts where the gates read them.

    Why: cross-compilation often runs its own script (build_ohos_k.py) or CI;
    rerunning it in the tool is slow and may not match the real artifacts. Previously the only way to make
    G3/G4 reflect the real state was to hand-write build.json - which bypasses the tool and leaves no evidence.
    """
    project = Path(st.project_root)
    patterns = args.artifacts or []
    found = []
    for pattern in patterns:
        for match in sorted(project.glob(pattern)):
            if match.is_file():
                found.append(match.relative_to(project).as_posix())
    found = found[:50]
    status = "PASS" if (args.status == "pass" and found) else "FAIL"
    reason = ""
    if args.status == "pass" and not patterns:
        reason = "record-only without --artifacts: unrecorded artifacts can't be checked, G4 will report missing artifacts"
    elif args.status == "pass" and not found:
        reason = ("record-only claims the build succeeded, but --artifacts matched no files: %s"
                  % ", ".join(patterns))
    evidence = ""
    if args.log:
        log_path = Path(args.log)
        if not log_path.is_absolute():
            log_path = project / log_path
        evidence = str(log_path) if log_path.exists() else ""
        if args.log and not evidence:
            reason = (reason + "; " if reason else "") + \
                "the log given by --log does not exist: %s" % args.log
    build_json = st.read_json("build.json", default={}) or {}
    build_json["mode"] = "recorded"
    build_json["compile"] = {
        "command": "record-only (external build)", "label": "build-recorded",
        "status": status, "exit_code": 0 if status == "PASS" else 1,
        "stdout": "", "stderr": reason,
        "evidence": evidence, "start_time": _now_iso(),
    }
    build_json["artifacts"] = found
    st.write_json("build.json", build_json)
    if status == "PASS":
        st.complete_stage("compile", next_action="package")
        print("[qt-ohos-run] recorded external build: PASS, %d artifacts%s" % (
            len(found), " (evidence: %s)" % evidence if evidence else ""))
        for rel in found[:5]:
            print("  %s" % rel)
        return 0
    st.fail_stage("compile", error="record-only", next_action="build")
    print("[qt-ohos-run] recorded external build: FAIL (%s)" % (reason or "status=fail"))
    return 1


def cmd_build(args):
    st = _state(args)
    if getattr(args, "record_only", False):
        return _record_external_build(st, args)
    st.check_budget()
    st.begin_stage("compile")
    result = builder.configure_and_build(st, timeout=args.timeout)
    if result.status == "PASS":
        st.complete_stage("compile", next_action="package")
    else:
        hits = error_engine.ErrorEngine(KB_ROOT).analyze(
            result.stdout + "\n" + result.stderr, stage_hint="build")
        if hits:
            print("[qt-ohos-run] error-engine hits:")
            for hit in hits[:5]:
                print("  %-8s %-30s %.2f" % (hit["id"], hit.get("name"),
                                              hit["score"]))
        st.fail_stage("compile", error=(hits[0]["id"] if hits else result.status),
                      next_action="analyze-log then build")
    print("[qt-ohos-run] compile: %s (%.1fs)" % (result.status, result.duration))
    return 0 if result.status == "PASS" else 1


def cmd_package(args):
    st = _state(args)
    if getattr(args, "record_only", False):
        return _record_external_package(st, args)
    st.check_budget()
    st.begin_stage("package")
    result = builder.package_hap(st, timeout=args.timeout)
    if result.status == "PASS":
        st.complete_stage("package", next_action="install")
        print("[qt-ohos-run] HAP: %s" % st.read_json("build.json")["hap"])
        return 0
    st.fail_stage("package", error=result.status, next_action="package")
    print("[qt-ohos-run] package: %s" % result.status)
    return 1


def cmd_install(args):
    st = _state(args)
    st.check_budget()
    st.begin_stage("install")
    result = builder.install_hap(st, timeout=args.timeout)
    if result.status == "PASS":
        st.complete_stage("install", next_action="launch")
    else:
        st.fail_stage("install", error=result.status, next_action="install")
    print("[qt-ohos-run] install: %s" % result.status)
    return 0 if result.status == "PASS" else 1


def cmd_launch(args):
    st = _state(args)
    st.check_budget()
    st.begin_stage("launch")
    result = builder.launch_app(st, timeout=args.timeout)
    if result.status == "PASS":
        builder.check_ui_window(st)          # G9 evidence
        st.complete_stage("launch", next_action="smoke")
    else:
        st.fail_stage("launch", error=result.status, next_action="launch")
    print("[qt-ohos-run] launch: %s" % result.status)
    return 0 if result.status == "PASS" else 1


def cmd_smoke(args):
    st = _state(args)
    st.check_budget()
    st.begin_stage("smoke")
    runtime = st.read_json("runtime.json", default={}) or {}
    if args.result:
        runtime["smoke"] = {"status": args.result.upper(),
                            "note": args.note or "", "manual": True}
        st.write_json("runtime.json", runtime)
        st.complete_stage("smoke", next_action="verify")
        print("[qt-ohos-run] smoke recorded: %s" % args.result.upper())
        return 0
    result = builder.crash_check(st, timeout=args.timeout)
    print("[qt-ohos-run] crash window: %s (%s)" % (result.status, result.stderr))
    if result.status == "PASS":
        st.complete_stage("smoke", next_action="verify")
        return 0
    if result.status in ("SKIP", "NOT_RUN"):
        # Not installed / not launched / no logs from this app captured: that is "not tested", not "passed".
        st.fail_stage("smoke", error="not-run:%s" % result.status,
                      next_action="install+launch")
        print("[qt-ohos-run] smoke not run (%s) - get install/launch to pass first, "
              "or check that bundle_name matches the hilog output" % result.status)
        return 2
    st.fail_stage("smoke", error="crash-detected", next_action="analyze-log")
    return 1


def cmd_verify(args):
    st = _state(args)
    _warn_stale_scan(st)
    gates, overall = verifier.evaluate(st)
    st.data["gates"] = gates
    st.data["overall"] = overall
    st.save()
    _say(args, verifier.render(gates, overall))
    _emit({"gates": gates, "overall": overall}, args)
    return {"PASS": 0, "PARTIAL": 3}.get(overall, 1)


def cmd_analyze_log(args):
    # Log analysis doesn't depend on project state: only write back the error field when --project is given
    # explicitly; otherwise don't mislead a user who just wants to read a log with "init first".
    st = None
    if getattr(args, "project", None):
        try:
            st = _state(args)
        except SystemExit:
            st = None
    engine = error_engine.ErrorEngine(KB_ROOT)
    hits = engine.analyze_file(args.logfile)
    if not hits:
        print("[qt-ohos-run] no known error patterns matched")
        # Link-time undefined symbols are the most common "nobody implemented it" in mid-porting; there's no
        # fixed error code to match (symbol names vary endlessly), so point to the tool that can actually narrow it down.
        try:
            raw = Path(args.logfile).read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
        if "undefined symbol" in raw or "undefined reference" in raw:
            print("[qt-ohos-run] the log has undefined symbol/reference: use\n"
                  "  python tools/ohos-platform-audit.py <platform dir> "
                  "--undefined %s\n"
                  "to tell 'not yet implemented in the platform layer' from 'third-party library/toolchain problem'" % args.logfile)
        if st is not None:
            print("[qt-ohos-run] consider: qt-ohos-run draft \"<new problem>\"")
        return 1
    print("Hits:")
    for hit in hits[:10]:
        print("  %-8s %-34s %.2f  [%s]" % (hit["id"], hit.get("name"),
                                            hit["score"], hit["severity"]))
    top = hits[0]
    print("\nTop hit: %s (%s)" % (top["id"], top.get("name")))
    for cause in top.get("root_causes", []):
        print("  cause   : %s" % cause)
    for step in top.get("diagnosis", []):
        print("  diagnose: %s" % step)
    for solution in top.get("solutions", []):
        print("  fix     : %s" % solution)
    refs = top.get("refs") or {}
    for ref in (refs.get("problems") or []) + (refs.get("kb") or []):
        print("  read    : %s" % ref)
    if st is not None:
        st.data["current"]["error"] = top["id"]
        st.save()
    _emit(hits, args)
    return 0


def _warn_stale_scan(st) -> None:
    """When scan results are stale, say so first; otherwise status/verify show old facts."""
    stale = st.data.get("scan_invalidated")
    info = st.read_json("scan.json", default={}) or {}
    reason = ""
    if stale:
        reason = "%s changed %s" % (stale.get("at") or "?", ", ".join(
            stale.get("keys") or []))
    elif info and info.get("scan_config_hash"):
        try:
            current = _scan_config_hash(st, Path(st.data.get("project") or "."))
        except Exception:
            current = ""
        if current and current != info["scan_config_hash"]:
            reason = "current config differs from the one used at scan time"
    if reason:
        print("[qt-ohos-run] WARNING: scan results are stale (%s); "
              "run `scan` (or `scan --force`) before trusting these numbers" % reason,
              file=sys.stderr)


def cmd_status(args):
    st = _state(args)
    _warn_stale_scan(st)
    data = st.data
    print("project : %s" % data.get("project"))
    print("stage   : %s" % data.get("stage"))
    print("current : %s" % json.dumps(data.get("current"), ensure_ascii=False))
    print("next    : %s" % json.dumps(data.get("next"), ensure_ascii=False))
    print("completed: %s" % ", ".join(data.get("completed", [])) or "-")
    remaining = st.remaining_stages()
    print("remaining: %s" % (", ".join(remaining) if remaining else "(none)"))
    if data.get("gates"):
        print("")
        print(verifier.render(data["gates"], data.get("overall", "?")))
    _emit(data, args)
    return 0


def cmd_resume(args):
    st = _state(args)
    st.reset_budget_session()
    remaining = st.remaining_stages()
    if not remaining:
        print("[qt-ohos-run] all stages completed; run `verify` / `finish`")
        return 0
    print("[qt-ohos-run] resuming; completed=%s" %
          ", ".join(st.data.get("completed", [])) or "-")
    print("[qt-ohos-run] remaining: %s" % ", ".join(remaining))
    print("[qt-ohos-run] next action: %s" % st.data.get("next", {}).get("action"))
    if args.run:
        return _run_pipeline(st, args)
    return 0


def cmd_migrate(args):
    _apply_positional(args)
    _require_explicit_project(args, "migrate")
    project = _resolve_project(args, required=True)
    st = (state_mod.init_state(project)
          if not (project / state_mod.STATE_DIR_NAME / "state.json").exists()
          else state_mod.load_state(project))
    st.reset_budget_session()
    try:
        rc = _run_pipeline(st, args)
    except BudgetExhausted as exc:
        print("[qt-ohos-run] %s" % exc)
        return 2
    # always finish with verification + report
    cmd_verify(args) if not args.no_verify else None
    _do_finish(st, args)
    return rc


def _run_pipeline(st: MigrationState, args) -> int:
    """Run remaining automatable stages in order."""
    project = st.project_root
    rc = 0
    stages_left = st.remaining_stages()

    def stage_done(name):
        return name not in st.remaining_stages()

    try:
        if not stage_done("env_check"):
            st.check_budget()
            st.begin_stage("env_check")
            if not builder.env_of(st):
                _import_env_local(st)
            st.complete_stage("env_check", next_action="scan")

        if not stage_done("project_scan") or not stage_done("qt_scan"):
            st.check_budget()
            st.begin_stage("project_scan")
            info = scanner.scan_project(project)
            existing = st.read_json("scan.json", default={}) or {}
            existing.update({k: v for k, v in info.items() if k != "risk"})
            st.write_json("scan.json", existing)
            st.complete_stage("project_scan", next_action="scan")
            st.complete_stage("qt_scan", next_action="scan")
            print("[qt-ohos-run] scanned: %s (%s, modules: %s)" % (
                info["name"], info["build_system"],
                ", ".join(info["qt_modules"]) or "-"))

        if not stage_done("risk_scan"):
            st.check_budget()
            st.begin_stage("risk_scan")
            info = st.read_json("scan.json", default={}) or {}
            risk = rule_engine.RuleEngine(KB_ROOT).scan(info, project)
            info["risk"] = risk
            st.write_json("scan.json", info)
            _print_risk_report(risk, args)
            st.complete_stage("risk_scan", next_action="plan")

        if not stage_done("dependency_scan"):
            st.check_budget()
            st.begin_stage("dependency_scan")
            info = st.read_json("scan.json", default={}) or {}
            info["dependencies"] = dependency.analyze_dependencies(info, st)
            st.write_json("scan.json", info)
            st.complete_stage("dependency_scan", next_action="plan")

        if not stage_done("assess"):
            # feasibility gate: blocked projects stop here with a report
            st.check_budget()
            st.begin_stage("assess")
            info = st.read_json("scan.json", default={}) or {}
            recipes = knowledge.similar_recipes(KB_ROOT, info)
            assessment = assessor.evaluate(KB_ROOT, info, info.get("risk"),
                                           recipes, project_root=project)
            info["assessment"] = assessment
            st.write_json("scan.json", info)
            st.write_json("assessment.json", assessment)
            print(assessor.render(assessment))
            if assessment["verdict"] == "blocked":
                st.fail_stage("assess", error="feasibility-blocked",
                              next_action="resolve blockers (see assessment.json)")
                return 1
            st.complete_stage("assess", next_action="plan")

        if not stage_done("plan"):
            st.check_budget()
            st.begin_stage("plan")
            info = st.read_json("scan.json", default={}) or {}
            plan = migration.build_plan(info, info.get("risk") or {},
                                        info.get("dependencies") or [],
                                        kb_root=KB_ROOT, env=builder.env_of(st))
            st.write_json("migration-plan.json", plan)
            st.complete_stage("plan", next_action="patch")
            print("[qt-ohos-run] plan: %d steps" % plan["counts"]["total"])

        if not stage_done("project_generation"):
            # INIT3 fix: auto-generate the shell from the bundled template;
            # fall back to the assisted pause when no template is available
            st.begin_stage("project_generation")
            if (project / "entry").is_dir() or getattr(
                    args, "assume_project_ready", False):
                st.complete_stage("project_generation", next_action="patch")
            elif _generate_shell_project(st, project):
                st.complete_stage("project_generation", next_action="patch")
            else:
                print("[qt-ohos-run] project_generation is assisted - create "
                      "the HarmonyOS entry module from OHOS_TEMPLATE_SRC "
                      "(qtbase/src/harmonyos/templates) or "
                      "templates/qt-ohos-app, then continue")
                st.data["next"] = {"action": "create HarmonyOS shell, then resume"}
                st.save()
                return 0

        if not stage_done("source_patch"):
            st.check_budget()
            st.begin_stage("source_patch")
            info = st.read_json("scan.json", default={}) or {}
            tracker = ChangeTracker(st)
            applied = migration.apply_auto_fixes(info, project, tracker)
            st.data["patches"] = tracker.generate_patches()
            st.complete_stage("source_patch", next_action="build")
            print("[qt-ohos-run] auto fixes applied: %d" % len(applied))

        env = builder.env_of(st)
        device_steps = {"compile": lambda: builder.configure_and_build(
                            st, timeout=args.timeout),
                        "package": lambda: builder.package_hap(
                            st, timeout=args.timeout),
                        "install": lambda: builder.install_hap(
                            st, timeout=args.timeout),
                        "launch": lambda: builder.launch_app(
                            st, timeout=args.timeout),
                        "smoke": lambda: builder.crash_check(
                            st, timeout=args.timeout)}
        broken = None
        for stage_name, fn in device_steps.items():
            if stage_done(stage_name):
                continue
            if broken:
                # Upstream already failed: carrying on only produces a chain of knock-on failures and mixes
                # "not tested" into the report. Record it explicitly as not tested and stop the chain.
                st.skip_cmd(stage_name, "skipped: upstream %s did not pass" % broken)
                st.fail_stage(stage_name, error="upstream:%s" % broken,
                              next_action="fix %s" % broken)
                print("[qt-ohos-run] %s: SKIP (upstream %s did not pass)"
                      % (stage_name, broken))
                rc = max(rc, 2)
                continue
            st.check_budget()
            st.begin_stage(stage_name)
            if stage_name == "compile" and not (env.get("build_command") or
                                                env.get("qt_sdk_prefix")):
                st.skip_cmd("compile", "env.json not configured (build_command / "
                            "qt_sdk_prefix missing)")
                st.fail_stage("compile", error="env-not-configured",
                              next_action="config set ...")
                print("[qt-ohos-run] compile skipped: env.json not configured")
                rc = 1
                broken = "compile"
                continue
            result = fn()
            if stage_name == "launch" and result.status == "PASS":
                # G9 evidence: dump the layout tree right after a good launch
                builder.check_ui_window(st)
            if result.status == "PASS":
                st.complete_stage(stage_name, next_action="verify")
                print("[qt-ohos-run] %s: PASS" % stage_name)
            elif result.status in ("SKIP", "NOT_RUN"):
                st.fail_stage(stage_name, error="not-run:%s" % result.status,
                              next_action="install+launch")
                print("[qt-ohos-run] %s: %s (not run, which is not a pass)"
                      % (stage_name, result.status))
                rc = max(rc, 2)
                if stage_name in ("compile", "package"):
                    broken = stage_name
            else:
                st.fail_stage(stage_name, error=result.status,
                              next_action="analyze-log")
                print("[qt-ohos-run] %s: %s" % (stage_name, result.status))
                rc = max(rc, 1)
                if stage_name in ("compile", "package"):
                    broken = stage_name
    except BudgetExhausted:
        raise
    return rc


def cmd_finish(args):
    st = _state(args)
    _do_finish(st, args)
    return 0


def _do_finish(st: MigrationState, args):
    st.check_budget()
    st.begin_stage("report")
    info = st.read_json("scan.json", default={}) or {}
    risk = info.get("risk") or {}
    plan = st.read_json("migration-plan.json", default={}) or {}
    deps = info.get("dependencies") or []
    gates, overall = verifier.evaluate(st)
    st.data["gates"] = gates
    st.data["overall"] = overall

    tracker = ChangeTracker(st)
    changes = tracker.all_changes()
    patches = st.data.get("patches") or []
    recipes = knowledge.similar_recipes(KB_ROOT, info)

    hits = []
    runtime = st.read_json("runtime.json", default={}) or {}
    for key in ("compile", "install", "launch", "crash_check"):
        records = []
        record = (st.read_json("build.json", default={}) or {}).get(key) or \
            runtime.get(key)
        if record:
            records.append(record)
        for rec in records:
            if rec.get("status") not in (None, "PASS"):
                text = (rec.get("stdout") or "") + "\n" + (rec.get("stderr") or "")
                hits.extend(error_engine.ErrorEngine(KB_ROOT).analyze(text))
    hits.sort(key=lambda h: -h["score"])
    seen = set()
    hits = [h for h in hits if not (h["id"] in seen or seen.add(h["id"]))]

    report_text = report.build_report(st, info, plan, risk, deps, gates, overall,
                                      changes, patches, recipes, hits)
    report_path = st.state_dir / "report.md"
    report_path.write_text(report_text, encoding="utf-8")
    st.complete_stage("report", next_action="knowledge")
    print("[qt-ohos-run] report: %s (overall=%s)" % (report_path, overall))

    # knowledge stage: prompt distillation, never silent
    st.begin_stage("knowledge")
    drafts = st.data.get("drafts") or []
    if not drafts:
        print("[qt-ohos-run] knowledge: no drafts yet. If anything NEW was "
              "learned, run: qt-ohos-run draft \"<title>\"")
    else:
        st.complete_stage("knowledge", next_action="done")
    st.save()
    _emit({"report": str(report_path), "overall": overall}, args)


def cmd_draft(args):
    summary = args.summary or ""
    if getattr(args, "summary_file", None):
        # PowerShell splits a long Chinese summary into several arguments; reading from a file is the only reliable channel
        summary = Path(args.summary_file).read_text(encoding="utf-8").strip()
    path = knowledge.create_draft(KB_ROOT, args.title, summary=summary,
                                  symptom=args.symptom or "", log=args.log or "",
                                  tags=args.tag or [])
    print("[qt-ohos-run] draft created: %s" % path)
    print("[qt-ohos-run] fill it in, then: qt-ohos-run promote %s" % path.stem)
    # SED1 fix: record the draft in the migration state so `finish` can see it
    # and the knowledge stage can complete.
    try:
        st = _state(args)
    except SystemExit:
        st = None
    if st is not None:
        drafts = st.data.setdefault("drafts", [])
        record = {"id": path.stem, "path": str(path),
                  "title": args.title, "created": st.data.get("updated")}
        if record not in drafts:
            drafts.append(record)
        if st.data.get("stage") == "knowledge":
            st.complete_stage("knowledge", next_action="done")
        else:
            st.save()
    return 0


def cmd_promote(args):
    target = knowledge.promote_draft(KB_ROOT, args.draft_id)
    print("[qt-ohos-run] promoted: %s" % target)
    print("[qt-ohos-run] next: edit problems page (root cause/solution) and "
          "knowledge/errors/%s.yaml (patterns), then regenerate indexes"
          % args.draft_id.upper())
    return 0


def cmd_recipes(args):
    _apply_positional(args)
    _require_explicit_project(args, "recipes")
    if getattr(args, "project", None):
        project = _resolve_project(args, required=True)
        try:
            st = state_mod.load_state(project)
            info = st.read_json("scan.json", default={}) or {}
        except FileNotFoundError:
            info = scanner.scan_project(project)
    else:
        info = {"qt_modules": [], "build_system": "", "third_party_hints": []}
    results = knowledge.similar_recipes(KB_ROOT, info)
    if not results:
        print("[qt-ohos-run] no similar historical migrations found")
        return 0
    print("Historical Migration Similarity")
    for item in results:
        print("  %.2f  %-40s %s" % (item["score"], item["case"],
                                    item["summary"][:60]))
    _emit(results, args)
    return 0


# ---- Keys that only affect runtime behavior: changing them needs no project rescan ----------
# The old code invalidated the scan on any change, so "just changing the hdc path" meant a 12-second rescan,
# and users naturally learned to bypass config. Runtime keys and project-fact keys must be kept apart.
# These keys hold lists: `config set hap_allowed_libs libssl.so.3,libcrypto.so.3`
# must be stored as a list; stored as a string it gets expanded per character downstream ("l" allows every lib*).
LIST_KEYS = {"hap_allowed_libs", "undefined_allow", "cmake_args"}


def _split_list_value(key: str, raw: str):
    """Split a command-line value into a list, rejecting short prefixes that would allow half the system."""
    if key not in LIST_KEYS:
        return None
    items = [item for item in re.split(r"[,;\s]+", str(raw)) if item]
    if key in ("hap_allowed_libs", "undefined_allow"):
        kept, rejected = [], []
        for item in items:
            (kept if len(item) >= 4 else rejected).append(item)
        if rejected:
            print("[qt-ohos-run] ignoring too-short prefixes (would allow too many libraries): %s"
                  % ", ".join(rejected), file=sys.stderr)
        return kept
    return items


RUNTIME_KEYS = {
    "hdc", "bundle_name", "ability_name", "package_dir", "build_dir",
    "harmonyos_build", "hvigor", "java_home", "deveco_sdk_home", "hvigor_home",
    "npm_cache", "device_sdk", "compatible_sdk", "hap_glob", "crash_wait_sec",
    "process_name", "hdc_serial", "devecocli", "timeout_sec", "package_target",
    "package_command", "build_command", "auto_package", "hap_allowed_libs",
}


def cmd_config(args):
    st = _state(args)
    env = builder.env_of(st)
    if args.config_action == "show":
        print(json.dumps(env, ensure_ascii=False, indent=2))
        return 0
    if args.config_action == "set":
        if not args.key or args.value is None:
            print("[qt-ohos-run] usage: config set <key> <value>", file=sys.stderr)
            return 2
        as_list = _split_list_value(args.key, args.value)
        if as_list is not None:
            env[args.key] = as_list
        elif args.value.lower() in ("true", "false"):
            env[args.key] = args.value.lower() == "true"
        else:
            env[args.key] = args.value
        st.write_json("env.json", env)
        print("[qt-ohos-run] env.json: %s = %s" % (args.key, args.value))
        if args.key in RUNTIME_KEYS or args.no_invalidate:
            print("[qt-ohos-run] runtime key, scan results remain valid")
            return 0
        # A project fact changed (qt_version / source path etc.), so earlier scan results are stale.
        invalidated = st.invalidate_scan_stages()
        if invalidated:
            import datetime as _dt
            st.data["scan_invalidated"] = {
                "at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "keys": sorted(set((st.data.get("scan_invalidated") or {}).get(
                    "keys", []) + [args.key])),
            }
            st.save()
            print("[qt-ohos-run] scan state invalidated (%s)" % ", ".join(invalidated))
        if getattr(args, "rescan", False):
            scan_args = argparse.Namespace(**vars(args))
            code = cmd_scan(scan_args)
            return code
        print("[qt-ohos-run] the next scan will rescan; to skip that use "
              "`config set <key> <value> --no-invalidate` (runtime keys only)")
        return 0
    return 1


def _probe(name: str, ok: bool, detail: str, fix: str = "",
           partial: bool = False) -> dict:
    status = "PASS" if ok else ("PARTIAL" if partial else "FAIL")
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _which_or(value) -> str:
    return value if value else ""


def cmd_doctor(args):
    """Environment self-check: ask about every "blows up only at run time" prerequisite at once, each with an actionable fix.

    These checks all come from real pitfalls (Qt6 prebuilt kit / the five hvigor essentials / SDK version / device chain);
    they used to be scattered across knowledge pages, and porters had to work back from failure logs one by one.
    """
    import shutil as _shutil
    import subprocess as _subprocess
    import types

    # doctor must also work on a project where "nothing has been init-ed yet": without a state dir it probes read-only,
    # and never creates .qt-ohos/ in someone else's project just for a check-up.
    root = Path(getattr(args, "project", None) or ".").resolve()
    st = None
    if (root / state_mod.STATE_DIR_NAME).is_dir():
        try:
            st = _state(args)
        except SystemExit:
            st = None
    env_file = root / state_mod.STATE_DIR_NAME / "env.json"
    if st is not None:
        env = builder.env_of(st)
    elif env_file.is_file():
        try:
            env = json.loads(env_file.read_text(encoding="utf-8"))
        except ValueError:
            env = {}
    else:
        env = {}
    probe = st if st is not None else types.SimpleNamespace(project_root=root)
    checks = []

    cmake = env.get("cmake") or _shutil.which("cmake") or ""
    checks.append(_probe("cmake", bool(cmake), cmake or "not found",
                         "config set cmake <absolute cmake path>"))

    # The kit ships mingw32-make but it's not on PATH: looking only at PATH makes doctor and the builder
    # give two different answers (the builder falls back to Ninja, doctor reports "make not installed").
    make = builder.mingw32_make(env) or _shutil.which("ninja") or \
        _shutil.which("make") or ""
    checks.append(_probe("build tool", bool(make), make or "not found",
                         "on Windows use the kit's own mingw_64/bin/mingw32-make; "
                         "config set make_program <path>"))

    qt = env.get("qt_sdk_prefix") or ""
    toolchain = Path(qt) / "lib" / "cmake" / "Qt6" / "qt.toolchain.cmake" \
        if qt else None
    checks.append(_probe(
        "Qt kit", bool(toolchain and toolchain.is_file()),
        str(toolchain) if toolchain else "qt_sdk_prefix not configured",
        "config set qt_sdk_prefix <kit root> (a Qt6 kit must contain "
        "lib/cmake/Qt6/qt.toolchain.cmake)"))

    if toolchain and toolchain.is_file():
        platform = Path(qt) / "plugins" / "platforms" / "libqohos.so"
        checks.append(_probe("Qt OHOS platform plugin", platform.is_file(),
                             str(platform),
                             "this kit is not an OHOS build (missing plugins/platforms/libqohos.so)"))
        host = env.get("qt_host_sdk") or ""
        moc = Path(host) / "bin" / ("moc.exe" if os.name == "nt" else "moc") \
            if host else None
        checks.append(_probe(
            "host kit", bool(moc and moc.is_file()),
            str(moc) if moc else "qt_host_sdk not configured",
            "config set qt_host_sdk <host kit root> (QT_HOST_PATH for Qt6 cross-compilation)"))

    native = env.get("ohos_sdk_native") or ""
    chainload = Path(native) / "build" / "cmake" / "ohos.toolchain.cmake" \
        if native else None
    checks.append(_probe(
        "OHOS native SDK", bool(chainload and chainload.is_file()),
        str(chainload) if (chainload and chainload.is_file()) else "not configured/incomplete",
        "config set ohos_sdk_native <SDK>/native"))

    sysroot = Path(native) / "sysroot" / "usr" / "lib" \
        / (env.get("ohos_arch") or "arm64-v8a") if native else None
    checks.append(_probe(
        "sysroot (G13 unresolved-symbol check)", bool(sysroot and sysroot.is_dir()),
        str(sysroot) if sysroot else "ohos_sdk_native not configured",
        "G13 needs it to judge unresolved symbols: with it, reports PARTIAL as advisory; without it, can only SKIP",
        partial=True))

    sdk_version = builder._sdk_from_sdk_home(env)
    checks.append(_probe(
        "SDK version", bool(sdk_version), sdk_version or "cannot read oh-uni-package.json",
        "config set deveco_sdk_home <command-line-tools>/sdk"))

    hvigor = builder.find_hvigor(env)
    checks.append(_probe(
        "hvigorw", bool(hvigor), hvigor or "not found",
        "config set hvigor <DevEco>/tools/hvigor/bin/hvigorw.bat (absolute path)"))

    extra = builder.hvigor_env(probe, env, create=False)
    checks.append(_probe("JAVA_HOME", "JAVA_HOME" in extra,
                         extra.get("JAVA_HOME", "not found (DevEco ships a jbr)"),
                         "config set java_home <DevEco>/jbr"))
    checks.append(_probe("HVIGOR_USER_HOME", "HVIGOR_USER_HOME" in extra,
                         extra.get("HVIGOR_USER_HOME", ""),
                         "config set hvigor_home <absolute writable path>"))
    def _writable(path) -> bool:
        """If the directory doesn't exist yet, check the nearest existing ancestor: a check-up shouldn't create directories."""
        if not str(path):
            return False
        current = Path(path)
        while not current.exists() and current != current.parent:
            current = current.parent
        return current.is_dir() and os.access(current, os.W_OK)

    writable = _writable(extra.get("npm_config_cache"))
    checks.append(_probe("npm cache writable", writable,
                         extra.get("npm_config_cache", ""),
                         "config set npm_cache <absolute writable path>"))

    # pkg-config: Windows hosts don't ship it, and the .pc files of HarmonyOS artifacts contain build-machine
    # absolute paths (`prefix=/storage/Users/...`); together these make every pkg_check_modules
    # fail. A shim also counts as passing - this tool implements the query semantics.
    shim = root / ".qt-ohos" / "bin" / ("pkg-config.bat" if os.name == "nt"
                                       else "pkg-config")
    pkgconfig_bin = _shutil.which("pkg-config") or (
        str(shim) if shim.is_file() else None)
    libs_dir = _pkgconfig_libs_dir(args)
    pc_count = 0
    if libs_dir.is_dir():
        pc_count = sum(1 for _ in libs_dir.rglob("pkgconfig/*.pc"))
    checks.append(_probe(
        "pkg-config", bool(pkgconfig_bin or pc_count),
        pkgconfig_bin or ("%d .pc files, but no pkg-config on PATH" % pc_count
                          if pc_count else "not found"),
        "pkgconfig --write-shim to generate a stand-in, then pkgconfig --relocate "
        "to rewrite the build-machine absolute paths in the .pc files",
        partial=not pkgconfig_bin))

    hdc = env.get("hdc") or find_hdc()
    checks.append(_probe("hdc", bool(hdc), hdc or "not found",
                         "config set hdc <command-line-tools>/sdk/default/openharmony/toolchains/hdc"))
    if hdc:
        if st is not None:
            targets = st.run_cmd([hdc, "list", "targets"],
                                 label="hdc-list-targets", timeout=60)
            target_out = targets.stdout or ""
        else:
            try:
                target_out = _subprocess.run(
                    [hdc, "list", "targets"], capture_output=True,
                    timeout=60).stdout.decode("utf-8", "replace")
            except (OSError, _subprocess.SubprocessError):
                target_out = ""
        lines = [ln for ln in target_out.splitlines()
                 if ln.strip() and not ln.lower().startswith("[empty]")]
        checks.append(_probe("device", bool(lines), ", ".join(lines) or "no device",
                             "hdc list targets is empty: check USB debugging/authorization"))

    checks.append(_probe("bundle_name", bool(env.get("bundle_name")),
                         env.get("bundle_name", "not configured"),
                         "config set bundle_name <bundle>"))
    ability = env.get("ability_name") or builder.detect_ability(probe, env)
    checks.append(_probe("ability", bool(ability), ability or "not found",
                         "resolved automatically after package; or config set ability_name <name>"))

    cli = builder.find_devecocli(env)
    checks.append(_probe("devecocli", bool(cli), cli or "not found (optional, used for signing/screenshots)",
                         "npm i -g @deveco/deveco-cli", partial=True))

    failures = [c for c in checks if c["status"] == "FAIL"]
    partials = [c for c in checks if c["status"] == "PARTIAL"]
    lines = ["%s %s: %s" % ("[PASS]" if c["status"] == "PASS"
                            else ("[WARN]" if c["status"] == "PARTIAL"
                                  else "[FAIL]"),
                            c["name"], c["detail"])
             for c in checks]
    for c in checks:
        if c["status"] != "PASS" and c["fix"]:
            lines.append("       fix: %s" % c["fix"])
    lines.append("doctor: %d PASS / %d WARN / %d FAIL"
                 % (len(checks) - len(failures) - len(partials),
                    len(partials), len(failures)))
    _say(args, "\n".join(lines))
    _emit({"checks": checks, "failures": len(failures)}, args)
    return 1 if failures else 0


def cmd_sign(args):
    """Signing: prefer letting devecocli generate it; when materials are missing, print the manual six-item checklist."""
    st = _state(args)
    env = builder.env_of(st)
    cli = builder.find_devecocli(env)
    if not cli:
        print("[qt-ohos-run] devecocli not found, signing needs the six items configured manually:\n"
              "  --signing-cert-path / --signing-profile / --signing-store-file\n"
              "  --signing-key-alias / --signing-key-password / --signing-store-password\n"
              "see procedural/qt6-ohos-windows-cli-deploy.md §7.1 Command-line signing",
              file=sys.stderr)
        return 2
    argv = [cli, "signature", "generate",
            "--product", args.product or "default",
            "--type", args.type]
    if args.force:
        argv.append("--force")
    result = st.run_cmd(argv, label="devecocli-signature", timeout=args.timeout,
                        cwd=st.project_root)
    print("[qt-ohos-run] signature: %s" % result.status)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.status != "PASS":
        print(result.stderr.strip(), file=sys.stderr)
        return 1
    # Generating the materials isn't enough: they only take effect once products[].signingConfig references signingConfigs
    profile = None
    for directory in builder._package_dirs(st, env) or [Path(st.project_root)]:
        candidate = directory / "build-profile.json5"
        if candidate.is_file():
            profile = candidate
            break
    if profile is None:
        print("[qt-ohos-run] build-profile.json5 not found: signing materials were generated but not wired into the project",
              file=sys.stderr)
        return 1
    data = builder.read_json5(profile)
    text = profile.read_text(encoding="utf-8", errors="replace")
    referenced = bool(re.search(r'"signingConfig"\s*:\s*"', text))
    print("[qt-ohos-run] %s: signingConfigs=%s, referenced by products=%s"
          % (profile.as_posix(),
             bool(data and data.get("app", {}).get("signingConfigs")),
             referenced))
    return 0 if referenced else 1


def cmd_smoke_interact(args):
    st = _state(args)
    result = builder.smoke_interact(st, timeout=args.timeout)
    _say(args, "[qt-ohos-run] smoke-interact: %s\n%s\n%s"
         % (result.status, result.stdout, result.stderr))
    _emit({"status": result.status, "stdout": result.stdout}, args)
    code = {"PASS": 0, "PARTIAL": 3}.get(result.status, 1)
    if result.status in ("SKIP", "NOT_RUN"):
        code = 2
    return code


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _pkgconfig_libs_dir(args):
    """Pick the ohos-libs directory: --libdir > env.package_libs > <project>/ohos-libs."""
    if getattr(args, "libdir", None):
        return Path(args.libdir).expanduser()
    root = Path(getattr(args, "project", None) or os.getcwd())
    env = {}
    if (root / ".qt-ohos").is_dir():
        try:
            env = _state(args).read_json("env.json", default={}) or {}
        except SystemExit:
            env = {}
    for key in ("ohos_libs", "package_libs", "libs_dir"):
        val = env.get(key)
        if val:
            return Path(val).expanduser()
    return root / "ohos-libs"


def cmd_pkgconfig(args):
    """pkg-config stand-in entry point (see the module docstring of tools/qt_ohos/pkgconfig.py).

    Windows hosts have no pkg-config by default, and the `.pc` files of HarmonyOS artifacts contain build-machine
    absolute paths: together these make every CMake `pkg_check_modules` fail
    (in tdesktop all 377 .pc files were broken). The three actions are separate so they can slot in
    after fetch and before configure:
      --relocate   rewrite prefixes (idempotent, can be rerun)
      --write-shim generate pkg-config / pkg-config.bat
      (no args)    pass through to pkg-config query semantics
    """
    from qt_ohos import pkgconfig as pc

    libs_dir = _pkgconfig_libs_dir(args)
    if args.relocate is not None:
        target = Path(args.relocate).expanduser() if args.relocate else libs_dir
        if not target.is_dir():
            print("[pkgconfig] directory does not exist: %s" % target, file=sys.stderr)
            return 2
        out = pc.relocate_tree(target, dry_run=args.dry_run)
        for c in out["changed"]:
            print("%s %s (%d places)" % (
                "would rewrite" if args.dry_run else "relocated", c["path"],
                len(c["notes"])))
            for note in c["notes"][:5]:
                print("  " + note)
        print("pkgconfig: scanned %d .pc, %s %d, local packages %d" % (
            out["scanned"], "to rewrite" if args.dry_run else "rewrote",
            len(out["changed"]), len(out["local_packages"])))
        if not out["scanned"]:
            print("hint: no *.pc under this directory (expected in <pkg>/<ver>/lib/pkgconfig/); "
                  "make sure fetch-deps has run", file=sys.stderr)
        return 0

    if args.write_shim is not None:
        bin_dir = (Path(args.write_shim).expanduser() if args.write_shim
                   else Path(getattr(args, "project", None) or os.getcwd())
                   / ".qt-ohos" / "bin")
        out = pc.write_shim(bin_dir)
        for w in out["written"]:
            print("wrote %s" % w)
        print("add %s to PATH and CMake's pkg_check_modules will work" % bin_dir)
        return 0

    dirs = pc.search_dirs(libs_dir if libs_dir.is_dir() else None)
    if args.print_path:
        for d in dirs:
            print(str(d))
        return 0
    if args.list:
        index = pc.build_index(dirs)
        for name in sorted(index):
            print("%-28s %s" % (name, pc.read_pc(index[name])["version"]))
        print("pkgconfig: %d packages (searched %d directories)" % (len(index), len(dirs)))
        return 0

    argv = [a for a in (list(args.pkg_args or [])
                        + list(getattr(args, "pkg_extra", []) or []))
            if a != "--"]
    if not argv:
        print("usage: pkgconfig [--relocate|--write-shim|--list|--print-path]"
              " or pkgconfig --cflags --libs <pkg>")
        print("found %d .pc packages" % len(pc.build_index(dirs)))
        return 0
    if libs_dir.is_dir():
        argv.extend(["--libdir", str(libs_dir)])
    return pc.main(argv)


def cmd_libcheck(args):
    """Library-level intermediate gate: record a library's porting progress as a verifiable fact.

    The whole HAP running on a device is the finish line, but what actually moves during porting is a batch of libraries.
    The old model only had "whole package PASS/FAIL", so progress like "this library now compiles and links, and its
    platform functions work on the device" had nowhere to be recorded and couldn't show up in `verify`.

    Two levels (only these two, to avoid inventing states):
      built  -- the library compiles + links (artifact exists)
      probed -- platform functions were really called on the device (with device-side evidence)
    """
    st = _state(args)
    data = st.read_json("libs.json", default={}) or {}
    libraries = data.get("libraries") or []

    if args.list:
        if not libraries:
            print("[qt-ohos-run] no libraries recorded yet")
            return 0
        print("%-28s %-8s %-20s %s" % ("library", "level", "recorded", "evidence"))
        for item in libraries:
            print("%-28s %-8s %-20s %s" % (
                item.get("name"), item.get("level"), item.get("at", "-"),
                (item.get("evidence") or "")[:60]))
        return 0

    if not args.name:
        print("[qt-ohos-run] library name required: libcheck <name> --level built|probed")
        return 2
    level = (args.level or "").lower()
    if level not in ("built", "probed"):
        print("[qt-ohos-run] --level must be built or probed")
        return 2
    if level == "probed" and not args.evidence:
        # Device-side evidence is mandatory: "probed" without evidence is self-deception
        print("[qt-ohos-run] probed requires --evidence (device log/hilog key line)")
        return 2

    record = {"name": args.name, "level": level,
              "evidence": args.evidence or "", "at": _now_iso()}
    for idx, item in enumerate(libraries):
        if item.get("name") == args.name:
            libraries[idx] = record
            break
    else:
        libraries.append(record)
    data["libraries"] = libraries
    st.write_json("libs.json", data)
    print("[qt-ohos-run] library %s -> %s" % (args.name, level))
    return 0


def cmd_mark_risk(args):
    st = _state(args)
    verifier.mark_critical_addressed(st, args.rule, evidence=args.evidence,
                                     note=args.note)
    print("[qt-ohos-run] marked addressed: %s (evidence: %s)"
          % (", ".join(args.rule), args.evidence))
    return 0


def cmd_assess(args):
    _apply_positional(args)
    _require_explicit_project(args, "assess")
    """Feasibility verdict (portable / blocked / uncertain) - migration step 0.

    Runs the scan stages when needed, then evaluates against the adaptation
    machine layer (knowledge/adaptation/{modules,blockers,checklist}.yaml).
    """
    project = _resolve_project(args, required=True)
    st = (state_mod.init_state(project)
          if not (project / state_mod.STATE_DIR_NAME / "state.json").exists()
          else state_mod.load_state(project))
    st.check_budget()
    info = st.read_json("scan.json", default={}) or {}
    if not info or args.force:
        st.begin_stage("project_scan")
        info = _scan_with_env(st, project)
        st.write_json("scan.json", info)
        st.complete_stage("project_scan", next_action="assess")
        st.complete_stage("qt_scan", next_action="assess")
        risk = rule_engine.RuleEngine(KB_ROOT).scan(info, project)
        info["risk"] = risk
        st.write_json("scan.json", info)
        st.complete_stage("risk_scan", next_action="assess")
    st.begin_stage("assess")
    recipes = knowledge.similar_recipes(KB_ROOT, info)
    assessment = assessor.evaluate(KB_ROOT, info, info.get("risk"), recipes,
                                   project_root=project)
    info["assessment"] = assessment
    st.write_json("scan.json", info)
    st.write_json("assessment.json", assessment)
    if assessment["verdict"] == "blocked":
        st.fail_stage("assess", error="feasibility-blocked",
                      next_action="resolve blockers (see assessment.json)")
    else:
        st.complete_stage("assess", next_action="plan")
    print(assessor.render(assessment))
    _emit(assessment, args)
    return 0 if assessment["verdict"] != "blocked" else 1


def cmd_rollback(args):
    """Restore all tracked files from .qt-ohos/originals/ (PROC3)."""
    st = _state(args)
    tracker = ChangeTracker(st)
    restored = tracker.rollback()
    if restored:
        print("[qt-ohos-run] rolled back %d file(s):" % len(restored))
        for rel in restored:
            print("  - %s" % rel)
        print("[qt-ohos-run] note: changes.json still holds the history; "
              "patches/ remain for review")
    else:
        print("[qt-ohos-run] nothing to roll back (no originals/ recorded)")
    return 0


def cmd_mark_gate(args):
    """Record a manual gate result (G10 smoke / G11 feature / G12 regression)."""
    gate_id = args.gate.upper()
    if gate_id not in ("G10", "G11", "G12"):
        print("[qt-ohos-run] mark-gate only accepts G10|G11|G12")
        return 1
    st = _state(args)
    manual = st.data.setdefault("manual_gates", {})
    manual[gate_id] = {"status": args.result.upper(), "note": args.note or ""}
    st.save()
    print("[qt-ohos-run] %s recorded: %s" % (gate_id, args.result.upper()))
    return 0


def cmd_mark_ui(args):
    """Record manual G9 (UI window) evidence when uitest is unavailable."""
    st = _state(args)
    runtime = st.read_json("runtime.json", default={}) or {}
    runtime["ui_window_seen"] = bool(args.seen)
    runtime["ui_window"] = {
        "status": "PASS" if args.seen else "FAIL",
        "manual": True, "note": args.note or "manual mark-ui"}
    st.write_json("runtime.json", runtime)
    print("[qt-ohos-run] G9 ui_window_seen=%s (manual)" % args.seen)
    return 0


# ------------------------------------------------------------------ main

HOISTED_VALUE_FLAGS = ("--project", "--timeout")


def _hoist_global_flags(argv):
    """Hoist global flags from any position to before the subcommand.

    argparse only accepts `--project X verify`; `verify --project X` is treated by the subcommand
    as an unknown argument (or worse: silently ignored), though to a human both forms are identical.
    Returns (remaining argv, defaults dict, whether any flag was "given after the subcommand").
    """
    rest, defaults, misplaced = [], {}, False
    seen_command = False
    i = 0
    while i < len(argv):
        token = argv[i]
        name, sep, inline = token.partition("=")
        if name in HOISTED_VALUE_FLAGS:
            value = inline if sep else (argv[i + 1] if i + 1 < len(argv) else None)
            if value is None:
                rest.append(token)
                i += 1
                continue
            defaults[name.lstrip("-").replace("-", "_")] = value
            if seen_command:
                misplaced = True
            i += 2 if not sep else 1
            continue
        if token == "--json":
            defaults["json"] = True
            if seen_command:
                misplaced = True
            i += 1
            continue
        if not token.startswith("-"):
            seen_command = True
        rest.append(token)
        i += 1
    if "timeout" in defaults:
        try:
            defaults["timeout"] = float(defaults["timeout"])
        except ValueError:
            defaults.pop("timeout")
    return rest, defaults, misplaced


def _force_utf8_stdio():
    """A Chinese-locale Windows console defaults to GBK, so printing characters like `•`/`—` raises UnicodeEncodeError;
    file writes are UTF-8 too, so report.md doesn't end up with mojibake like `鈥?`."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def main(argv=None):
    _force_utf8_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    argv, hoisted, misplaced = _hoist_global_flags(argv)
    parser = argparse.ArgumentParser(
        prog="qt-ohos-run",
        description="Qt -> HarmonyOS porting execution CLI (ohos_qt-skills)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON where supported")
    parser.add_argument("--project", default=None,
                        help="target project directory (default: cwd)")
    parser.add_argument("--timeout", type=float, default=600.0,
                        help="per-command timeout seconds (default 600)")
    if hoisted and misplaced:
        # Both forms are equivalent; only mention it when flags were "given after the subcommand" (stderr, don't pollute --json)
        label = ", ".join("--%s" % k.replace("_", "-") for k in hoisted)
        print("[qt-ohos-run] global flag(s) %s given after the subcommand; handled accordingly" % label,
              file=sys.stderr)
    parser.set_defaults(**hoisted)
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="create .qt-ohos state in a project")
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")

    p = sub.add_parser("scan", help="pre-scan: project/Qt/risk/dependencies")
    # The positional argument is optional: both `scan <dir>` and `--project <dir> scan` work
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")
    p.add_argument("--force", action="store_true")

    sub.add_parser("plan", help="generate migration plan")
    sub.add_parser("patch", help="apply tracked automatic fixes")
    p = sub.add_parser("build", help="compile (G3)")
    p.add_argument("--record-only", action="store_true",
                   help="only record an external build result, don't run the build")
    p.add_argument("--artifacts", action="append", default=None,
                   metavar="GLOB",
                   help="record-only: artifact glob (relative to project root, repeatable)")
    p.add_argument("--status", choices=["pass", "fail"], default="pass",
                   help="record-only: external build outcome")
    p.add_argument("--log", default=None, help="record-only: log file (as evidence)")
    p = sub.add_parser("package", help="build HAP (G5)")
    p.add_argument("--record-only", action="store_true",
                   help="only record an external packaging result, don't run hvigor")
    p.add_argument("--hap", default=None, help="record-only: HAP path (relative to project root)")
    sub.add_parser("install", help="hdc install (G6)")
    sub.add_parser("launch", help="aa start (G7)")
    p = sub.add_parser("smoke", help="crash window check (G8) or manual record")
    p.add_argument("--result", choices=["pass", "fail", "partial"], default=None)
    p.add_argument("--note", default=None)

    sub.add_parser("verify", help="run verification gates G0..G12 "
                                  "(exit 0=PASS / 3=PARTIAL / 1=FAIL)")
    p = sub.add_parser("analyze-log", help="match a log against known errors")
    p.add_argument("logfile")
    sub.add_parser("status", help="show migration state")
    p = sub.add_parser("resume", help="resume from checkpoint")
    p.add_argument("--run", action="store_true",
                   help="continue executing remaining stages")
    p = sub.add_parser("migrate", help="run the full automatable pipeline")
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")
    p.add_argument("--no-verify", action="store_true")
    p.add_argument("--assume-project-ready", action="store_true",
                   help="skip the assisted project_generation pause")
    sub.add_parser("finish", help="generate report + knowledge prompts")
    p = sub.add_parser("assess", help="feasibility verdict "
                     "(portable/blocked/uncertain) - migration step 0")
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")
    p.add_argument("--force", action="store_true",
                   help="re-run the scan even if scan.json exists")
    sub.add_parser("rollback", help="restore tracked files from originals/")
    p = sub.add_parser("mark-gate", help="record manual gate result (G10-G12)")
    p.add_argument("gate", choices=["G10", "G11", "G12", "g10", "g11", "g12"])
    p.add_argument("--result", choices=["pass", "fail", "partial", "not-run"],
                   required=True)
    p.add_argument("--note", default=None)
    p = sub.add_parser("mark-ui", help="record manual G9 (UI window) evidence")
    p.add_argument("--seen", action="store_true",
                   help="window was seen (omit for not-seen)")
    p.add_argument("--note", default=None)
    p = sub.add_parser("draft", help="create a knowledge draft")
    p.add_argument("title")
    p.add_argument("--summary", default=None)
    p.add_argument("--summary-file", default=None,
                   help="read the summary from a file (PowerShell splits long Chinese summaries into several arguments)")
    p.add_argument("--symptom", default=None)
    p.add_argument("--log", default=None)
    p.add_argument("--tag", action="append")
    p = sub.add_parser("promote", help="promote a draft: problems/ page + "
                       "knowledge/errors/ yaml + index count")
    p.add_argument("draft_id")
    p = sub.add_parser("recipes", help="similar historical migrations")
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")
    p = sub.add_parser("config", help="manage .qt-ohos/env.json")
    p.add_argument("config_action", choices=["show", "set"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.add_argument("--no-invalidate", action="store_true",
                   help="don't invalidate scan results (runtime keys never invalidate by default)")
    p.add_argument("--rescan", action="store_true",
                   help="rescan immediately after invalidation")

    p = sub.add_parser("doctor",
                       help="check environment prerequisites with fixes")
    p = sub.add_parser("sign",
                       help="generate signing materials (devecocli) and verify wiring")
    p.add_argument("--product", default=None)
    p.add_argument("--type", choices=["debug", "release"], default="debug")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("smoke-interact",
                       help="G10 machine evidence: screenshot -> tap -> screenshot")
    p = sub.add_parser("mark-risk", help="mark critical risks as addressed (G2)")
    p.add_argument("--rule", action="append", required=True)
    p.add_argument("--evidence", required=True,
                   help="which file was changed / how it was verified (G2 only accepts marks with evidence)")
    p.add_argument("--note", default="", help="optional note")

    p = sub.add_parser(
        "pkgconfig",
        help="pkg-config stand-in: relocate .pc prefixes / generate shim / query cflags+libs")
    p.add_argument("--relocate", nargs="?", const="", default=None,
                   metavar="LIBS_DIR",
                   help="rewrite build-machine absolute paths in all .pc files under ohos-libs to this machine")
    p.add_argument("--dry-run", action="store_true",
                   help="only print the lines that would change, don't write files")
    p.add_argument("--write-shim", nargs="?", const="", default=None,
                   metavar="BIN_DIR",
                   help="generate pkg-config / pkg-config.bat stand-ins (default .qt-ohos/bin)")
    p.add_argument("--libdir", default=None,
                   help="ohos-libs directory (default: project .qt-ohos/env.json or ohos-libs)")
    p.add_argument("--list", action="store_true", help="list discoverable .pc packages")
    p.add_argument("--print-path", action="store_true",
                   help="print directories suitable for PKG_CONFIG_PATH")
    p.add_argument("pkg_args", nargs=argparse.REMAINDER,
                   help="arguments passed through to pkg-config (--cflags/--libs/package name)")

    p = sub.add_parser("libcheck",
                       help="record per-library porting milestones (built/probed)")
    p.add_argument("name", nargs="?", help="library or CMake target name")
    p.add_argument("--level", choices=["built", "probed"],
                   help="built=compiled+linked, probed=platform funcs called on device")
    p.add_argument("--evidence", help="device log line / hilog key line (required for probed)")
    p.add_argument("--list", action="store_true", help="list recorded libraries")
    # A same-named subparser argument overwrites the global --project with its default (argparse semantics),
    # so `libcheck --project X` fell back to the repo root. SUPPRESS = leave the global value alone.
    p.add_argument("--project", default=argparse.SUPPRESS,
                   help="project directory (defaults to cwd)")

    # What follows `pkgconfig` is native pkg-config syntax (--cflags/--libs/package name);
    # argparse would reject `--cflags` as an unknown option. Relax it for this one subcommand only:
    # remaining unknown arguments pass through to pkg-config unchanged; other subcommands stay strict.
    if argv and argv[0] == "pkgconfig":
        args, extra = parser.parse_known_args(argv)
        args.pkg_extra = extra
    else:
        args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1

    handlers = {
        "init": cmd_init, "scan": cmd_scan, "assess": cmd_assess,
        "plan": cmd_plan, "patch": cmd_patch,
        "build": cmd_build, "package": cmd_package, "install": cmd_install,
        "launch": cmd_launch, "smoke": cmd_smoke, "verify": cmd_verify,
        "analyze-log": cmd_analyze_log, "status": cmd_status, "resume": cmd_resume,
        "migrate": cmd_migrate, "finish": cmd_finish, "rollback": cmd_rollback,
        "mark-gate": cmd_mark_gate, "mark-ui": cmd_mark_ui,
        "draft": cmd_draft, "promote": cmd_promote, "recipes": cmd_recipes,
        "config": cmd_config, "mark-risk": cmd_mark_risk,
        "doctor": cmd_doctor, "sign": cmd_sign,
        "smoke-interact": cmd_smoke_interact,
        "libcheck": cmd_libcheck, "pkgconfig": cmd_pkgconfig,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
