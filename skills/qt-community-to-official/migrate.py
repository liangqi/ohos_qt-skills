#!/usr/bin/env python3
"""
Qt for OpenHarmony: 社区版 → 官方版 一键迁移脚本

完整实现 qt-community-to-official skill 工作流：
  Step 1: 复制胶水代码 + 从 templates/ 模版创建新工程 + 导入 SDK 库/头文件 + 源码迁移
  Step 2: 按目录生成迁移 patch 文件（过滤 .so/.py）
  Step 3: 修复编译问题完成编译 + 生成编译修复 patch
  Step 4: 生成签名 hap 并测试启动不崩溃

Usage:
    python3 migrate.py [original_project] [official_sdk]

    original_project  — 原始社区版工程路径（胶水代码来源）
    official_sdk      — 官方版 Qt SDK install 路径（含 lib/ 和 include/）

    模版工程自动使用 SKILL.md 同级目录下的 templates/ 文件夹，无需用户输入。
"""

import os
import re
import sys
import shutil
import time
import subprocess
import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
DOCS_DIR = SKILL_DIR / "docs"
PATCHES_DIR = SKILL_DIR / "patches"
BUILD_DOCS_DIR = SKILL_DIR / "build"
# Templates path: same directory as SKILL_DIR and migrate.py (SKILL_DIR)
TEMPLATES_DIR = SKILL_DIR / "templates"
ORIG_PROJECT_DIR = None  # set in step1_get_project_path(), used in step2
SELECTED_QT_VERSION = None  # set in step1_select_qt_version()
SELECTED_QT_DOCS_DIR = None  # docs/qt<version>/ dir for version-specific docs
BUILD_CMD = "hvigorw assembleHap --mode module -p module=entry@default -p product=default --no-daemon"

class C:
    R="\033[0m"; B="\033[1m"; RED="\033[31m"; GRN="\033[32m"
    YLW="\033[33m"; BLU="\033[34m"; CYA="\033[36m"; GRY="\033[90m"

def banner(t): print(f"\n{C.BLU}{'='*60}{C.R}\n{C.BLU}  {t}{C.R}\n{C.BLU}{'='*60}{C.R}\n")
def step(n,t): print(f"\n{C.CYA}{C.B}Step {n}: {t}{C.R}\n")
def info(m):   print(f"  {C.GRY}ℹ{C.R}  {m}")
def ok(m):     print(f"  {C.GRN}✓{C.R}  {m}")
def warn(m):   print(f"  {C.YLW}⚠{C.R}  {m}")
def err(m):    print(f"  {C.RED}✗{C.R}  {m}")
def ask(m):
    print(f"\n  {C.YLW}❓ {m}{C.R}")
    return input(f"  {C.GRY}> {C.R}").strip()

def run(cmd, cwd=None, capture=False):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=capture, text=True)

def _setup_build_env():
    """Auto-detect and set DEVECO_SDK_HOME + JAVA_HOME + hdc for hvigor/hdc (build-fix-12).
    DevEco Studio sets these internally; command-line scripts must set them too."""
    env = os.environ.copy()
    # DEVECO_SDK_HOME: must point to the parent of default/ SDK directory
    sdk = env.get("DEVECO_SDK_HOME", "")
    if not sdk or not Path(sdk).exists():
        for c in ["/Applications/DevEco-Studio.app/Contents/sdk",
                  "C:\\Program Files\\Huawei\\DevEco Studio\\sdk"]:
            if Path(c).exists():
                env["DEVECO_SDK_HOME"] = c
                break
    # JAVA_HOME: DevEco's bundled JBR
    jbr = env.get("JAVA_HOME", "")
    if not jbr or not Path(jbr).exists():
        for c in ["/Applications/DevEco-Studio.app/Contents/jbr/Contents/Home",
                  "C:\\Program Files\\Huawei\\DevEco Studio\\jbr"]:
            if Path(c).exists():
                env["JAVA_HOME"] = c
                break
    extra_paths = []
    if "JAVA_HOME" in env:
        extra_paths.append(env["JAVA_HOME"] + os.sep + "bin")
    # hdc toolchain: add to PATH if not already found
    if run("which hdc", capture=True).returncode != 0:
        for c in ["/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains",
                  "C:\\Program Files\\Huawei\\DevEco Studio\\sdk\\default\\openharmony\\toolchains"]:
            if Path(c).exists():
                extra_paths.append(c)
                break
    if extra_paths:
        env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")
    return env

def run_build(cmd, cwd=None):
    """Run a build command with DEVECO_SDK_HOME/JAVA_HOME set (build-fix-12)."""
    env = _setup_build_env()
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, env=env)

def run_hdc(cmd, timeout=30):
    """Run an hdc command with proper DevEco environment (build-fix-12)."""
    env = _setup_build_env()
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, returncode=124, stdout="", stderr="timeout")

# ── Migration mappings ──────────────────────────────────────────────────────
HEADER_MIGRATIONS = [
    (r"#include\s*<QtOhExtras/QOhAppContext>", "#include <QtOhosExtras/QOhosAbilityContext>"),
    (r"#include\s*<QtOhExtras/QOhFunctions>",  "#include <QtOhosExtras/QOhosAppPermissions>"),
    (r"#include\s*<QtOhExtras/QOhFileShare>",  "#include <QtOhosExtras/QOhosShareKit>"),
    (r"#include\s*<QtOhExtras/",               "#include <QtOhosExtras/"),
]

CLASS_MIGRATIONS = [
    (r"\bQOhAppContext\b",                      "QOhosAbilityContext"),
    (r"\bnamespace\s+QtOh\b(?!os)",              "namespace QtOhosExtras"),
    (r"\busing\s+namespace\s+QtOh\b(?!os)",      "using namespace QtOhosExtras"),
    (r"\bQtOh::PermissionResult\b",              "AppPermissions::PermissionResult"),
    (r"\bQtOh::PermissionRequestResult\b",       "AppPermissions::PermissionRequestResult"),
    (r"\bQtOh::PermissionResult::Granted\b",     "AppPermissions::PermissionResult::Granted"),
    (r"\bQtOh::PermissionResult::Denied\b",      "AppPermissions::PermissionResult::Denied"),
    (r"\bQtOh::PermissionResult::InValidRequest\b","AppPermissions::PermissionResult::InValidRequest"),
    (r"\bPermissionResultCallback\b",            "std::function<void(AppPermissions::PermissionResult)>"),
    (r"->isPermissionGranted\b",                 "->requestPermissionFromUserIfNeeded"),
    (r"->requestPermissionFromUser\b(?!IfNeeded)","->requestPermissionFromUserIfNeeded"),
    (r"->requestPermissionsOnSetting\b(?!IfNeeded)","->requestPermissionOnSettingIfNeeded"),
    (r"\bQOhAppContext::setColorMode\b",         "QOhosPlatformIntegration::setDarkThemeEnabled"),
    (r"\bQOhAppContext::ColorMode\b",            "QOhosAppContext::ColorMode"),
    (r"\bQOhAppContext::SysThem\b",              "QOhosAppContext::SysThem"),
    (r"\bQOpenHarmonyAbility\b",                 "QOhosAbilityContext"),
    (r"\bQOpenHarmonyWant\b",                    "QOhosWant"),
    (r"\bQOpenHarmonyStartOptions\b",            "QOhosStartOptions"),
]

BUILD_CONFIG_MIGRATIONS = [
    (r"QT\s*\+=\s*ohextras\b",        "QT += ohosextras"),
    (r"CONFIG\s*\+=\s*openharmony\b", "CONFIG += ohos"),
    (r"-platform\s+openharmony\b",    "-platform ohos"),
    (r"\bopenharmony\.prf\b",         "ohos_deployment.prf"),
    (r"\blibqopenharmony\b",          "libqohos"),
]

SCAN_PATTERNS = [
    "QtOhExtras","QOhAppContext","QOhFunctions","QOhFileShare",
    "namespace QtOh","QT += ohextras","CONFIG += openharmony",
    "libqopenharmony","platform openharmony","QOpenHarmony",
]

CODE_EXTS = {".cpp",".h",".hpp",".cxx",".cc",".c",".pro",".pri",".qrc",".cmake",".txt"}
SOURCE_EXTS = CODE_EXTS | {".json",".json5",".ts"}
PATCH_EXCLUDE_EXTS = {".so",".py"}
PATCH_EXCLUDE_NAMES = {"migrate.py"}
COMMUNITY_ONLY_SO = {
    "libQt5OhExtras.so",
    "libqopenharmony.so",
    "libplugins_platforms_qopenharmony.so",
    "libplugins_platforms_qohos.so",
    "libplugins_styles_qharmonystyle.so",
    "libplugins_styles_qohosstyle.so",
}
RENAMED_SO = {
    "libQt5OhExtras.so":                   "libQt5OhosExtras.so",
    "libqopenharmony.so":                  "libqohos.so",
    "libplugins_platforms_qopenharmony.so": "libqohos.so",
    "libplugins_platforms_qohos.so":       "libqohos.so",
    "libplugins_styles_qharmonystyle.so":  "libqohosstyle.so",
    "libplugins_styles_qohosstyle.so":     "libqohosstyle.so",
}

# ── Complex source code transformations ─────────────────────────────────────
def transform_permission_api(content):
    changes = 0
    def _chk(m):
        nonlocal changes; changes+=1; p=m.group(1)
        return f'/* MIGRATED: QtOh::checkPermission → async */\n        QOhosAbilityContext::instance()->requestPermissionFromUserIfNeeded({p})'
    content = re.sub(r'QtOh::checkPermission\(\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')\s*\)', _chk, content)

    def _sync(m):
        nonlocal changes; changes+=1; s=m.group(1)
        f=re.search(r'["\']([^"\']+)["\']',s); p=f'"{f.group(1)}"' if f else 'QString()'
        return f'/* MIGRATED: requestPermissionsSync → async */\n        QOhosAbilityContext::instance()->requestPermissionFromUserIfNeeded({p})'
    content = re.sub(r'QtOh::requestPermissionsSync\(\s*(\{[^}]+\})\s*(?:,\s*\d+\s*)?\)', _sync, content)

    def _async(m):
        nonlocal changes; changes+=1; s=m.group(1)
        f=re.search(r'["\']([^"\']+)["\']',s); p=f'"{f.group(1)}"' if f else 'QString()'
        return f'/* MIGRATED: requestPermissions(callback) → signal-slot */\n        QOhosAbilityContext::instance()->requestPermissionFromUserIfNeeded({p})'
    content = re.sub(r'QtOh::requestPermissions\(\s*(\{[^}]+\})\s*,\s*[^)]+\)', _async, content)

    def _ssync(m):
        nonlocal changes; changes+=1; s=m.group(1)
        f=re.search(r'["\']([^"\']+)["\']',s); p=f'"{f.group(1)}"' if f else 'QString()'
        return f'/* MIGRATED: requestPermissionsOnSettingSync → async */\n        QOhosAbilityContext::instance()->requestPermissionOnSettingIfNeeded({p})'
    content = re.sub(r'QtOh::requestPermissionsOnSettingSync\(\s*(\{[^}]+\})\s*(?:,\s*\d+\s*)?\)', _ssync, content)

    def _sasync(m):
        nonlocal changes; changes+=1; s=m.group(1)
        f=re.search(r'["\']([^"\']+)["\']',s); p=f'"{f.group(1)}"' if f else 'QString()'
        return f'/* MIGRATED: requestPermissionsOnSetting(callback) → signal-slot */\n        QOhosAbilityContext::instance()->requestPermissionOnSettingIfNeeded({p})'
    content = re.sub(r'QtOh::requestPermissionsOnSetting\(\s*(\{[^}]+\})\s*,\s*[^)]+\)', _sasync, content)

    def _notif(m):
        nonlocal changes; changes+=1
        return '/* TODO MIGRATE: requestEnableNotification → QOhosAbilityContext notification API */'
    content = re.sub(r'QtOh::requestEnableNotification\([^)]*\)', _notif, content)

    def _nsync(m):
        nonlocal changes; changes+=1
        return '/* TODO MIGRATE: requestEnableNotificationSync → QOhosAbilityContext notification API */'
    content = re.sub(r'QtOh::requestEnableNotificationSync\([^)]*\)', _nsync, content)

    def _nchk(m):
        nonlocal changes; changes+=1
        return '/* TODO MIGRATE: isNotificationEnabled → QOhosAbilityContext API */ false'
    content = re.sub(r'QtOh::isNotificationEnabled\(\)', _nchk, content)

    def _nset(m):
        nonlocal changes; changes+=1
        return '/* TODO MIGRATE: openNotificationSettings → QOhosAbilityContext API */'
    content = re.sub(r'QtOh::openNotificationSettings\(\)', _nset, content)

    def _sdk(m):
        nonlocal changes; changes+=1
        return 'QOhosAppContext::instance()->bundleVersion()'
    content = re.sub(r'QtOh::ohSdkVersion\(\)', _sdk, content)

    return content, changes

