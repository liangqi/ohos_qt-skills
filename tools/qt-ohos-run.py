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


def _say(args, message=""):
    """人类可读输出。`--json` 时改走 stderr——stdout 必须是可直接 parse 的 JSON。"""
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
                                info.get("dependencies") or [], kb_root=KB_ROOT,
                                env=builder.env_of(st))
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


def _record_external_package(st, args):
    """登记外部打包结果（HAP 已由别的流程产出）。"""
    project = Path(st.project_root)
    if not args.hap:
        print("[qt-ohos-run] package --record-only 需要 --hap <路径>")
        return 2
    hap = Path(args.hap)
    if not hap.is_absolute():
        hap = project / hap
    build_json = st.read_json("build.json", default={}) or {}
    if not hap.is_file() or hap.stat().st_size == 0:
        build_json["package"] = {
            "command": "record-only (external package)", "status": "FAIL",
            "exit_code": 1, "stdout": "", "start_time": _now_iso(),
            "stderr": "HAP 不存在或为空：%s" % args.hap}
        st.write_json("build.json", build_json)
        st.fail_stage("package", error="record-only", next_action="package")
        print("[qt-ohos-run] 已登记外部打包：FAIL（HAP 不存在或为空：%s）" % args.hap)
        return 1
    build_json["hap"] = hap.relative_to(project).as_posix() \
        if hap.is_relative_to(project) else str(hap)
    build_json["package"] = {
        "command": "record-only (external package)", "label": "package-recorded",
        "status": "PASS", "exit_code": 0, "stdout": "",
        "stderr": "", "evidence": str(hap), "start_time": _now_iso()}
    st.write_json("build.json", build_json)
    st.complete_stage("package", next_action="install")
    print("[qt-ohos-run] 已登记外部打包：PASS（%s）" % build_json["hap"])
    return 0


