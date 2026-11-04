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
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from qt_ohos import (assessor, builder, dependency, error_engine, knowledge,
                     migration, report, rule_engine, scanner,
                     state as state_mod, verifier)
from qt_ohos.patch import ChangeTracker
from qt_ohos.state import BudgetExhausted, MigrationState

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
    print("[qt-ohos-run] 用 `--project <项目目录>` 指向已 scan 过的工程"
          "（例如 `qt-ohos-run --project ~/app scan` 后跟 `--project ~/app plan`），"
          "或先在该工程内 `init`")
    sys.exit(1)


def _require_explicit_project(args, command: str) -> None:
    """init/scan/migrate/assess 必须显式给工程：否则会在仓根或当前目录建 .qt-ohos。"""
    if not ((getattr(args, "path", None)) or getattr(args, "project", None)):
        print("[qt-ohos-run] %s 需要工程目录：`%s <工程目录>` 或 "
              "`--project <工程目录> %s`" % (command, command, command))
        sys.exit(2)


def _apply_positional(args) -> None:
    """把可选的工程位置参数并进 args.project，让 `cmd <dir>` 与 `--project <dir> cmd` 等价。"""
    path = getattr(args, "path", None)
    if path:
        args.project = path


def _state(args) -> MigrationState:
    project = _resolve_project(args, required=False)
    return state_mod.load_state(project)