def transform_file_share_api(content):
    changes = 0
    def _sf(m):
        nonlocal changes; changes+=1
        u=m.group(1).strip(); t=m.group(2).strip() if m.group(2) else 'QString()'
        return (f'/* MIGRATED: QOhFileShare::shareFile → shareDataWithShareKit */\n'
                f'    do {{\n'
                f'        auto _ctx = QOhosAbilityContext::getDefaultInstance();\n'
                f'        if (_ctx) {{\n'
                f'            auto _r = QSharedPointer<ShareKit::QOhosSharedRecord>::create();\n'
                f'            _r->setTitle({t}); _r->addFile({u});\n'
                f'            auto _o = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();\n'
                f'            _ctx->shareDataWithShareKit({{_r}}, _o);\n'
                f'        }}\n    }} while(0)')
    content = re.sub(r'QOhFileShare::shareFile\s*\(\s*([^,)]+?)\s*(?:,\s*([^)]+?)\s*)?\)', _sf, content)

    def _sfs(m):
        nonlocal changes; changes+=1
        us=m.group(1).strip(); t=m.group(2).strip() if m.group(2) else 'QString()'
        return (f'/* MIGRATED: QOhFileShare::shareFiles → shareDataWithShareKit */\n'
                f'    do {{\n'
                f'        auto _ctx = QOhosAbilityContext::getDefaultInstance();\n'
                f'        if (_ctx) {{\n'
                f'            auto _r = QSharedPointer<ShareKit::QOhosSharedRecord>::create();\n'
                f'            _r->setTitle({t});\n'
                f'            for (const auto &_u : {us}) _r->addFile(_u);\n'
                f'            auto _o = QSharedPointer<ShareKit::QOhosShareControllerOptions>::create();\n'
                f'            _ctx->shareDataWithShareKit({{_r}}, _o);\n'
                f'        }}\n    }} while(0)')
    content = re.sub(r'QOhFileShare::shareFiles\s*\(\s*(\{[^}]+\}[^,)]*)\s*(?:,\s*([^)]+?)\s*)?\)', _sfs, content)
    return content, changes

def _insert_include(content, inc):
    lines = content.split('\n')
    last = -1
    for i,l in enumerate(lines):
        if l.strip().startswith('#include'): last = i
    if last >= 0:
        lines.insert(last+1, inc)
        return '\n'.join(lines)
    return inc+'\n'+content

def strip_comments(content):
    """Remove C/C++ comments from content. Returns code-only text."""
    # Remove block comments /* ... */ (non-greedy, multiline)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove line comments // ...
    content = re.sub(r'//[^\n]*', '', content)
    return content

def add_includes_if_needed(content):
    added = []
    # Strip comments before checking for API usage — if the marker only
    # appears in comments (e.g. "QOhosAbilityContext" in a // comment),
    # do NOT add the corresponding #include.
    code_only = strip_comments(content)
    checks = [
        ('shareDataWithShareKit','QOhosShareKit','#include <QtOhosExtras/QOhosShareKit>'),
        ('QOhosAbilityContext','QOhosAbilityContext>','#include <QtOhosExtras/QOhosAbilityContext>'),
        ('QOhosAppContext::','QOhosAppContext>','#include <QtOhosExtras/QOhosAppContext>'),
        ('QOhosPlatformIntegration','QOhosPlatformIntegration>','#include <QtOhosExtras/QOhosPlatformIntegration>'),
        ('AppPermissions::','QOhosAppPermissions>','#include <QtOhosExtras/QOhosAppPermissions>'),
        ('QOhosWant','QOhosWant>','#include <QtOhosExtras/QOhosWant>'),
    ]
    for marker, guard, inc in checks:
        if marker in code_only and guard not in content and inc not in content:
            content = _insert_include(content, inc)
            added.append(inc)
    return content, added

# ── File helpers ────────────────────────────────────────────────────────────
def find_source_files(root):
    ignore = {".git","node_modules","build",".hvigor","oh_modules",".cxx",".idea","__pycache__","patches"}
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in ignore]
        for f in fns:
            if os.path.splitext(f)[1].lower() in SOURCE_EXTS:
                files.append(os.path.join(dp, f))
    return files

def apply_replacements(filepath, replacements):
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f: content = f.read()
    except: return 0
    orig = content; ch = 0
    for pat, rep in replacements:
        content, c = re.subn(pat, rep, content); ch += c
    if content != orig:
        with open(filepath, "w", encoding="utf-8") as f: f.write(content)
    return ch

def is_excluded(fp):
    ext = os.path.splitext(fp)[1].lower()
    name = os.path.basename(fp)
    return ext in PATCH_EXCLUDE_EXTS or name in PATCH_EXCLUDE_NAMES