def _record_external_build(st, args):
    """登记外部构建结果：不重跑构建，只把事实写进门禁读的地方。

    为什么需要：交叉编译常常跑自己的脚本（build_ohos_k.py）或 CI，
    工具再跑一遍既慢又可能和真实产物不一致。此前只能手写 build.json 才能让
    G3/G4 反映真实状态——那等于绕过工具，且没有证据。
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
        reason = "record-only 没给 --artifacts：不登记产物就无法校验，G4 会判缺产物"
    elif args.status == "pass" and not found:
        reason = ("record-only 声称构建成功，但 --artifacts 没匹配到任何文件：%s"
                  % ", ".join(patterns))
    evidence = ""
    if args.log:
        log_path = Path(args.log)
        if not log_path.is_absolute():
            log_path = project / log_path
        evidence = str(log_path) if log_path.exists() else ""
        if args.log and not evidence:
            reason = (reason + "; " if reason else "") + \
                "--log 指向的日志不存在：%s" % args.log
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
        print("[qt-ohos-run] 已登记外部构建：PASS，%d 个产物%s" % (
            len(found), "（证据：%s）" % evidence if evidence else ""))
        for rel in found[:5]:
            print("  %s" % rel)
        return 0
    st.fail_stage("compile", error="record-only", next_action="build")
    print("[qt-ohos-run] 已登记外部构建：FAIL（%s）" % (reason or "status=fail"))
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
    _say(args, verifier.render(gates, overall))
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
                # 上游已经失败：继续往下跑只会拿到一连串连带失败，还把"没测"
                # 混进报告。这里明确记成未测并停链。
                st.skip_cmd(stage_name, "skipped: upstream %s did not pass" % broken)
                st.fail_stage(stage_name, error="upstream:%s" % broken,
                              next_action="fix %s" % broken)
                print("[qt-ohos-run] %s: SKIP（上游 %s 未通过）"
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
                print("[qt-ohos-run] %s: %s（未执行，不等于通过）"
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


# ---- 只影响运行期行为的键：改动它们不需要重扫工程 -------------------------
# 旧实现一改就让扫描失效，于是"只想把 hdc 路径改一下"也要等 12 秒重扫，
# 用户自然学会绕开 config。运行期键与工程事实键必须分开。
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
            print("[qt-ohos-run] 用法：config set <key> <value>", file=sys.stderr)
            return 2
        if args.value.lower() in ("true", "false"):
            env[args.key] = args.value.lower() == "true"
        else:
            env[args.key] = args.value
        st.write_json("env.json", env)
        print("[qt-ohos-run] env.json: %s = %s" % (args.key, args.value))
        if args.key in RUNTIME_KEYS or args.no_invalidate:
            print("[qt-ohos-run] 运行期键，扫描结论仍然有效")
            return 0
        # 工程事实变了（qt_version / 源码路径等），之前的扫描结论过期。
        invalidated = st.invalidate_scan_stages()
        if invalidated:
            print("[qt-ohos-run] scan 状态已失效（%s）" % ", ".join(invalidated))
        if getattr(args, "rescan", False):
            scan_args = argparse.Namespace(**vars(args))
            code = cmd_scan(scan_args)
            return code
        print("[qt-ohos-run] 下次 scan 会重扫；想免掉这一步用 "
              "`config set <key> <value> --no-invalidate`（仅限运行期键）")
        return 0
    return 1


def _probe(name: str, ok: bool, detail: str, fix: str = "",
           partial: bool = False) -> dict:
    status = "PASS" if ok else ("PARTIAL" if partial else "FAIL")
    return {"name": name, "status": status, "detail": detail, "fix": fix}


def _which_or(value) -> str:
    return value if value else ""


def cmd_doctor(args):
    """环境自检：把"跑起来才炸"的前置条件一次问完，每条带可执行的修法。

    这些检查都来自实测踩坑（Qt6 预构建 kit / hvigor 五件套 / SDK 版本 / 设备链），
    以前散落在各页知识里，移植者要在失败日志里逐个反推。
    """
    import shutil as _shutil
    import subprocess as _subprocess
    import types

    # doctor 要在"什么都还没 init"的工程上也能跑：没有状态目录时按只读方式探测，
    # 绝不为了体检而在别人的工程里建 .qt-ohos/。
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
    checks.append(_probe("cmake", bool(cmake), cmake or "未找到",
                         "config set cmake <cmake 绝对路径>"))

    make = env.get("make_program") or _shutil.which("mingw32-make") or \
        _shutil.which("ninja") or _shutil.which("make") or ""
    checks.append(_probe("构建工具", bool(make), make or "未找到",
                         "Windows 装 mingw32-make 或 ninja；"
                         "config set make_program <路径>"))

    qt = env.get("qt_sdk_prefix") or ""
    toolchain = Path(qt) / "lib" / "cmake" / "Qt6" / "qt.toolchain.cmake" \
        if qt else None
    checks.append(_probe(
        "Qt kit", bool(toolchain and toolchain.is_file()),
        str(toolchain) if toolchain else "未配置 qt_sdk_prefix",
        "config set qt_sdk_prefix <kit 根目录>（Qt6 kit 需含 "
        "lib/cmake/Qt6/qt.toolchain.cmake）"))

    if toolchain and toolchain.is_file():
        platform = Path(qt) / "plugins" / "platforms" / "libqohos.so"
        checks.append(_probe("Qt OHOS 平台插件", platform.is_file(),
                             str(platform),
                             "该 kit 不是 OHOS 版（缺 plugins/platforms/libqohos.so）"))
        host = env.get("qt_host_sdk") or ""
        moc = Path(host) / "bin" / ("moc.exe" if os.name == "nt" else "moc") \
            if host else None
        checks.append(_probe(
            "宿主 kit", bool(moc and moc.is_file()),
            str(moc) if moc else "未配置 qt_host_sdk",
            "config set qt_host_sdk <宿主 kit 根目录>（Qt6 交叉编译的 QT_HOST_PATH）"))

    native = env.get("ohos_sdk_native") or ""
    chainload = Path(native) / "build" / "cmake" / "ohos.toolchain.cmake" \
        if native else None
    checks.append(_probe(
        "OHOS native SDK", bool(chainload and chainload.is_file()),
        str(chainload) if (chainload and chainload.is_file()) else "未配置/不完整",
        "config set ohos_sdk_native <SDK>/native"))

    sdk_version = builder._sdk_from_sdk_home(env)
    checks.append(_probe(
        "SDK 版本", bool(sdk_version), sdk_version or "读不到 oh-uni-package.json",
        "config set deveco_sdk_home <command-line-tools>/sdk"))

    hvigor = builder.find_hvigor(env)
    checks.append(_probe(
        "hvigorw", bool(hvigor), hvigor or "未找到",
        "config set hvigor <DevEco>/tools/hvigor/bin/hvigorw.bat（绝对路径）"))

    extra = builder.hvigor_env(probe, env, create=False)
    checks.append(_probe("JAVA_HOME", "JAVA_HOME" in extra,
                         extra.get("JAVA_HOME", "未找到（DevEco 自带 jbr）"),
                         "config set java_home <DevEco>/jbr"))
    checks.append(_probe("HVIGOR_USER_HOME", "HVIGOR_USER_HOME" in extra,
                         extra.get("HVIGOR_USER_HOME", ""),
                         "config set hvigor_home <绝对可写路径>"))
    def _writable(path) -> bool:
        """目录还不存在时看最近的存在祖先：体检不该边查边建目录。"""
        if not str(path):
            return False
        current = Path(path)
        while not current.exists() and current != current.parent:
            current = current.parent
        return current.is_dir() and os.access(current, os.W_OK)

    writable = _writable(extra.get("npm_config_cache"))
    checks.append(_probe("npm 缓存可写", writable,
                         extra.get("npm_config_cache", ""),
                         "config set npm_cache <绝对可写路径>"))

    hdc = env.get("hdc") or find_hdc()
    checks.append(_probe("hdc", bool(hdc), hdc or "未找到",
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
        checks.append(_probe("设备", bool(lines), ", ".join(lines) or "无设备",
                             "hdc list targets 为空：检查 USB 调试/授权"))

    checks.append(_probe("bundle_name", bool(env.get("bundle_name")),
                         env.get("bundle_name", "未配置"),
                         "config set bundle_name <bundle>"))
    ability = env.get("ability_name") or builder.detect_ability(probe, env)
    checks.append(_probe("ability", bool(ability), ability or "未找到",
                         "package 后自动解析；也可 config set ability_name <name>"))

    cli = builder.find_devecocli(env)
    checks.append(_probe("devecocli", bool(cli), cli or "未找到（可选，用于签名/截图）",
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
    """签名：优先让 devecocli 生成，材料缺失时给六件套手工清单。"""
    st = _state(args)
    env = builder.env_of(st)
    cli = builder.find_devecocli(env)
    if not cli:
        print("[qt-ohos-run] 未找到 devecocli，签名需手工配置六件套：\n"
              "  --signing-cert-path / --signing-profile / --signing-store-file\n"
              "  --signing-key-alias / --signing-key-password / --signing-store-password\n"
              "参考 procedural/qt6-ohos-windows-cli-deploy.md §签名",
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
    # 光生成材料不算完：只有 products[].signingConfig 引用到 signingConfigs 才生效
    profile = None
    for directory in builder._package_dirs(st, env) or [Path(st.project_root)]:
        candidate = directory / "build-profile.json5"
        if candidate.is_file():
            profile = candidate
            break
    if profile is None:
        print("[qt-ohos-run] 没找到 build-profile.json5：签名材料生成了但没写进工程",
              file=sys.stderr)
        return 1
    data = builder.read_json5(profile)
    text = profile.read_text(encoding="utf-8", errors="replace")
    referenced = bool(re.search(r'"signingConfig"\s*:\s*"', text))
    print("[qt-ohos-run] %s: signingConfigs=%s, products 引用=%s"
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
    verifier.mark_critical_addressed(st, args.rule, evidence=args.evidence,
                                     note=args.note)
    print("[qt-ohos-run] marked addressed: %s（证据：%s）"
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
    """把全局参数从任意位置提到子命令之前。

    argparse 只认 `--project X verify`；写成 `verify --project X` 会被子命令
    当成未知参数（或更糟：被静默忽略），而两种写法在人看来完全一样。
    返回 (剩余 argv, 默认值 dict, 是否发生过"写在子命令之后")。
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
    """Windows 中文控制台默认 GBK，输出 `•`/`—` 这类字符会 UnicodeEncodeError；
    文件写入也统一 UTF-8，免得 report.md 里出现 `鈥?`。"""
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
        # 两种写法等价；只在"写在子命令之后"时说一声（stderr，别污染 --json）
        label = ", ".join("--%s" % k.replace("_", "-") for k in hoisted)
        print("[qt-ohos-run] 全局参数 %s 写在子命令之后，已按此处理" % label,
              file=sys.stderr)
    parser.set_defaults(**hoisted)
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
    p = sub.add_parser("build", help="compile (G3)")
    p.add_argument("--record-only", action="store_true",
                   help="只登记外部构建结果，不自己跑构建")
    p.add_argument("--artifacts", action="append", default=None,
                   metavar="GLOB",
                   help="record-only：产物 glob（相对工程根，可重复）")
    p.add_argument("--status", choices=["pass", "fail"], default="pass",
                   help="record-only：外部构建结论")
    p.add_argument("--log", default=None, help="record-only：日志文件（作为证据）")
    p = sub.add_parser("package", help="build HAP (G5)")
    p.add_argument("--record-only", action="store_true",
                   help="只登记外部打包结果，不自己跑 hvigor")
    p.add_argument("--hap", default=None, help="record-only：HAP 路径（相对工程根）")
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
                   help="不使扫描结论失效（运行期键默认就不失效）")
    p.add_argument("--rescan", action="store_true",
                   help="失效后立即重扫")

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
                   help="改在哪个文件/怎么验证的（G2 只认带证据的标记）")
    p.add_argument("--note", default="", help="可选备注")

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
        "doctor": cmd_doctor, "sign": cmd_sign,
        "smoke-interact": cmd_smoke_interact,
        "libcheck": cmd_libcheck,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