def _emit(payload, args):
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_risk_report(risk: dict) -> None:
    summary = risk.get("summary") or {}
    print("\nQt HarmonyOS Porting Risk Report")
    print("================================")
    for sev in ("critical", "high", "medium", "low"):
        count = summary.get(sev, 0)
        if count:
            print("%-8s : %d" % (sev.upper(), count))
    for finding in risk.get("findings", [])[:40]:
        print("  %-5s %-7s %-22s %s:%s" % (
            finding["severity"][:4].upper(), finding["rule"],
            str(finding.get("name"))[:22], finding.get("file"),
            finding.get("line")))
        if finding.get("snippet"):
            print("        %s" % finding["snippet"][:100])
    if len(risk.get("findings", [])) > 40:
        print("  ... %d more findings in scan.json" %
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


def _scan_with_env(st, project) -> dict:
    """扫描工程并应用 env.json 的 qt_version 覆盖（assess --force 之前会丢掉这个覆盖）。"""
    info = scanner.scan_project(project)
    override = str((builder.env_of(st) or {}).get("qt_version") or "").strip()
    if override:
        info["qt_version_hint"] = override
        info["qt_version_evidence"] = "config set qt_version %s" % override
        info["warnings"] = [w for w in info.get("warnings", [])
                            if "未能从构建文件判定 Qt 主版本" not in w]
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
                    version = info.get("qt_version_hint") or "未判定"
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
                _print_risk_report(risk)
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
        # 全部阶段已完成时旧实现静默退出：改了代码再 scan 看到"什么都没发生"，
        # 很容易以为已经重扫。说清楚它没重扫、怎么重扫。
        print("[qt-ohos-run] 扫描阶段都已完成，本次未重扫（上次 %s）"
              % (st.data.get("updated") or "?"))
        print("[qt-ohos-run] 代码改动后要重扫：加 --force；只改了配置则 "
              "`config set` 会让相关阶段自动失效")
    _emit(st.read_json("scan.json"), args)
    return 0


def cmd_plan(args):
    st = _state(args)
    st.check_budget()
    st.begin_stage("plan")
    info = st.read_json("scan.json", default={}) or {}
    if not info:
        print("[qt-ohos-run] run `scan` first")
        return 1
    plan = migration.build_plan(info, info.get("risk") or {},
                                info.get("dependencies") or [], kb_root=KB_ROOT)
    st.write_json("migration-plan.json", plan)
    st.complete_stage("plan", next_action="patch")
    info = st.read_json("scan.json", default={}) or {}
    if not info.get("qt_modules"):
        print("[qt-ohos-run] WARNING: 扫描没识别到 Qt 模块（%s），"
              "下面的计划可能不适用——先确认工程根目录对不对" %
              (info.get("build_system") or "无构建文件"))
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
    else:
        print("[qt-ohos-run] no automatic fixes applicable")
    if patches:
        print("[qt-ohos-run] patches: %s" % ", ".join(patches))
    _emit({"applied": applied, "patches": patches}, args)
    return 0


def cmd_build(args):
    st = _state(args)
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
        # 没装上 / 没起来 / 没抓到本应用日志：这是"没测"，不是"通过"。
        st.fail_stage("smoke", error="not-run:%s" % result.status,
                      next_action="install+launch")
        print("[qt-ohos-run] smoke 未执行（%s）——先让 install/launch 通过，"
              "或确认 bundle_name 与 hilog 输出对得上" % result.status)
        return 2
    st.fail_stage("smoke", error="crash-detected", next_action="analyze-log")
    return 1


def cmd_verify(args):
    st = _state(args)
    gates, overall = verifier.evaluate(st)
    st.data["gates"] = gates
    st.data["overall"] = overall
    st.save()
    print(verifier.render(gates, overall))
    _emit({"gates": gates, "overall": overall}, args)
    return {"PASS": 0, "PARTIAL": 3}.get(overall, 1)


def cmd_analyze_log(args):
    # 日志分析与工程状态无关：只有显式给了 --project 才回写 error 字段，
    # 否则不要用"先 init"去误导一个只想看日志的用户。
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
        # 链接期 undefined symbol 是移植中期最常见的"没人实现"，它没有固定
        # 错误码可匹配（符号名千变万化），指到真正能收敛它的工具上。
        try:
            raw = Path(args.logfile).read_text(encoding="utf-8", errors="replace")
        except OSError:
            raw = ""
        if "undefined symbol" in raw or "undefined reference" in raw:
            print("[qt-ohos-run] 日志里有 undefined symbol/reference：用\n"
                  "  python tools/ohos-platform-audit.py <platform 目录> "
                  "--undefined %s\n"
                  "区分『平台层还没实现』与『三方库/工具链问题』" % args.logfile)
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


def cmd_status(args):
    st = _state(args)
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
            _print_risk_report(risk)
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
                                        kb_root=KB_ROOT)
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
        for stage_name, fn in device_steps.items():
            if stage_done(stage_name):
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
                print("[qt-ohos-run] %s: %s（未执行，不等于通过）"
                      % (stage_name, result.status))
                rc = max(rc, 2)
            else:
                st.fail_stage(stage_name, error=result.status,
                              next_action="analyze-log")
                print("[qt-ohos-run] %s: %s" % (stage_name, result.status))
                rc = max(rc, 1)
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
    path = knowledge.create_draft(KB_ROOT, args.title, summary=args.summary or "",
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


def cmd_config(args):
    st = _state(args)
    env = builder.env_of(st)
    if args.config_action == "show":
        print(json.dumps(env, ensure_ascii=False, indent=2))
        return 0
    if args.config_action == "set":
        if args.value.lower() in ("true", "false"):
            env[args.key] = args.value.lower() == "true"
        else:
            env[args.key] = args.value
        st.write_json("env.json", env)
        # 配置变了，之前的扫描结论就过期了：扫过的东西要在下次 scan 时重算，
        # 否则改了 qt_version / bundle_name 还得记得加 --force（旧行为）。
        invalidated = st.invalidate_scan_stages()
        print("[qt-ohos-run] env.json: %s = %s" % (args.key, args.value))
        if invalidated:
            print("[qt-ohos-run] scan 状态已失效（%s），下次 scan 会重扫"
                  % ", ".join(invalidated))
        return 0
    return 1


def _now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def cmd_libcheck(args):
    """库级中间门禁：把一个库的移植进展记成可核验的事实。

    整包 HAP 上板是终点，但移植过程中真正推进的是一批库。旧模型只有
    "整包 PASS/FAIL"，于是"这个库已经编译链接通过、平台函数在设备上调通了"
    这种进展无处可记，也无法在 `verify` 里体现。

    两个层级（只认这两个，避免自造状态）：
      built  —— 该库编译 + 链接通过（产物存在）
      probed —— 平台函数在设备上被真实调用过（有设备侧证据）
    """
    st = _state(args)
    data = st.read_json("libs.json", default={}) or {}
    libraries = data.get("libraries") or []

    if args.list:
        if not libraries:
            print("[qt-ohos-run] 还没有登记任何库")
            return 0
        print("%-28s %-8s %-20s %s" % ("library", "level", "recorded", "evidence"))
        for item in libraries:
            print("%-28s %-8s %-20s %s" % (
                item.get("name"), item.get("level"), item.get("at", "-"),
                (item.get("evidence") or "")[:60]))
        return 0

    if not args.name:
        print("[qt-ohos-run] 需要库名：libcheck <name> --level built|probed")
        return 2
    level = (args.level or "").lower()
    if level not in ("built", "probed"):
        print("[qt-ohos-run] --level 只能是 built 或 probed")
        return 2
    if level == "probed" and not args.evidence:
        # 设备侧证据不许省略：没有证据的 "probed" 就是自欺
        print("[qt-ohos-run] probed 必须带 --evidence（设备日志/hilog 关键行）")
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
    verifier.mark_critical_addressed(st, args.rule)
    print("[qt-ohos-run] marked addressed: %s" % ", ".join(args.rule))
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

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="qt-ohos-run",
        description="Qt -> HarmonyOS porting execution CLI (ohos_qt-skills)")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON where supported")
    parser.add_argument("--project", default=None,
                        help="target project directory (default: cwd)")
    parser.add_argument("--timeout", type=float, default=600.0,
                        help="per-command timeout seconds (default 600)")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("init", help="create .qt-ohos state in a project")
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")

    p = sub.add_parser("scan", help="pre-scan: project/Qt/risk/dependencies")
    # 位置参数可选：`scan <dir>` 与 `--project <dir> scan` 两种写法都成立
    p.add_argument("path", nargs="?", default=None, metavar="project",
                   help="project directory (same as --project)")
    p.add_argument("--force", action="store_true")

    sub.add_parser("plan", help="generate migration plan")
    sub.add_parser("patch", help="apply tracked automatic fixes")
    sub.add_parser("build", help="compile (G3)")
    sub.add_parser("package", help="build HAP (G5)")
    sub.add_parser("install", help="hdc install (G6)")
    sub.add_parser("launch", help="aa start (G7)")
    p = sub.add_parser("smoke", help="crash window check (G8) or manual record")
    p.add_argument("--result", choices=["pass", "fail", "partial"], default=None)
    p.add_argument("--note", default=None)

    sub.add_parser("verify", help="run verification gates G0..G12")
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
    p = sub.add_parser("mark-risk", help="mark critical risks as addressed (G2)")
    p.add_argument("--rule", action="append", required=True)

    p = sub.add_parser("libcheck",
                       help="record per-library porting milestones (built/probed)")
    p.add_argument("name", nargs="?", help="library or CMake target name")
    p.add_argument("--level", choices=["built", "probed"],
                   help="built=compiled+linked, probed=platform funcs called on device")
    p.add_argument("--evidence", help="device log line / hilog key line (probed 必填)")
    p.add_argument("--list", action="store_true", help="列出已登记的库")
    p.add_argument("--project", help="project directory (defaults to cwd)")

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
        "libcheck": cmd_libcheck,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