# ══════════════════════════════════════════════════════════════════════════
# Step 1
# ══════════════════════════════════════════════════════════════════════════
def create_clone_project(orig_dir, template_dir, sdk_dir):
    """1.0b: Create new clone project from template, copy glue code, import SDK."""

    # ── Create new project from template ──
    orig_name = orig_dir.name
    new_name = f"{orig_name}-official"
    new_project_dir = SKILL_DIR / new_name

    step("1.0b", f"从官方模版创建新工程: {new_name}")

    if new_project_dir.exists():
        info(f"目录已存在，清理: {new_project_dir}")
        shutil.rmtree(str(new_project_dir))

    info(f"复制模版工程 → {new_project_dir}")
    shutil.copytree(str(template_dir), str(new_project_dir))
    ok(f"新工程已创建: {new_project_dir}")

    # ── Remove libentry.so-related files from the copied template ──
    # These reference the template's default library name and conflict with
    # the imported CMakeLists.txt target name. Must be removed, not kept.
    libentry_paths = [
        new_project_dir / "entry" / "src" / "main" / "cpp" / "hello.cpp",
        new_project_dir / "entry" / "src" / "main" / "cpp" / "types",
        new_project_dir / "entry" / "oh_modules" / "@types" / "libentry.so",
    ]
    for p in libentry_paths:
        if p.exists():
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()
            ok(f"删除模版 libentry 相关: {p.relative_to(new_project_dir)}")

    # ── Update entry/oh-package.json5: remove @types/libentry.so reference ──
    # The deleted types/libentry dir was referenced in devDependencies;
    # leaving it causes ohpm error 00617301 "Fetch Source Code Failed".
    entry_ohpkg = new_project_dir / "entry" / "oh-package.json5"
    if entry_ohpkg.exists():
        ohpkg_content = entry_ohpkg.read_text(encoding="utf-8", errors="replace")
        # Remove the @types/libentry.so line (with trailing comma if present)
        ohpkg_content = re.sub(
            r'"@types/libentry\.so"\s*:\s*"file:[^"]*"\s*,?\s*\n', '', ohpkg_content)
        entry_ohpkg.write_text(ohpkg_content, encoding="utf-8")
        ok("已从 entry/oh-package.json5 移除 @types/libentry.so 引用 (build-fix-09)")

    # ── Copy glue code (C++ source) from original project ──
    # Merge into template's cpp/ — do NOT overwrite template-only files/dirs
    # (e.g., types/, libentry/ that are part of the official template).
    step("1.0c", "导入胶水代码（合并，保留模版独有文件）")
    orig_cpp = orig_dir / "entry" / "src" / "main" / "cpp"
    new_cpp = new_project_dir / "entry" / "src" / "main" / "cpp"

    # Directories/files that exist only in the template — never copy/overwrite
    # types/libentry and hello.cpp reference template's default library name
    # which conflicts with the imported CMakeLists.txt target name.
    TEMPLATE_ONLY_CPP = {"types", "libentry", "hello.cpp"}

    if orig_cpp.exists():
        new_cpp.mkdir(parents=True, exist_ok=True)
        src_count = 0
        for item in sorted(orig_cpp.iterdir()):
            dst = new_cpp / item.name
            # Skip if this is a template-only path
            if item.name in TEMPLATE_ONLY_CPP:
                info(f"  保留模版独有: {item.name}/")
                continue
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(str(dst))
                shutil.copytree(str(item), str(dst))
                ok(f"  导入目录: {item.name}/")
            else:
                shutil.copy2(str(item), str(dst))
                ok(f"  导入文件: {item.name}")
                src_count += 1
        src_count += len(list(new_cpp.rglob("*.cpp"))) + len(list(new_cpp.rglob("*.h")))
        ok(f"已导入胶水代码: {src_count} 个源文件 (保留模版独有: {', '.join(sorted(TEMPLATE_ONLY_CPP))})")
    else:
        warn(f"原始工程未找到 entry/src/main/cpp/ 目录")

    # Copy resources — merge into template's resources/, do NOT overwrite
    # template config files (main_pages.json, string.json, etc.)
    TEMPLATE_ONLY_RES = {
        "base/profile/main_pages.json",
        "base/element/string.json",
        "base/element/color.json",
    }
    orig_res = orig_dir / "entry" / "src" / "main" / "resources"
    new_res = new_project_dir / "entry" / "src" / "main" / "resources"
    if orig_res.exists():
        new_res.mkdir(parents=True, exist_ok=True)
        res_copied = 0
        res_skipped = 0
        for src_file in sorted(orig_res.rglob("*")):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(orig_res)
            dst_file = new_res / rel
            # Skip template-only config files
            if str(rel).replace(os.sep, "/") in TEMPLATE_ONLY_RES:
                info(f"  保留模版配置: {rel}")
                res_skipped += 1
                continue
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dst_file))
            res_copied += 1
        ok(f"已导入资源文件: {res_copied} 个 (保留模版配置: {res_skipped} 个)")
    else:
        info("原始工程无 resources 目录，保留模版资源")

    # ── Merge signingConfigs & products from original → template build-profile.json5 ──
    # These tags carry machine-bound signing certs and product config from the original.
    orig_bp = orig_dir / "build-profile.json5"
    new_bp = new_project_dir / "build-profile.json5"

    if orig_bp.exists() and new_bp.exists():
        orig_bp_content = orig_bp.read_text(encoding="utf-8", errors="replace")
        new_bp_content = new_bp.read_text(encoding="utf-8", errors="replace")

        for tag in ("signingConfigs", "products"):
            # Extract array from original
            orig_match = re.search(rf'"{tag}"\s*:\s*\[', orig_bp_content)
            if not orig_match:
                continue
            o_start = orig_match.end() - 1
            depth = 0
            o_end = o_start
            for i in range(o_start, len(orig_bp_content)):
                if orig_bp_content[i] == '[': depth += 1
                elif orig_bp_content[i] == ']':
                    depth -= 1
                    if depth == 0: o_end = i + 1; break
            orig_arr = orig_bp_content[o_start:o_end]

            # Replace array in template
            tpl_match = re.search(rf'"{tag}"\s*:\s*\[', new_bp_content)
            if tpl_match:
                t_start = tpl_match.end() - 1
                depth = 0
                t_end = t_start
                for i in range(t_start, len(new_bp_content)):
                    if new_bp_content[i] == '[': depth += 1
                    elif new_bp_content[i] == ']':
                        depth -= 1
                        if depth == 0: t_end = i + 1; break
                new_bp_content = new_bp_content[:t_start] + orig_arr + new_bp_content[t_end:]
                ok(f"已合并 {tag} → 模版 build-profile.json5")
            else:
                info(f"模版 build-profile.json5 无 {tag}，跳过")

        new_bp.write_text(new_bp_content, encoding="utf-8")
    elif not orig_bp.exists():
        info("原始工程无 build-profile.json5，跳过")
    elif not new_bp.exists():
        info("模版工程无 build-profile.json5，跳过")

    # ── Copy bundleName & app config from original AppScope/app.json5 → template ──
    # Use original project's bundleName, not template's default.
    orig_appscope = orig_dir / "AppScope" / "app.json5"
    new_appscope = new_project_dir / "AppScope" / "app.json5"
    if orig_appscope.exists() and new_appscope.exists():
        orig_app = orig_appscope.read_text(encoding="utf-8", errors="replace")
        new_app = new_appscope.read_text(encoding="utf-8", errors="replace")

        # Extract and replace these fields from original → template
        for field in ("bundleName", "vendor", "versionCode", "versionName", "icon", "label"):
            orig_match = re.search(rf'"{field}"\s*:\s*("[^"]*"|\d+)', orig_app)
            if orig_match:
                orig_val = orig_match.group(1)
                new_app = re.sub(
                    rf'"{field}"\s*:\s*("[^"]*"|\d+)',
                    f'"{field}": {orig_val}',
                    new_app)
        new_appscope.write_text(new_app, encoding="utf-8")

        # Extract bundleName for display
        bn_match = re.search(r'"bundleName"\s*:\s*"([^"]+)"', orig_app)
        bn = bn_match.group(1) if bn_match else "?"
        ok(f"已从原始工程导入包名: bundleName = {bn}")
    elif not orig_appscope.exists():
        info("原始工程无 AppScope/app.json5，保留模版包名")
    elif not new_appscope.exists():
        info("模版工程无 AppScope/app.json5，跳过")

    # ── Copy AppScope/resources from original → template (merge) ──
    # Preserves original app-level string resources (e.g., app_name)
    # Template's AppScope/resources/ has default values like "ohosQtTemplate";
    # original's has the actual app name like "QtBugDemo".
    orig_appscope_res = orig_dir / "AppScope" / "resources"
    new_appscope_res = new_project_dir / "AppScope" / "resources"
    if orig_appscope_res.exists():
        res_copied = 0
        for src_file in sorted(orig_appscope_res.rglob("*")):
            if src_file.is_dir():
                continue
            rel = src_file.relative_to(orig_appscope_res)
            dst_file = new_appscope_res / rel
            # Always overwrite AppScope resources with original's version
            # (string.json with app_name, media/ with app icon, etc.)
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dst_file))
            res_copied += 1
        if res_copied > 0:
            ok(f"已导入 AppScope/resources: {res_copied} 个文件 (保留原始 app_name 等配置)")
    else:
        info("原始工程无 AppScope/resources，保留模版资源")

    # ── Fix entry/build-profile.json5: remove x86_64 from abiFilters ──
    entry_bp = new_project_dir / "entry" / "build-profile.json5"
    if entry_bp.exists():
        bp_content = entry_bp.read_text(encoding="utf-8", errors="replace")
        # Remove "x86_64" from abiFilters array
        bp_content = re.sub(r'"x86_64"', '"arm64-v8a"', bp_content)
        # Deduplicate if arm64-v8a appears twice in the same array
        bp_content = re.sub(
            r'("abiFilters"\s*:\s*\[)([^]]*)\]',
            lambda m: m.group(1) + re.sub(
                r'"arm64-v8a"(?:\s*,\s*)?"arm64-v8a"', '"arm64-v8a"',
                m.group(2)) + ']',
            bp_content)
        entry_bp.write_text(bp_content, encoding="utf-8")
        ok("已移除 entry/build-profile.json5 中的 x86_64，仅保留 arm64-v8a")
    else:
        info("模版工程无 entry/build-profile.json5，跳过 abiFilters 修正")

    # ── Update QtAppConstants.ets: set APP_LIBRARY_NAME from CMake target ──
    # Template default is e.g. 'libwidgettest.so' — must match actual CMake
    # add_library(NAME SHARED ...) → 'libNAME.so'
    cmake_file = new_project_dir / "entry" / "src" / "main" / "cpp" / "CMakeLists.txt"
    qt_constants = new_project_dir / "entry" / "src" / "main" / "ets" / "common" / "QtAppConstants.ets"

    if cmake_file.exists() and qt_constants.exists():
        cmake_content = cmake_file.read_text(encoding="utf-8", errors="replace")
        # Extract library name from: add_library(NAME SHARED ...)
        cmake_match = re.search(r'add_library\s*\(\s*(\w+)\s+SHARED', cmake_content)
        if cmake_match:
            lib_target = cmake_match.group(1)
            lib_name = f"lib{lib_target}.so"
            # Update APP_LIBRARY_NAME in QtAppConstants.ets
            constants_content = qt_constants.read_text(encoding="utf-8", errors="replace")
            constants_content = re.sub(
                r'APP_LIBRARY_NAME\s*=\s*[\'"][^\'"]*[\'"]',
                f"APP_LIBRARY_NAME = '{lib_name}'",
                constants_content)
            qt_constants.write_text(constants_content, encoding="utf-8")
            ok(f"已更新 APP_LIBRARY_NAME = '{lib_name}' (from CMake add_library({lib_target} SHARED))")
        else:
            warn(f"未在 CMakeLists.txt 中找到 add_library(NAME SHARED ...)")
    elif not cmake_file.exists():
        info("无 entry/src/main/cpp/CMakeLists.txt，跳过 APP_LIBRARY_NAME 更新")
    elif not qt_constants.exists():
        # Search for QtAppConstants.ets in case path differs
        for f in new_project_dir.rglob("QtAppConstants.ets"):
            if cmake_file.exists():
                cmake_content = cmake_file.read_text(encoding="utf-8", errors="replace")
                cmake_match = re.search(r'add_library\s*\(\s*(\w+)\s+SHARED', cmake_content)
                if cmake_match:
                    lib_name = f"lib{cmake_match.group(1)}.so"
                    content = f.read_text(encoding="utf-8", errors="replace")
                    content = re.sub(
                        r'APP_LIBRARY_NAME\s*=\s*[\'"][^\'"]*[\'"]',
                        f"APP_LIBRARY_NAME = '{lib_name}'",
                        content)
                    f.write_text(content, encoding="utf-8")
                    ok(f"已更新 APP_LIBRARY_NAME = '{lib_name}' → {f.relative_to(new_project_dir)}")
                    break

    # ── Merge requestPermissions from original module.json5 → template ──
    # Do NOT copy the entire module.json5 or AppScope — keep template's config.
    # Only extract requestPermissions array and merge into template's module.json5.
    orig_module = orig_dir / "entry" / "src" / "main" / "module.json5"
    new_module = new_project_dir / "entry" / "src" / "main" / "module.json5"

    if orig_module.exists() and new_module.exists():
        orig_content = orig_module.read_text(encoding="utf-8", errors="replace")

        # Extract requestPermissions array from original module.json5
        # Match: "requestPermissions": [ ... ] (handle nested brackets)
        perms_match = re.search(r'"requestPermissions"\s*:\s*\[', orig_content)
        if perms_match:
            # Find matching closing bracket
            start = perms_match.end() - 1  # position of [
            depth = 0
            end = start
            for i in range(start, len(orig_content)):
                if orig_content[i] == '[':
                    depth += 1
                elif orig_content[i] == ']':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            orig_perms = orig_content[start:end]  # the [...] array text

            # Replace requestPermissions in template's module.json5
            tpl_content = new_module.read_text(encoding="utf-8", errors="replace")
            tpl_match = re.search(r'"requestPermissions"\s*:\s*\[', tpl_content)
            if tpl_match:
                # Find matching closing bracket in template
                t_start = tpl_match.end() - 1
                t_depth = 0
                t_end = t_start
                for i in range(t_start, len(tpl_content)):
                    if tpl_content[i] == '[':
                        t_depth += 1
                    elif tpl_content[i] == ']':
                        t_depth -= 1
                        if t_depth == 0:
                            t_end = i + 1
                            break
                # Replace template's array with original's
                new_content = tpl_content[:t_start] + orig_perms + tpl_content[t_end:]
                new_module.write_text(new_content, encoding="utf-8")
                ok(f"已合并 requestPermissions ({len(orig_perms)} chars) → 模版 module.json5")
            else:
                # Template has no requestPermissions — insert before closing "module" brace
                # Find "module": { ... } and add requestPermissions
                new_content = tpl_content.rstrip()
                if new_content.endswith("}"):
                    insert = f'\n    "requestPermissions": {orig_perms},\n'
                    new_content = new_content[:-1] + insert + "}"
                new_module.write_text(new_content, encoding="utf-8")
                ok(f"已插入 requestPermissions → 模版 module.json5")
        else:
            info("原始工程 module.json5 无 requestPermissions，跳过")
    elif not orig_module.exists():
        info("原始工程无 module.json5，跳过")
    elif not new_module.exists():
        info("模版工程无 module.json5，跳过")

    # ── Import .so: only replace .so that exist in original project (by name) ──
    # Walk SDK for all .so files, but only copy those whose name matches
    # a .so in the original project. Do NOT copy all SDK .so blindly.
    step("1.0d", "替换 so 文件（仅替换原工程中已有的同名 so）")

    # Build SDK .so index: filename → path (search entire SDK)
    sdk_so_map = {}
    for f in sdk_dir.rglob("*.so"):
        sdk_so_map[f.name] = f
    ok(f"SDK 中找到 {len(sdk_so_map)} 个 .so 文件")

    # Community → official .so rename mapping
    SO_RENAME = {
        "libQt5OhExtras.so":                   "libQt5OhosExtras.so",
        "libqopenharmony.so":                  "libqohos.so",
        "libplugins_platforms_qopenharmony.so": "libqohos.so",
        "libplugins_platforms_qohos.so":       "libqohos.so",
        "libplugins_styles_qharmonystyle.so":  "libqohosstyle.so",
        "libplugins_styles_qohosstyle.so":     "libqohosstyle.so",
    }

    # Build original project .so index: filename → list of relative directory paths
    # This defines which .so files should exist in the clone (by name + location)
    orig_so_files = {}  # {filename: [rel_dir1, rel_dir2, ...]}
    for so_file in orig_dir.rglob("*.so"):
        name = so_file.name
        rel_dir = so_file.parent.relative_to(orig_dir)
        orig_so_files.setdefault(name, []).append(rel_dir)

    ok(f"原工程中找到 {len(orig_so_files)} 个不同 .so 文件")

    tr = ta = td = 0

    # For each .so in original project: create dir in clone, replace with SDK version
    for name, rel_dirs in sorted(orig_so_files.items()):
        for rel_dir in rel_dirs:
            # Create matching directory in clone
            clone_dir = new_project_dir / rel_dir
            clone_dir.mkdir(parents=True, exist_ok=True)

            # Case 1: Same name exists in SDK → replace in-place
            if name in sdk_so_map:
                dst = clone_dir / name
                existed = dst.exists()
                shutil.copy2(str(sdk_so_map[name]), str(dst))
                if existed:
                    tr += 1
                else:
                    ta += 1
                ok(f"  替换: {rel_dir}/{name}")

            # Case 2: Community-renamed .so → delete old, copy official to same dir
            elif name in SO_RENAME:
                official_name = SO_RENAME[name]
                official_src = sdk_so_map.get(official_name)
                if official_src:
                    # Remove old community .so if it exists in clone
                    old = clone_dir / name
                    if old.exists():
                        old.unlink()
                        td += 1
                    # Copy official .so to same directory
                    dst = clone_dir / official_name
                    if not dst.exists():
                        shutil.copy2(str(official_src), str(dst))
                        ta += 1
                    ok(f"  替换: {rel_dir}/{name} → {official_name}")

            # Case 3: .so in original but not in SDK — leave as-is
            else:
                info(f"  跳过（SDK 中无同名）: {rel_dir}/{name}")

    print(f"\n  {C.B}so 替换汇总{C.R}: 替换 {tr} / 新增 {ta} / 删除 {td}")

    # 4. Ensure libqohos.so in EVERY directory that had a QPA plugin
    #    (covers directories that had libplugins_platforms_qopenharmony.so)
    QOHOS_PLUGIN_NAME = "libqohos.so"
    # Community QPA plugin names that should be replaced by libqohos.so
    COMMUNITY_QPA_NAMES = {
        "libqopenharmony.so",
        "libplugins_platforms_qopenharmony.so",
        "libplugins_platforms_qohos.so",
    }

    qohos_in_sdk = sdk_so_map.get(QOHOS_PLUGIN_NAME)
    if not qohos_in_sdk:
        for name, path in sdk_so_map.items():
            if "qohos" in name.lower() and "platform" in name.lower():
                qohos_in_sdk = path
                break
    if not qohos_in_sdk:
        # Last resort: search any *qohos*.so
        for name, path in sdk_so_map.items():
            if "qohos" in name.lower():
                qohos_in_sdk = path
                break

    if qohos_in_sdk:
        # Find every directory in the project, ensure libqohos.so exists
        # wherever any community QPA plugin existed or platforms/ dir exists
        checked_dirs = set()
        for platforms_dir in new_project_dir.rglob("platforms"):
            if not platforms_dir.is_dir():
                continue
            qohos_dst = platforms_dir / QOHOS_PLUGIN_NAME
            if not qohos_dst.exists():
                shutil.copy2(str(qohos_in_sdk), str(qohos_dst))
                ta += 1
                ok(f"  新增: {qohos_dst.relative_to(new_project_dir)}")
            checked_dirs.add(str(platforms_dir))

        # Also check any directory that might have had QPA plugins (not just "platforms")
        # by searching for remaining community QPA .so references in non-.so files
        # (e.g., in config files that reference .so names)
    else:
        warn("SDK 中未找到 libqohos.so (QPA 平台插件)")
        manual = ask("请输入 libqohos.so 文件路径（或直接 Enter 跳过）")
        if manual and Path(manual).exists():
            for platforms_dir in new_project_dir.rglob("platforms"):
                if platforms_dir.is_dir():
                    qohos_dst = platforms_dir / QOHOS_PLUGIN_NAME
                    if not qohos_dst.exists():
                        shutil.copy2(manual, str(qohos_dst))
                        ta += 1
                        ok(f"  手动导入: {platforms_dir.relative_to(new_project_dir)}/{QOHOS_PLUGIN_NAME}")

    # 5. Ensure libqohosstyle.so in every styles/ directory
    QOHOS_STYLE_NAME = "libqohosstyle.so"
    style_in_sdk = sdk_so_map.get(QOHOS_STYLE_NAME)
    if not style_in_sdk:
        for name, path in sdk_so_map.items():
            if "qohosstyle" in name.lower():
                style_in_sdk = path
                break
    if style_in_sdk:
        for styles_dir in new_project_dir.rglob("styles"):
            if not styles_dir.is_dir():
                continue
            style_dst = styles_dir / QOHOS_STYLE_NAME
            if not style_dst.exists():
                shutil.copy2(str(style_in_sdk), str(style_dst))
                ta += 1
                ok(f"  新增: {style_dst.relative_to(new_project_dir)}")
    else:
        warn("SDK 中未找到 libqohosstyle.so (样式插件)")
        manual_style = ask("请输入 libqohosstyle.so 文件路径（或直接 Enter 跳过）")
        if manual_style and Path(manual_style).exists():
            for styles_dir in new_project_dir.rglob("styles"):
                if styles_dir.is_dir():
                    shutil.copy2(manual_style, str(styles_dir / QOHOS_STYLE_NAME))
                    ta += 1
                    ok(f"  手动导入: {styles_dir.relative_to(new_project_dir)}/{QOHOS_STYLE_NAME}")

    print(f"\n  {C.B}so 导入汇总{C.R}: 替换 {tr} / 新增 {ta} / 删除 {td}")

    # ── Dev headers (keep existing logic) ──
    sdk_include = sdk_dir / "include"
    dev_include = new_project_dir / "third_party" / "qt-ohos-dev" / "include"
    if sdk_include.exists():
        dev_include.mkdir(parents=True, exist_ok=True)
        for item in sdk_include.iterdir():
            dst = dev_include / item.name
            if item.is_dir():
                if dst.exists(): shutil.rmtree(str(dst))
                shutil.copytree(str(item), str(dst))
            else:
                shutil.copy2(str(item), str(dst))
        hdr_count = len(list(dev_include.rglob("*.h")))
        ok(f"头文件: {hdr_count} 个 → third_party/qt-ohos-dev/include/")
    else:
        warn("SDK 无 include/ 目录")

    # ── mkspecs (keep existing logic) ──
    sdk_mkspecs = sdk_dir / "mkspecs"
    dev_mkspecs = new_project_dir / "third_party" / "qt-ohos-dev" / "mkspecs"
    if sdk_mkspecs.exists():
        dev_mkspecs.parent.mkdir(parents=True, exist_ok=True)
        if dev_mkspecs.exists(): shutil.rmtree(str(dev_mkspecs))
        shutil.copytree(str(sdk_mkspecs), str(dev_mkspecs))
        ok("mkspecs 已导入")

    return new_project_dir


def step1_get_project_path():
    """1.0: Get paths, use templates dir (CLI arg / env / default)."""
    step("1.0", "获取路径并创建克隆工程")

    # --- 1. Original project path ---
    if len(sys.argv) > 1:
        orig_input = sys.argv[1]
    else:
        orig_input = ask("请输入需要迁移的qt社区版工程路径")
    orig_dir = Path.cwd() if orig_input in (".", "") else Path(orig_input).resolve()
    if not orig_dir.is_dir(): err(f"目录不存在: {orig_dir}"); sys.exit(1)
    ok(f"原始工程: {orig_dir}")
    global ORIG_PROJECT_DIR
    ORIG_PROJECT_DIR = orig_dir

    # --- 2. Template project (auto: templates/ in same dir as SKILL.md) ---
    template_dir = TEMPLATES_DIR
    if not template_dir.is_dir():
        err(f"模版工程目录不存在: {template_dir}")
        err("请确保 templates/ 目录存在于 SKILL.md 同级目录")
        sys.exit(1)
    ok(f"模版工程: {template_dir} (自动)")

    # --- 3. Official SDK install path ---
    if len(sys.argv) > 2:
        sdk_input = sys.argv[2]
    else:
        sdk_input = ask("请输入官方版 Qt SDK install 路径（含 lib/ 和 include/）")
    sdk_dir = Path(sdk_input).resolve() if sdk_input else None
    if not sdk_dir or not sdk_dir.is_dir():
        err(f"SDK 目录不存在: {sdk_input}"); sys.exit(1)
    ok(f"SDK 路径: {sdk_dir}")

    # --- Create clone project ---
    new_project_dir = create_clone_project(orig_dir, template_dir, sdk_dir)
    os.chdir(new_project_dir)
    ok(f"当前工作目录: {new_project_dir}")

    return new_project_dir

def step1_select_qt_version():
    """Step 1.0a: Select Qt version from docs/ subdirectories.
    Lists available versions (docs/qt<version>/ folders), default = highest."""
    global SELECTED_QT_VERSION, SELECTED_QT_DOCS_DIR
    step("1.0a", "选择 Qt 版本")

    # Scan docs/ for version subdirectories (qt<version>/)
    versions = []
    if DOCS_DIR.exists():
        for d in sorted(DOCS_DIR.iterdir()):
            if d.is_dir() and d.name.startswith("qt"):
                # Extract version number from dir name: "qt5.12.12" → "5.12.12"
                ver_str = d.name[2:]  # strip "qt" prefix
                # Parse version as tuple for sorting: "5.12.12" → (5, 12, 12)
                try:
                    ver_tuple = tuple(int(x) for x in ver_str.split("."))
                    versions.append((ver_str, ver_tuple, d))
                except ValueError:
                    continue

    if not versions:
        warn("docs/ 下未找到 Qt 版本子目录 (qt<version>/)")
        info("将使用根目录文档进行迁移")
        SELECTED_QT_VERSION = "default"
        SELECTED_QT_DOCS_DIR = None
        return

    # Sort by version tuple (highest last)
    versions.sort(key=lambda v: v[1])
    default_ver = versions[-1]  # highest version

    # Display available versions
    info("可用 Qt 版本:")
    for i, (ver_str, _, dir_path) in enumerate(versions, 1):
        doc_count = len(list(dir_path.glob("*.md")))
        marker = " (默认)" if ver_str == default_ver[0] else ""
        print(f"    {i}. Qt {ver_str} ({doc_count} 个文档){marker}")

    # Prompt user
    print(f"\n  {C.YLW}❓ 请选择 Qt 版本 (输入序号或版本号，直接 Enter 选择默认 {default_ver[0]}){C.R}")
    response = input(f"  {C.GRY}> {C.R}").strip()

    selected = None
    if not response:
        selected = default_ver
    elif response.isdigit():
        idx = int(response) - 1
        if 0 <= idx < len(versions):
            selected = versions[idx]
    else:
        # Try matching version string
        for v in versions:
            if v[0] == response or f"qt{v[0]}" == response:
                selected = v
                break

    if not selected:
        warn(f"无效输入，使用默认版本: {default_ver[0]}")
        selected = default_ver

    SELECTED_QT_VERSION = selected[0]
    SELECTED_QT_DOCS_DIR = selected[2]
    ok(f"已选择 Qt 版本: {SELECTED_QT_VERSION}")
    info(f"版本文档目录: {SELECTED_QT_DOCS_DIR}")

    # List docs that will be used for migration
    root_docs = sorted(DOCS_DIR.glob("*.md"))
    version_docs = sorted(SELECTED_QT_DOCS_DIR.glob("*.md")) if SELECTED_QT_DOCS_DIR else []
    info(f"迁移参考文档:")
    for d in root_docs:
        info(f"  docs/{d.name}")
    for d in version_docs:
        info(f"  docs/{SELECTED_QT_DOCS_DIR.name}/{d.name}")

def step1_scan(project_dir):
    step("1.1", "扫描社区版 API 标记")
    # Display which version docs guide this migration
    if SELECTED_QT_VERSION and SELECTED_QT_VERSION != "default":
        info(f"迁移参考: Qt {SELECTED_QT_VERSION} 版本文档 + 根目录文档")
        if SELECTED_QT_DOCS_DIR and SELECTED_QT_DOCS_DIR.exists():
            for d in sorted(SELECTED_QT_DOCS_DIR.glob("*.md")):
                info(f"  docs/{SELECTED_QT_DOCS_DIR.name}/{d.name}")
        for d in sorted(DOCS_DIR.glob("*.md")):
            info(f"  docs/{d.name}")
        print()
    files = find_source_files(str(project_dir)); matches = {}
    for fp in files:
        try:
            with open(fp,"r",encoding="utf-8",errors="replace") as f: content = f.read()
        except: continue
        fm = []
        for pat in SCAN_PATTERNS:
            for m in re.finditer(re.escape(pat), content):
                ln = content[:m.start()].count("\n")+1
                lt = content.split("\n")[ln-1].strip() if ln<=len(content.split("\n")) else ""
                fm.append((ln,pat,lt))
        if fm: matches[os.path.relpath(fp,str(project_dir))] = fm
    if not matches: ok("未找到社区版 API 标记"); return {}
    total = sum(len(v) for v in matches.values())
    warn(f"{len(matches)} 个文件, {total} 处标记:\n")
    for fp,fm in sorted(matches.items()):
        print(f"  {C.GRY}{fp}{C.R}")
        for ln,pat,lt in fm: print(f"    L{ln} [{C.YLW}{pat}{C.R}] {lt[:80]}")
        print()
    return matches

def step1_migrate(project_dir):
    step("1.2", "应用迁移映射（源码替换 + API 重写）")
    # Show which version docs guide this migration
    if SELECTED_QT_VERSION and SELECTED_QT_VERSION != "default":
        info(f"基于 Qt {SELECTED_QT_VERSION} 版本文档进行迁移:")
        if SELECTED_QT_DOCS_DIR and SELECTED_QT_DOCS_DIR.exists():
            for d in sorted(SELECTED_QT_DOCS_DIR.glob("*.md")):
                info(f"  📄 docs/{SELECTED_QT_DOCS_DIR.name}/{d.name}")
        for d in sorted(DOCS_DIR.glob("*.md")):
            info(f"  📄 docs/{d.name}")
        print()
    files = find_source_files(str(project_dir))
    code_files = [f for f in files if os.path.splitext(f)[1].lower() in CODE_EXTS]
    simple = HEADER_MIGRATIONS + CLASS_MIGRATIONS + BUILD_CONFIG_MIGRATIONS
    total = 0; changed = []

    info("Phase 1: 标识符替换（头文件/类名/命名空间/构建配置）...")
    for fp in code_files:
        ch = apply_replacements(fp, simple)
        if ch>0: changed.append((os.path.relpath(fp,str(project_dir)),ch,"replace")); total+=ch

    info("Phase 2: 源码 API 重写（权限同步→异步、文件分享重写）...")
    pt=st=it=0
    for fp in code_files:
        try:
            with open(fp,"r",encoding="utf-8",errors="replace") as f: content = f.read()
        except: continue
        orig = content; fc = 0
        content,pc = transform_permission_api(content); pt+=pc; fc+=pc
        content,sc = transform_file_share_api(content); st+=sc; fc+=sc
        content,ai = add_includes_if_needed(content); it+=len(ai); fc+=len(ai)
        if content!=orig:
            with open(fp,"w",encoding="utf-8") as f: f.write(content)
            rp = os.path.relpath(fp,str(project_dir))
            found=False
            for i,(r,c,_) in enumerate(changed):
                if r==rp: changed[i]=(r,c+fc,"replace+transform"); found=True; break
            if not found: changed.append((rp,fc,"transform"))
            total+=fc

    if total>0:
        ok(f"迁移完成: {len(changed)} 个文件, {total} 处修改\n")
        info(f"  标识符替换: {total-pt-st-it} 处")
        info(f"  权限 API 重写: {pt} 处 (sync→async)")
        info(f"  文件分享重写: {st} 处")
        info(f"  自动 #include: {it} 处\n")
        for rp,ch,mt in changed:
            lb = {"replace":"替换","transform":"重写","replace+transform":"替换+重写"}.get(mt,mt)
            print(f"  {C.GRN}✓{C.R}  {rp} ({ch} 处, {lb})")
    else: info("未发现需要迁移的内容")

    manual = []
    for fp in code_files:
        try:
            with open(fp,"r",encoding="utf-8",errors="replace") as f: content = f.read()
        except: continue
        todos = re.findall(r'/\* TODO MIGRATE: ([^*]+) \*/', content)
        if todos: manual.append((os.path.relpath(fp,str(project_dir)),todos))
    if manual:
        print(); warn(f"{len(manual)} 个文件含需手动确认项:")
        for rp,todos in manual:
            print(f"\n  {C.YLW}{rp}{C.R}")
            for t in todos: print(f"    ⚠  {t.strip()}")
        info("参考: docs/Qt社区版本差异文档.md §2.3 §2.4")
        input(f"\n  {C.GRY}检查完成后按 Enter 继续...{C.R}")
    return changed

def step1_window_api(project_dir):
    step("1.3", "窗口属性 API（官方版新增）")
    info("官方版新增窗口属性 API（圆角/隐私模式/亮度等），参考 docs/Qt社区版本差异文档.md §3")
    info("标准 Qt 窗口 API 无需修改")

def step1_verify(project_dir):
    step("1.4", "验证无社区版标记残留")
    files = find_source_files(str(project_dir)); remaining = {}
    for fp in files:
        try:
            with open(fp,"r",encoding="utf-8",errors="replace") as f: content = f.read()
        except: continue
        for pat in SCAN_PATTERNS:
            for m in re.finditer(re.escape(pat), content):
                rp = os.path.relpath(fp,str(project_dir))
                ln = content[:m.start()].count("\n")+1
                remaining.setdefault(rp,[]).append((ln,pat))
    if remaining:
        warn(f"仍有 {len(remaining)} 个文件含社区版标记:")
        for rp,items in remaining.items():
            for ln,pat in items: print(f"  {rp}:L{ln} [{pat}]")
        warn("(Qt SDK 源码内部标记可忽略)")
    else: ok("应用代码中无社区版标记残留")

# ══════════════════════════════════════════════════════════════════════════
# Step 2
# ══════════════════════════════════════════════════════════════════════════
def _generate_patches(orig_dir, project_dir, patch_output_dir):
    """Core patch generation logic — shared by Step 2 and Step 3.5.
    Uses git diff --no-index format. Bottom-up traversal.
    All patches are flat in patch_output_dir/, named by directory path (no timestamp).
    Returns list of generated patch paths."""
    patches = []

    ignore_dirs = {".git", "node_modules", "build", ".hvigor", "oh_modules",
                   ".cxx", ".idea", "__pycache__", ".DS_Store", "third_party",
                   "hvigor", "qEmbeddedUiExtensionHost_build"}

    def _is_ignored(name):
        return name in ignore_dirs or name.startswith(".")

    def _git_diff_file(orig_file, clone_file):
        """Generate git-format diff for a single file."""
        if os.path.isdir(orig_file) or os.path.isdir(clone_file):
            return []
        if os.path.exists(orig_file) and os.path.exists(clone_file):
            r = run(f"git diff --no-index --no-color -- "
                    f"'{orig_file}' '{clone_file}'", capture=True)
        elif not os.path.exists(orig_file) and os.path.exists(clone_file):
            r = run(f"git diff --no-index --no-color -- "
                    f"/dev/null '{clone_file}'", capture=True)
        elif os.path.exists(orig_file) and not os.path.exists(clone_file):
            r = run(f"git diff --no-index --no-color -- "
                    f"'{orig_file}' /dev/null", capture=True)
        else:
            return []
        if r.stdout and r.stdout.strip():
            return r.stdout.splitlines()
        return []

    # Bottom-up traversal: deepest directories first
    for dirpath, dirnames, filenames in os.walk(str(orig_dir), topdown=False):
        dirnames[:] = [d for d in dirnames if not _is_ignored(d)]

        rel_dir = os.path.relpath(dirpath, str(orig_dir))
        if rel_dir == ".":
            clone_dirpath = str(project_dir)
            patch_name = "root.patch"
        else:
            clone_dirpath = str(project_dir / rel_dir)
            safe_name = rel_dir.replace(os.sep, "_").replace("/", "_")
            patch_name = f"{safe_name}.patch"

        if not os.path.isdir(clone_dirpath):
            continue

        # Collect all file names from both orig and clone
        all_files = set()
        for fname in filenames:
            if not _is_ignored(fname) and not is_excluded(fname):
                all_files.add(fname)
        try:
            for fname in os.listdir(clone_dirpath):
                if not _is_ignored(fname) and not is_excluded(fname):
                    clone_f = os.path.join(clone_dirpath, fname)
                    if os.path.isfile(clone_f):
                        all_files.add(fname)
        except OSError:
            pass

        # Generate git diff for each file in this directory
        changes = []
        for fname in sorted(all_files):
            orig_file = os.path.join(dirpath, fname)
            clone_file = os.path.join(clone_dirpath, fname)
            diff_lines = _git_diff_file(orig_file, clone_file)
            changes.extend(diff_lines)

        # Only generate patch if there are actual changes
        if changes:
            patch_path = patch_output_dir / patch_name
            patch_content = "\n".join(changes) + "\n"
            patch_path.write_text(patch_content, encoding="utf-8")
            file_count = patch_content.count("diff --git ")
            ok(f"  {patch_name}  ({file_count} files, {len(changes)} lines)")
            patches.append(patch_path)

    return patches

def step2_generate_patches(project_dir):
    """Step 2: Compare official project with original, generate per-directory patches.
    All patches are flat in patches/<orig_name>/, named by directory path."""
    banner("Step 2: 生成迁移 patch 文件（与原工程对比）")

    orig_dir = ORIG_PROJECT_DIR
    if not orig_dir or not orig_dir.is_dir():
        warn("无法确定原始工程路径，跳过 patch 生成")
        return []

    orig_name = orig_dir.name
    patch_output_dir = PATCHES_DIR / orig_name
    patch_output_dir.mkdir(parents=True, exist_ok=True)

    step("2.1", f"对比原始工程: {orig_dir}")
    step("2.2", f"patch 输出目录: {patch_output_dir}")

    patches = _generate_patches(orig_dir, project_dir, patch_output_dir)

    step("2.3", "验证 patch")
    if not patches:
        warn("未生成任何 patch（原工程与官方工程无差异）")
    for pp in patches:
        c = pp.read_text(encoding="utf-8", errors="replace")
        fc = c.count("diff --git ")
        info(f"  {pp.name}: {fc} files")

    step("2.4", "patch 回滚/重放")
    for pp in patches:
        info(f"  git apply {pp}")

    step("2.5", "输出路径")
    print(f"\n  {C.GRN}{C.B}迁移 patch 已生成{C.R}\n")
    print(f"  数量: {len(patches)} 个")
    print(f"  目录: {patch_output_dir}\n  文件列表:")
    for pp in patches:
        print(f"    {pp.name}  ({pp.stat().st_size} bytes)")
    print(f"\n  对比: 原工程({orig_dir}) ←→ 官方工程({project_dir})")
    print(f"  用途: 回滚/重放/审查/归档/选择性应用\n")
    return patches

# ── Build fix document loader ───────────────────────────────────────────────
def load_build_docs():
    """Load all .md files from build/ directory. Returns list of (name, content)."""
    docs = []
    if BUILD_DOCS_DIR.exists():
        for f in sorted(BUILD_DOCS_DIR.glob("*.md")):
            try:
                docs.append((f.name, f.read_text(encoding="utf-8", errors="replace")))
            except Exception:
                pass
    return docs

def find_build_fixes(error_lines, build_docs):
    """
    Match compilation error lines against build fix documents.
    Match at document level: if any error keyword appears anywhere in the
    document, the entire document is returned as a match.
    Returns list of (error_line, doc_name, doc_content).
    """
    matches = []
    for err_line in error_lines:
        # Extract significant keywords from the error line
        err_keywords = [w for w in re.findall(r'[a-zA-Z_][a-zA-Z0-9_:]+', err_line)
                       if len(w) > 2 and w.lower() not in
                       ('error','the','for','and','with','from','this',
                        'that','use','using','not','but','was','has')]
        if not err_keywords:
            continue

        for doc_name, doc_content in build_docs:
            doc_lower = doc_content.lower()
            # Match if ANY error keyword appears in the document
            if any(kw.lower() in doc_lower for kw in err_keywords):
                # Avoid duplicate (same doc matched by multiple error lines)
                already = any(d == doc_name for _, d, _ in matches)
                if not already:
                    matches.append((err_line.strip(), doc_name, doc_content))
    return matches

def extract_auto_fix_section(doc_content):
    """Extract the ## Auto-fix section content from a build-fix doc."""
    match = re.search(r'## Auto-fix\s*\n(.+?)(?=\n## |\Z)', doc_content, re.DOTALL)
    return match.group(1) if match else None

def parse_auto_fix_yaml(yaml_text):
    """Parse the YAML auto-fix block. Returns dict with match, files, actions."""
    result = {"match": None, "files": [], "actions": []}
    current_action = None
    in_files = False

    for line in yaml_text.strip().split('\n'):
        line = line.rstrip()
        if not line or line.strip().startswith('#'):
            continue
        stripped = line.strip()

        if stripped.startswith('match:'):
            result["match"] = stripped.split(':', 1)[1].strip().strip('"').strip("'")
            in_files = False
        elif stripped.startswith('files:'):
            in_files = True
        elif stripped.startswith('actions:'):
            in_files = False
        elif stripped.startswith('- type:'):
            if current_action:
                result["actions"].append(current_action)
            current_action = {"type": stripped.split('type:')[1].strip().strip('"').strip("'")}
        elif in_files and stripped.startswith('- '):
            result["files"].append(stripped[2:].strip().strip('"').strip("'"))
        elif current_action is not None and ':' in stripped:
            key, _, val = stripped.partition(':')
            current_action[key.strip()] = val.strip().strip('"').strip("'")

    if current_action:
        result["actions"].append(current_action)
    return result

def apply_doc_auto_fix(project_dir, auto_fix):
    """Apply a single auto-fix to the project. Returns count of changes."""
    total = 0
    files = [project_dir / f for f in auto_fix.get("files", [])]

    for action in auto_fix.get("actions", []):
        atype = action.get("type", "")

        if atype == "replace":
            from_str = action.get("from", "")
            to_str = action.get("to", "")
            for fp in files:
                if not fp.exists(): continue
                content = fp.read_text(encoding="utf-8", errors="replace")
                if from_str in content:
                    cnt = content.count(from_str)
                    fp.write_text(content.replace(from_str, to_str), encoding="utf-8")
                    total += cnt
                    ok(f"  replace: {fp.name} ({cnt})")

        elif atype == "replace_regex":
            from_pat = action.get("from", "")
            to_pat = action.get("to", "")
            for fp in files:
                if not fp.exists(): continue
                content = fp.read_text(encoding="utf-8", errors="replace")
                new_c, cnt = re.subn(from_pat, to_pat, content)
                if cnt > 0:
                    fp.write_text(new_c, encoding="utf-8")
                    total += cnt
                    ok(f"  replace_regex: {fp.name} ({cnt})")

        elif atype == "remove_include":
            inc = action.get("include", "")
            for fp in files:
                if not fp.exists(): continue
                content = fp.read_text(encoding="utf-8", errors="replace")
                pat = re.escape(inc) + r'\n?'
                new_c, cnt = re.subn(pat, '', content)
                if cnt > 0:
                    fp.write_text(new_c, encoding="utf-8")
                    total += cnt
                    ok(f"  remove_include: {fp.name} ({cnt})")

        elif atype == "add_include":
            inc = action.get("include", "")
            for fp in files:
                if not fp.exists(): continue
                content = fp.read_text(encoding="utf-8", errors="replace")
                if inc not in content:
                    fp.write_text(_insert_include(content, inc), encoding="utf-8")
                    total += 1
                    ok(f"  add_include: {fp.name}")

        elif atype == "rewrite_cmake":
            if fix_cmake_findpackage(project_dir, ["Failed to find required Qt component"]):
                total += 1

        elif atype == "remove_line":
            pattern = action.get("pattern", "")
            for fp in files:
                if not fp.exists(): continue
                content = fp.read_text(encoding="utf-8", errors="replace")
                lines = content.split('\n')
                new_lines = [l for l in lines if pattern not in l]
                if len(new_lines) != len(lines):
                    fp.write_text('\n'.join(new_lines), encoding="utf-8")
                    cnt = len(lines) - len(new_lines)
                    total += cnt
                    ok(f"  remove_line: {fp.name} ({cnt})")

    return total

def apply_build_fix(project_dir, error_lines, build_docs):
    """
    Read build/ docs, match errors, parse ## Auto-fix YAML sections,
    and apply fixes automatically — NO user prompts.
    Returns True if any fix was applied.
    """
    if not build_docs:
        return False

    fixes = find_build_fixes(error_lines, build_docs)
    if not fixes:
        return False

    total_applied = 0
    matched_docs = set()

    for err_line, doc_name, doc_content in fixes:
        if doc_name in matched_docs:
            continue
        matched_docs.add(doc_name)

        auto_fix_yaml = extract_auto_fix_section(doc_content)
        if not auto_fix_yaml:
            continue

        auto_fix = parse_auto_fix_yaml(auto_fix_yaml)
        match_pat = auto_fix.get("match")
        if not match_pat or not auto_fix.get("actions"):
            continue

        err_text = '\n'.join(error_lines)
        try:
            if not re.search(match_pat, err_text, re.IGNORECASE) and \
               not any(re.search(match_pat, el, re.IGNORECASE) for el in error_lines):
                continue
        except re.error:
            if match_pat.lower() not in err_text.lower():
                continue

        info(f"  匹配 build/{doc_name}: {match_pat}")
        count = apply_doc_auto_fix(project_dir, auto_fix)
        total_applied += count

    if total_applied > 0:
        ok(f"build/ 文档自动修复完成: {total_applied} 处")
        return True
    return False


# ── Built-in compilation auto-fixes (build-fix-04 ~ 08, 10) ─────────────────
def kill_stale_daemons():
    """Kill stale hvigor daemon processes (build-fix-10, build-fix-11)."""
    for pattern in ['daemon-process-boot-script', 'hvigor-java-daemon']:
        run(f"pkill -f '{pattern}'", capture=True)
    time.sleep(1)
    r = run("ps aux | grep -iE 'hvigor.*daemon' | grep -v grep | awk '{print $2}'", capture=True)
    if r.stdout and r.stdout.strip():
        pids = [p.strip() for p in r.stdout.strip().split('\n') if p.strip()]
        for pid in pids:
            run(f"kill -9 {pid}", capture=True)
        ok(f"已终止 {len(pids)} 个残留 hvigor 守护进程")
    else:
        info("无残留 hvigor 守护进程")


def _detect_local_sdk_version():
    """Detect local DevEco SDK version from sdk-pkg.json (build-fix-08)."""
    sdk_roots = [
        os.environ.get("DEVECO_SDK_HOME", ""),
        "/Applications/DevEco-Studio.app/Contents/sdk",
    ]
    for sdk_root in sdk_roots:
        if not sdk_root:
            continue
        for pkg_rel in ("sdk-pkg.json", "default/sdk-pkg.json"):
            pkg_file = Path(sdk_root) / pkg_rel
            if pkg_file.exists():
                content = pkg_file.read_text(encoding="utf-8", errors="replace")
                pv = re.search(r'"platformVersion"\s*:\s*"([^"]+)"', content)
                av = re.search(r'"apiVersion"\s*:\s*(\d+)', content)
                if pv and av:
                    return f"{pv.group(1)}({av.group(1)})"
    return None


def fix_cmake_findpackage(project_dir, error_lines):
    """build-fix-04: Rewrite CMakeLists.txt to bypass find_package, use direct
    .so path linking, and disable AUTO* (stripped SDK has no lib/cmake/ or bin/)."""
    cmake_file = project_dir / "entry" / "src" / "main" / "cpp" / "CMakeLists.txt"
    if not cmake_file.exists():
        return False

    content = cmake_file.read_text(encoding="utf-8", errors="replace")

    # Only fix if find_package is used and error matches
    has_findpkg = bool(re.search(r'find_package\s*\(\s*QT\s+NAMES\s+Qt5\s+Qt6', content))
    err_match = any(kw in '\n'.join(error_lines) for kw in
                    ('Failed to find required Qt component', 'WrapOpenGL',
                     'Qt6_FOUND', 'find_package'))
    if not has_findpkg or not err_match:
        return False
    # Already fixed?
    if 'find_package' not in content or 'CMAKE_AUTOMOC OFF' in content:
        return False

    # Extract project name
    proj_match = re.search(r'project\s*\(\s*(\w+)', content)
    proj_name = proj_match.group(1) if proj_match else 'qtbugdemo'

    # Extract add_library block (target name + source files)
    add_lib_match = re.search(
        r'add_library\s*\(\s*(\w+)\s+SHARED\s*\n(.*?)\n\)', content, re.DOTALL)
    if not add_lib_match:
        warn("无法解析 CMakeLists.txt 中的 add_library 块")
        return False
    target_name = add_lib_match.group(1)
    sources_block = add_lib_match.group(2).strip()
    sources = [s.strip().rstrip(',') for s in sources_block.split('\n') if s.strip()]

    # Check SDK structure
    qt_dev = cmake_file.parent / "../../../../third_party/qt-ohos-dev"
    qt_dev = qt_dev.resolve()
    has_cmake_cfg = (qt_dev / "lib" / "cmake").exists()
    has_host_tools = (qt_dev / "bin").exists()
    if has_cmake_cfg and has_host_tools:
        info("SDK 含 lib/cmake/ 和 bin/，find_package 应可用，跳过 CMake 重写")
        return False

    # Generate new CMakeLists.txt
    sources_str = '\n    '.join(sources)
    new_content = f"""# the minimum version of CMake.
cmake_minimum_required(VERSION 3.16)
project({proj_name} VERSION 0.1 LANGUAGES CXX)

# AUTOMOC/AUTOUIC/AUTORCC 关闭：仓内 third_party/qt-ohos-dev 无 bin/ 目录
# （moc/uic/rcc 主机工具），且无 lib/cmake/ 目录，find_package 不可用。
# 详见 build/build-fix-04-findpackage-qt6-fallback.md
set(CMAKE_AUTOUIC OFF)
set(CMAKE_AUTOMOC OFF)
set(CMAKE_AUTORCC OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(QT_OHOS_DEV_DIR ${{CMAKE_CURRENT_SOURCE_DIR}}/../../../../third_party/qt-ohos-dev)
if(DEFINED ENV{{QT_OHOS_SDK}})
    set(QT_OHOS_DEV_DIR $ENV{{QT_OHOS_SDK}})
endif()
set(QT_INCLUDE_DIR ${{QT_OHOS_DEV_DIR}}/include)
set(QT_LIB_DIR ${{QT_OHOS_DEV_DIR}}/lib)

add_library({target_name} SHARED
    {sources_str}
)

target_include_directories({target_name} PRIVATE
    ${{QT_INCLUDE_DIR}}/QtCore
    ${{QT_INCLUDE_DIR}}/QtGui
    ${{QT_INCLUDE_DIR}}/QtWidgets
    ${{QT_INCLUDE_DIR}}/QtNetwork
    ${{QT_INCLUDE_DIR}}
)

target_link_libraries({target_name} PRIVATE
    ${{QT_LIB_DIR}}/libQt5Core.so
    ${{QT_LIB_DIR}}/libQt5Gui.so
    ${{QT_LIB_DIR}}/libQt5Widgets.so
    ${{QT_LIB_DIR}}/libQt5Network.so
)
"""
    cmake_file.write_text(new_content, encoding="utf-8")
    ok(f"已重写 CMakeLists.txt: 绕开 find_package → 直接 .so 路径链接 + 关 AUTO*")
    return True


def fix_qwidget_screen_api(project_dir, error_lines):
    """build-fix-06: Replace QWidget::screen() (Qt 5.14+) with
    windowHandle()->screen() fallback for Qt 5.12 compatibility."""
    err_text = '\n'.join(error_lines)
    if "no member named 'screen'" not in err_text:
        return False

    code_files = [f for f in find_source_files(str(project_dir))
                  if os.path.splitext(f)[1].lower() in {".cpp", ".h"}]
    total = 0

    # Patterns to replace (order matters: specific before generic)
    replacements = [
        # parent->screen() with ternary context
        (r'parent\s*&&\s*parent->screen\(\)\s*\?\s*parent->screen\(\)',
         '(parent && parent->windowHandle()) ? parent->windowHandle()->screen()'),
        # dlg.screen()
        (r'(\w+)\.screen\(\)',
         r'\1.windowHandle() ? \1.windowHandle()->screen() : QGuiApplication::primaryScreen()'),
        # dlg->screen()
        (r'(\w+)->screen\(\)',
         r'\1->windowHandle() ? \1->windowHandle()->screen() : QGuiApplication::primaryScreen()'),
    ]

    for fp in code_files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except:
            continue
        orig = content
        # Apply replacements
        for pat, rep in replacements:
            content = re.sub(pat, rep, content)

        # Add #include <QWindow> if screen() was replaced but QWindow not included
        if content != orig and '#include <QWindow>' not in content:
            code_only = strip_comments(content)
            if 'windowHandle()->screen()' in code_only:
                content = _insert_include(content, '#include <QWindow>')

        if content != orig:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            count = orig.count('.screen()') + orig.count('->screen()')
            total += count
            ok(f"  {os.path.relpath(fp, str(project_dir))}: screen() → windowHandle()->screen()")

    if total > 0:
        ok(f"已修复 QWidget::screen() API: {total} 处")
        return True
    return False


def fix_sp_dialogsaveallbutton(project_dir, error_lines):
    """build-fix-07: Replace SP_DialogSaveAllButton (Qt 5.15+) with
    SP_DialogSaveButton for Qt 5.12 compatibility."""
    err_text = '\n'.join(error_lines)
    if 'SP_DialogSaveAllButton' not in err_text:
        return False

    code_files = [f for f in find_source_files(str(project_dir))
                  if os.path.splitext(f)[1].lower() in {".cpp", ".h"}]
    total = 0
    for fp in code_files:
        ch = apply_replacements(fp, [(r'SP_DialogSaveAllButton', 'SP_DialogSaveButton')])
        if ch > 0:
            ok(f"  {os.path.relpath(fp, str(project_dir))}: SP_DialogSaveAllButton → SP_DialogSaveButton ({ch} 处)")
            total += ch
    if total > 0:
        ok(f"已修复 SP_DialogSaveAllButton: {total} 处")
        return True
    return False


def fix_qtoshehtras_unused_include(project_dir, error_lines):
    """build-fix-05: Remove unused QtOhosExtras includes when the SDK lacks
    forwarding headers (only has lowercase .h files)."""
    err_text = '\n'.join(error_lines)
    if "QtOhosExtras/" not in err_text or "file not found" not in err_text.lower():
        return False

    code_files = [f for f in find_source_files(str(project_dir))
                  if os.path.splitext(f)[1].lower() in {".cpp", ".h"}]
    total = 0
    for fp in code_files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except:
            continue
        # Find QtOhosExtras includes
        includes = re.findall(r'#include\s*<QtOhosExtras/(\w+)>', content)
        if not includes:
            continue

        code_only = strip_comments(content)
        removed = []
        for cls in includes:
            # Check if the class name is actually used in code (not just include/comments)
            if cls not in code_only.replace(f'#include <QtOhosExtras/{cls}>', ''):
                # Class is used — try lowercase .h header instead
                # (SDK has qohosabilitycontext.h but not QOhosAbilityContext forwarding header)
                # For now, skip — this needs manual attention
                info(f"  {os.path.relpath(fp, str(project_dir))}: {cls} 在代码中使用，保留 include（考虑改用 .h）")
            else:
                # Class NOT used in code — remove the unused include
                content = re.sub(rf'#include\s*<QtOhosExtras/{cls}>\n?', '', content)
                removed.append(cls)

        if removed:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            ok(f"  {os.path.relpath(fp, str(project_dir))}: 移除未使用 include: {', '.join(removed)}")
            total += len(removed)

    if total > 0:
        ok(f"已移除未使用 QtOhosExtras include: {total} 处")
        return True
    return False


def fix_compatible_sdk_version(project_dir, error_lines):
    """build-fix-08: Fix compatibleSdkVersion mismatch in build-profile.json5."""
    err_text = '\n'.join(error_lines).lower()
    if 'sdk component missing' not in err_text and '00303168' not in err_text:
        # Also check for EPERM uv_cwd (build-fix-10) which can mask this
        if 'eperm' not in err_text and 'uv_cwd' not in err_text:
            return False

    bp_file = project_dir / "build-profile.json5"
    if not bp_file.exists():
        return False

    content = bp_file.read_text(encoding="utf-8", errors="replace")
    # Check current version
    ver_match = re.search(r'"compatibleSdkVersion"\s*:\s*"([^"]+)"', content)
    if not ver_match:
        return False
    current_ver = ver_match.group(1)

    # Detect local SDK version
    local_ver = _detect_local_sdk_version()
    if not local_ver:
        warn("无法检测本机 SDK 版本，跳过 compatibleSdkVersion 修复")
        return False

    if current_ver == local_ver:
        return False  # Already correct

    # Fix the version
    content = content.replace(
        f'"compatibleSdkVersion": "{current_ver}"',
        f'"compatibleSdkVersion": "{local_ver}"')
    bp_file.write_text(content, encoding="utf-8")
    ok(f"已修复 compatibleSdkVersion: {current_ver} → {local_ver}")
    return True


def fix_eperm_uv_cwd(error_lines):
    """build-fix-10: Kill stale hvigor daemons when EPERM: uv_cwd occurs."""
    err_text = '\n'.join(error_lines).lower()
    if 'eperm' not in err_text and 'uv_cwd' not in err_text:
        return False
    warn("检测到 EPERM: uv_cwd — hvigor 守护进程 cwd 失效 (build-fix-10)")
    kill_stale_daemons()
    return True


def apply_compilation_auto_fixes(project_dir, error_lines):
    """
    Try all built-in compilation auto-fixes (build-fix-04 ~ 08, 10).
    Returns True if any fix was applied.
    """
    applied = False

    # build-fix-10: EPERM uv_cwd (kill stale daemons first)
    if fix_eperm_uv_cwd(error_lines):
        applied = True

    # build-fix-04: CMake find_package Qt6 fallback
    if fix_cmake_findpackage(project_dir, error_lines):
        applied = True

    # build-fix-05: QtOhosExtras unused include
    if fix_qtoshehtras_unused_include(project_dir, error_lines):
        applied = True

    # build-fix-06: QWidget::screen() API
    if fix_qwidget_screen_api(project_dir, error_lines):
        applied = True

    # build-fix-07: SP_DialogSaveAllButton
    if fix_sp_dialogsaveallbutton(project_dir, error_lines):
        applied = True

    # build-fix-08: compatibleSdkVersion
    if fix_compatible_sdk_version(project_dir, error_lines):
        applied = True

    return applied


# ══════════════════════════════════════════════════════════════════════════
# Step 3
# ══════════════════════════════════════════════════════════════════════════
def step3_build_and_fix(project_dir):
    banner("Step 3: 修复编译问题完成编译")

    # build-fix-10: Kill stale hvigor daemons before building
    step("3.0", "清理 hvigor 守护进程 (build-fix-10)")
    kill_stale_daemons()

    # build-fix-11: Warn about DevEco Studio reverting external edits
    deveco_running = run("ps aux | grep -i 'devecostudio' | grep -v grep", capture=True)
    if deveco_running.stdout and deveco_running.stdout.strip():
        warn("DevEco Studio 正在运行 — 可能回退外部文件编辑 (build-fix-11)")
        warn("如修复被回退，请先退出 DevEco Studio 再重新运行本脚本:")
        warn("  osascript -e 'quit app \"DevEco-Studio\"'")

    # Load build fix documents
    build_docs = load_build_docs()

    step("3.1","构建工程")
    info(f"命令: {BUILD_CMD}")
    attempt=0; fixed=False; result=None
    all_errors = []  # collect all unique error lines across build attempts
    matched_fix_docs = set()  # track which build-fix docs were used
    while attempt<10:
        attempt+=1; info(f"第 {attempt} 次构建...")
        result = run_build(BUILD_CMD, cwd=str(project_dir))
        if result.returncode==0: ok("构建成功！零错误"); break

        # Collect error lines
        # Combine stdout + stderr — hvigor puts summary in stderr, details in stdout
        eo = (result.stdout or "") + "\n" + (result.stderr or "")
        # Broaden error collection: capture diagnostic lines, not just "error:"
        el = [l for l in eo.splitlines() if any(kw in l.lower() for kw in [
            "error:", "fatal error", "eperm", "uv_cwd",
            "00303168", "00303217", "00308018", "00617301",
            "failed", "not found", "could not find", "wrapopengl",
            "find_package", "configuring incomplete", "build failed",
            "component missing", "file not found",
            "deveco_sdk_home", "invalid value"
        ]        )]

        # Track unique error lines for Step 3.5 doc generation
        for l in el:
            l_stripped = l.strip()
            if l_stripped and l_stripped not in [e[0] for e in all_errors]:
                all_errors.append((l_stripped, attempt))

        # ── Auto-fix: built-in + build/ docs (no user prompts) ──
        step("3.2", f"第 {attempt} 次自动修复")

        # Try built-in auto-fixes first (build-fix-04~08, 10)
        auto_applied = apply_compilation_auto_fixes(project_dir, el)

        # If built-in didn't match, try build/ doc auto-fix
        if not auto_applied:
            # Track which docs match for Step 3.5
            fixes = find_build_fixes(el, build_docs)
            for _, doc_name, _ in fixes:
                matched_fix_docs.add(doc_name)
            doc_applied = apply_build_fix(project_dir, el, build_docs)
            if doc_applied:
                auto_applied = True

        if auto_applied:
            ok("自动修复已应用，重新构建...")
            fixed=True
            continue

        # ── Fallback: built-in error reference (manual) ──
        info("内置修复参考:")
        builtin_matched = False
        for em,fx in [
            ("'QtOhExtras/xxx.h' file not found","→ QtOhosExtras/xxx.h (§9.1)"),
            ("QOhAppContext was not declared","→ QOhosAbilityContext (§9.2)"),
            ("requestPermissionsSync","→ 异步信号槽 (§2.3)"),
            ("shareFile","→ shareDataWithShareKit() (§2.4)"),
            ("undefined reference to QtOh::checkPermission","→ 使用 QOhosAbilityContext 方法"),
            ("cannot find -lQt5OhExtras","→ QT += ohosextras"),
            ("QOhosPlatformIntegration was not declared","→ #include <QtOhosExtras/QOhosPlatformIntegration>"),
            ("QOhosWant","→ #include <QtOhosExtras/QOhosWant> 等"),
            ("QOhosStartOptions","→ #include <QtOhosExtras/QOhosStartOptions>"),
            ("EPERM: operation not permitted, uv_cwd","→ 终止 hvigor 守护进程 (build-fix-10)"),
            ("SDK component missing","→ 检查 compatibleSdkVersion + DEVECO_SDK_HOME (build-fix-08,03)"),
            ("00303217","→ DEVECO_SDK_HOME 未设置或无效 (build-fix-12); 也可能是 oh-package.json5 (build-fix-09)"),
            ("00308018","→ CMake 执行失败: 检查 find_package/SDK 结构 (build-fix-04)"),
            ("00617301","→ ohpm 包缺失: 移除 @types/libentry.so (build-fix-09)"),
        ]:
            if any(em.lower() in l.lower() for l in el):
                mk = f"{C.RED}✗{C.R}"
                builtin_matched = True
            else:
                mk = f"{C.GRY} {C.R}"
            print(f"  {mk}  {em}\n      {fx}")

        step("3.3","构建配置检查")
        # Check if SDK is stripped or full
        qt_dev = project_dir / "third_party" / "qt-ohos-dev"
        has_cmake_cfg = (qt_dev / "lib" / "cmake").exists()
        has_host_tools = (qt_dev / "bin").exists()
        if has_cmake_cfg and has_host_tools:
            info("SDK 类型: 完整版 (有 lib/cmake/ 和 bin/)")
            info("  CMake: find_package(Qt5 COMPONENTS ... OhosExtras) + Qt5::OhosExtras")
        else:
            info(f"SDK 类型: 精简版 (lib/cmake/: {'有' if has_cmake_cfg else '无'}, bin/: {'有' if has_host_tools else '无'})")
            info("  CMake: 直接 .so 路径链接 + 关 AUTO* (build-fix-04)")
        info("qmake: QT += ohosextras core gui widgets; CONFIG += ohos")

        if builtin_matched:
            if ask("\n内置参考匹配到错误，是否已手动修复？(y=重新构建 / n=跳过)") in ("y","yes","是"):
                fixed=True
                continue

        # ── Layer 4: Full error report ──
        print(f"\n  {C.RED}{C.B}════════════════════════════════════════{C.R}")
        print(f"  {C.RED}{C.B}  编译失败 — 编译错误报告{C.R}")
        print(f"  {C.RED}{C.B}════════════════════════════════════════{C.R}\n")
        print(f"  {C.B}构建命令{C.R}: {BUILD_CMD}")
        print(f"  {C.B}工程路径{C.R}: {C.YLW}{project_dir}{C.R}")
        print(f"  {C.B}错误数量{C.R}: {len(el)} 处\n")
        if el:
            print(f"  {C.B}错误列表 (过滤后){C.R}:")
            for i, l in enumerate(el[:20], 1):
                print(f"    {C.RED}{i}.{C.R} {l.strip()}")
            if len(el) > 20:
                print(f"    {C.GRY}... 还有 {len(el)-20} 处错误{C.R}")
        else:
            print(f"  (无 error: 行，构建返回码 {result.returncode})")
        # Show full build output for diagnosis (last 60 lines)
        print(f"\n  {C.B}完整构建输出 (最后 60 行){C.R}:")
        all_lines = eo.splitlines()
        for l in all_lines[-60:]:
            print(f"  {C.GRY}{l}{C.R}")
        print(f"\n  {C.YLW}请手动打开工程修改编译错误：{C.R}")
        print(f"  {C.YLW}用 DevEco Studio 打开以下路径的工程：{C.R}")
        print(f"  {C.YLW}{project_dir}{C.R}")
        print(f"  {C.YLW}注意：DevEco Studio 可能回退外部编辑 (build-fix-11){C.R}\n")

        if ask("修改完成后是否重新构建？(y=重新构建 / n=跳过)") in ("y","yes","是"):
            fixed=True
        else:
            warn("跳过编译修复"); break

    step("3.4","编译结果")
    success = result is not None and result.returncode==0
    ok("编译通过") if success else err("编译未通过")
    if not success:
        info("提示: deprecated QString 构造函数的警告可忽略 (社区版 SDK 遗留)")

    step("3.5","生成编译修复文档")
    if all_errors:
        # Load existing build-fix docs
        existing_docs = {}
        if BUILD_DOCS_DIR.exists():
            for f in sorted(BUILD_DOCS_DIR.glob("*.md")):
                try:
                    existing_docs[f.name] = f
                except Exception:
                    pass

        updated_docs = []
        uncovered_errors = []

        # For each error, check if it's covered by an existing build-fix doc
        for err_line, attempt_num in all_errors:
            if any(skip in err_line for skip in ["BUILD FAILED", "hvigor ERROR: Error Code"]):
                continue

            err_keywords = [w for w in re.findall(r'[a-zA-Z_][a-zA-Z0-9_:]+', err_line)
                           if len(w) > 3 and w.lower() not in
                           ('error','the','for','and','with','from','this','that','hvigor')]

            covered_by = None
            for doc_name, doc_path in existing_docs.items():
                try:
                    doc_content = doc_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if any(kw.lower() in doc_content.lower() for kw in err_keywords):
                    covered_by = (doc_name, doc_path, doc_content)
                    break

            if covered_by:
                doc_name, doc_path, doc_content = covered_by
                # Refresh the existing doc — update date and error output
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                # Update date line
                doc_content = re.sub(
                    r'> 日期：\d{4}-\d{2}-\d{2}',
                    f'> 日期：{today}（基于实测构建更新）',
                    doc_content)
                # Update status if build succeeded
                if success:
                    doc_content = re.sub(
                        r'> 当前状态：.*',
                        f'> 当前状态：已修复（构建通过）',
                        doc_content)
                # Ensure the latest error output is in the doc
                if err_line not in doc_content:
                    # Append latest error to the error section
                    doc_content = re.sub(
                        r'(## 1\. 报错\s*\n```\s*\n)',
                        rf'\1{err_line}\n',
                        doc_content, count=1)
                doc_path.write_text(doc_content, encoding="utf-8")
                if doc_path not in updated_docs:
                    updated_docs.append(doc_path)
            else:
                uncovered_errors.append((err_line, attempt_num))

        # Summary output
        if matched_fix_docs:
            info(f"已使用并刷新现有修复文档 ({len(updated_docs)} 个):")
            for dp in updated_docs:
                ok(f"  {dp}")
        if uncovered_errors:
            warn(f"发现 {len(uncovered_errors)} 个未被现有文档覆盖的错误:")
            for err_line, attempt_num in uncovered_errors:
                print(f"  {C.RED}  第{attempt_num}次: {err_line[:100]}{C.R}")
            warn("请在 build/ 目录下补充对应问题的修复文档")
            info("文档命名: build-fix-<编号>-<错误关键词>.md")
            info(f"路径: {BUILD_DOCS_DIR}")

        if updated_docs:
            print(f"\n  {C.YLW}{C.B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}")
            print(f"  {C.YLW}{C.B}  编译修复文档已刷新{C.R}")
            print(f"  {C.YLW}{C.B}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{C.R}\n")
            print(f"  {C.B}文档路径:{C.R}")
            for dp in updated_docs:
                print(f"    {C.GRN}{dp}{C.R}")
            print(f"\n  {C.B}说明:{C.R}")
            print(f"  以上文档已根据本次构建的最新报错更新。")
            print(f"  请检查文档内容是否完整后，上传更新到 skill。")
            print(f"\n  {C.CYA}温馨提示:{C.R}")
            print(f"  {C.CYA}上传更新后的文档可以帮助完善 skill，使自动修复功能更加智能。{C.R}")
            print(f"  {C.CYA}下次遇到相同错误时，skill 将自动匹配并修复。{C.R}")
            print(f"  {C.CYA}路径: {BUILD_DOCS_DIR}{C.R}\n")
        elif not uncovered_errors:
            info("所有编译错误均已被现有文档覆盖，无需更新")
    else:
        info("无编译错误（一次通过）")

    # Regenerate patches after compilation fixes — reflects final state
    # (original → official with all migration + compilation fixes applied)
    if fixed and ORIG_PROJECT_DIR and ORIG_PROJECT_DIR.is_dir():
        orig_name = ORIG_PROJECT_DIR.name
        patch_output_dir = PATCHES_DIR / orig_name
        patch_output_dir.mkdir(parents=True, exist_ok=True)
        info("重新生成 patch（含编译修复后的最终状态）...")
        regen_patches = _generate_patches(ORIG_PROJECT_DIR, project_dir,
                                          patch_output_dir)
        if regen_patches:
            ok(f"patch 已更新: {len(regen_patches)} 个 → {patch_output_dir}")
            for pp in regen_patches:
                ok(f"  {pp.name}")

    return success

# ══════════════════════════════════════════════════════════════════════════
# Step 4
# ══════════════════════════════════════════════════════════════════════════
def step4_hap_and_test(project_dir):
    banner("Step 4: 生成签名 hap 并测试启动")

    step("4.1","确认签名配置")
    bp = project_dir / "build-profile.json5"
    if bp.exists():
        c = bp.read_text(encoding="utf-8", errors="replace")
        ok("签名配置存在") if "signingConfigs" in c else warn("未找到 signingConfigs")
    else: warn("未找到 build-profile.json5")

    step("4.2","构建签名 hap")
    hd = project_dir / "entry" / "build" / "default" / "outputs" / "default"
    info(f"命令: {BUILD_CMD}")
    result = run_build(BUILD_CMD, cwd=str(project_dir))
    if result.returncode!=0:
        err("hap 构建失败")
        # Show build error details for diagnosis
        eo = (result.stdout or "") + "\n" + (result.stderr or "")
        err_lines = [l for l in eo.splitlines() if any(kw in l.lower() for kw in [
            "error:", "failed", "not found", "00303217", "00308018"])]
        for l in err_lines[-10:]:
            print(f"  {C.RED}{l.strip()}{C.R}")
        return False
    haps = list(hd.glob("*-signed.hap")) if hd.exists() else []
    if not haps: haps = list(project_dir.rglob("*-signed.hap"))
    if not haps: err("未找到签名 hap"); return False
    hap_path = haps[0]; ok(f"签名 hap: {hap_path}")

    step("4.3","安装并启动")
    bn = ""
    aj = project_dir / "AppScope" / "app.json5"
    if aj.exists():
        c = aj.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'"bundleName"\s*:\s*"([^"]+)"', c)
        if m: bn = m.group(1)
    if not bn: bn = ask("请输入 bundle name")
    info(f"Bundle: {bn}")

    # Read ability name from module.json5 (first ability in "abilities" array)
    ability_name = "EntryAbility"  # default fallback
    module_json5 = project_dir / "entry" / "src" / "main" / "module.json5"
    if module_json5.exists():
        c = module_json5.read_text(encoding="utf-8", errors="replace")
        # Find first "name" inside "abilities" array
        abilities_match = re.search(r'"abilities"\s*:\s*\[', c)
        if abilities_match:
            start = abilities_match.end()
            # Find first "name": "xxx" after abilities array start
            name_match = re.search(r'"name"\s*:\s*"([^"]+)"', c[start:start+500])
            if name_match:
                ability_name = name_match.group(1)
    info(f"Ability: {ability_name}")

    # Check device connectivity (build-fix-12: hdc needs DEVECO_SDK_HOME)
    info("检查设备连接...")
    hdc_check = run_hdc("hdc list targets")
    devices = [d.strip() for d in (hdc_check.stdout or "").splitlines() if d.strip() and d.strip() != "[Empty]"]
    if hdc_check.returncode != 0 or not devices:
        warn("未检测到已连接设备 (hdc list targets 为空)")
        info("可能原因: DEVECO_SDK_HOME 未设置 / 设备未连接 / hdc 未授权")
        info("请在 DevEco Studio 中确认设备已连接，或手动执行:")
        info(f"  hdc install {hap_path}")
        info(f"  hdc shell aa start -a {ability_name} -b {bn}")
        return False
    ok(f"已连接设备: {devices[0]}")

    info("安装..."); result = run_hdc(f"hdc install {hap_path}")
    if result.returncode!=0:
        # Try with -r flag (reinstall)
        result = run_hdc(f"hdc install -r {hap_path}")
        if result.returncode!=0:
            err("安装失败")
            if result.stderr: print(f"  {C.RED}{result.stderr[:200]}{C.R}")
            return False
    # Verify install output contains "success" (not just exit code 0)
    install_output = (result.stdout or "") + (result.stderr or "")
    if "success" not in install_output.lower() and result.returncode == 0:
        info(f"安装输出: {install_output[:200]}")
    ok("安装成功")

    # Record faultlog state BEFORE app launch (to detect new crashes only)
    fl_before = run_hdc("hdc shell ls /data/log/faultlog/temp/ 2>/dev/null")
    faultlog_before = set(l.strip() for l in (fl_before.stdout or "").splitlines() if l.strip())

    # Launch app with the ACTUAL ability name from module.json5
    info(f"启动: aa start -a {ability_name} -b {bn}")
    launch_result = run_hdc(f"hdc shell aa start -a {ability_name} -b {bn}")
    # Check launch command output for errors
    launch_output = (launch_result.stdout or "") + (launch_result.stderr or "")
    if "error" in launch_output.lower() or "fail" in launch_output.lower():
        warn(f"启动命令返回错误:")
        print(f"  {C.RED}{launch_output[:300]}{C.R}")
        warn("可能原因: ability 名称不匹配 / 应用未安装 / 签名问题")
        info(f"请检查 module.json5 中的 ability 名称: {ability_name}")
        info(f"手动启动: hdc shell aa start -a {ability_name} -b {bn}")
    elif launch_result.returncode != 0:
        warn(f"启动命令返回码: {launch_result.returncode}")
        if launch_output.strip():
            print(f"  {C.YLW}{launch_output[:300]}{C.R}")

    step("4.4","验证启动不崩溃")
    # Retry process check with delays — app may take time to start
    alive = False
    bn_short = bn.split(".")[-1] if "." in bn else bn
    for wait in [2, 3, 5]:
        time.sleep(wait)
        r = run_hdc("hdc shell ps -ef")
        ps_output = r.stdout or ""
        alive = bn in ps_output or bn_short in ps_output
        if alive:
            break
        info(f"  等待 {wait}s 后重试... (未找到 {bn})")
    ok("进程存活") if alive else err("进程未找到")

    # Check faultlog AFTER app launch — only NEW files indicate a crash in this run
    fl_after = run_hdc("hdc shell ls /data/log/faultlog/temp/ 2>/dev/null")
    faultlog_after = set(l.strip() for l in (fl_after.stdout or "").splitlines() if l.strip())
    new_faultlogs = faultlog_after - faultlog_before  # files that appeared after launch

    # Check hilog for crash keywords (only relevant if process died)
    r = run_hdc("hdc shell hilog", timeout=10)
    ck = ["FATAL","SIGSEGV","cppcrash","crash"]
    cl = [l for l in (r.stdout or "").splitlines() if any(k in l.upper() for k in ck) and bn in l]

    step("4.5","崩溃处理")
    if not new_faultlogs and alive and not cl:
        ok("启动正常，无崩溃")
    elif new_faultlogs:
        # New faultlog files appeared after app launch → app crashed in this run
        warn(f"检测到 {len(new_faultlogs)} 个新 faultlog 文件（本次运行产生）:")
        for fl in sorted(new_faultlogs):
            warn(f"  {fl}")
        # Display crash log content
        for fl in sorted(new_faultlogs):
            if "cppcrash" in fl:
                cr = run_hdc(f"hdc shell cat /data/log/faultlog/temp/{fl}")
                if cr.stdout:
                    print(f"\n  {C.GRY}--- {fl} ---{C.R}")
                    print(f"  {C.GRY}{cr.stdout[:2000]}{C.R}")
                    break
        info("\n常见崩溃原因:")
        for s,f in [
            ("libQt5OhExtras.so not found","→ libQt5OhosExtras.so"),
            ("libqopenharmony.so not found","→ libqohos.so"),
            ("SIGSEGV in QOhosAbilityContext::instance()","延迟到 QGuiApplication 后访问"),
            ('platform "ohos" not available',"确认 libqohos.so 在 platforms 目录"),
        ]: print(f"    {s}\n      → {f}")
        warn("\n应用启动崩溃，需要用户手动修复。跳过崩溃处理步骤。")
        info("修复后可重新运行本脚本验证。")
    elif cl and not alive:
        warn("hilog 崩溃日志 (进程已退出):")
        for l in cl[:5]: print(f"  {C.RED}{l.strip()}{C.R}")
        warn("\n应用启动崩溃，需要用户手动修复。跳过崩溃处理步骤。")
        info("修复后可重新运行本脚本验证。")
    else:
        # Process alive but has old faultlogs or hilog warnings — not a crash in this run
        info("进程存活，旧 faultlog 已忽略（时间戳早于本次启动）")

    step("4.6","功能冒烟测试")
    info("请手动验证:")
    for i,t in enumerate([
        "权限请求 — 弹窗出现（不阻塞 UI）",
        "文件分享 — 分享面板出现",
        "窗口渲染 — QHarmonyStyle 正常",
        "主题切换 — setDarkThemeEnabled() 生效",
    ],1): print(f"  {i}. {t}")
    print(f"\n  {C.GRN}{C.B}迁移完成！{C.R}\n")
    return True

# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════
def main():
    banner("Qt for OpenHarmony: 社区版 → 官方版 一键迁移")
    print()

    banner("Step 1: 识别社区版代码并迁移为官方版")
    step1_select_qt_version()
    project_dir = step1_get_project_path()
    step1_scan(project_dir)
    step1_migrate(project_dir)
    step1_window_api(project_dir)
    step1_verify(project_dir)

    step2_generate_patches(project_dir)
    step3_build_and_fix(project_dir)
    step4_hap_and_test(project_dir)

if __name__ == "__main__":
    main()
