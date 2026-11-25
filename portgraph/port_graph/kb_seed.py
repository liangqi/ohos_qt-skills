"""Seed data: Qt module HarmonyOS support matrix + platform interface whitelist + cross-source name alignment.

- Qt modules: the three tables of data/qt-harmonyos-modules.md (vendored knowledge page) are parsed at runtime
- Platform interface whitelist: hand-curated
- Name alignment: scan hint names -> harmonybrew/cmd-pkgs package nodes
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import DATA_DIR, db

MODULES_PAGE = DATA_DIR / "qt-harmonyos-modules.md"
QT_CLUSTER_ID = "cluster:qt"

# ------------------------------------------------------------- interface whitelist

# (id, name, category, ohos_status, note)
INTERFACE_SEEDS: List[Tuple[str, str, str, str, str]] = [
    ("iface:posix", "POSIX/musl C library", "os-api", "supported",
     "The OpenHarmony NDK uses musl libc; broad coverage of basic POSIX interfaces"),
    ("iface:bsd-socket", "BSD socket / TCP-IP", "network", "supported",
     "The HarmonyOS network stack supports the standard BSD socket API"),
    ("iface:opengl-es", "OpenGL ES / EGL", "graphics", "supported",
     "The HarmonyOS graphics stack provides EGL/GLES; desktop OpenGL must be downgraded to GLES"),
    ("iface:pthread", "pthread multithreading", "os-api", "supported",
     "musl provides pthread"),
    ("iface:dylib", "dlopen dynamic loading", "os-api", "convertible",
     "HarmonyOS supports dlopen, but library paths/packaging are restricted; adapt to the native directory inside the HAP"),
    ("iface:macos-system", "macOS system library binding", "os-api", "convertible",
     "The formula depends on libraries bundled with macOS; on HarmonyOS they must become explicitly packaged dependencies"),
    ("iface:glib-event", "glib event loop", "os-api", "convertible",
     "Replace with the Qt event loop, or port the glib main loop"),
    ("iface:gnutls-api", "GnuTLS/GSS-API system binding", "crypto", "convertible",
     "Can be changed to an explicit dependency on an open-source implementation package"),
    ("iface:x11", "Direct X11/Xlib", "display", "unsupported",
     "HarmonyOS has no X11 display server; Qt apps should go through QPA, code using X11 directly is not portable"),
    ("iface:wayland", "Direct Wayland", "display", "unsupported",
     "The HarmonyOS window model is not the Wayland protocol; code using it directly is not portable"),
    ("iface:dbus", "D-Bus IPC", "ipc", "unsupported",
     "HarmonyOS has no D-Bus (the Qt D-Bus module is out of scope); switch to system services/IPC"),
    ("iface:alsa", "Direct ALSA", "audio", "unsupported",
     "HarmonyOS audio goes through AudioRenderer/AudioCapturer; ALSA is unavailable"),
    ("iface:pulseaudio", "Direct PulseAudio", "audio", "unsupported",
     "HarmonyOS has no PulseAudio service"),
    ("iface:coreaudio", "macOS CoreAudio", "audio", "unsupported",
     "macOS-only audio framework"),
    ("iface:win32", "Win32 API", "os-api", "unsupported",
     "Windows-only system interface"),
    ("iface:cocoa", "macOS Cocoa/AppKit", "os-api", "unsupported",
     "macOS-only UI/system framework"),
    ("iface:systemd", "systemd", "os-api", "unsupported",
     "HarmonyOS has no systemd service management"),
    ("iface:fork-exec", "fork()/exec() process model", "os-api", "unknown",
     "musl provides fork, but the HarmonyOS app sandbox restricts child processes; evaluate per scenario"),
    ("iface:gpu-desktop-gl", "Desktop OpenGL (3.x+/compatibility context)", "graphics", "convertible",
     "Must be converted to OpenGL ES or go through Qt RHI/ANGLE-style solutions"),
    # ---- HarmonyOS native interfaces (as alternatives to unsupported interfaces) ----
    ("iface:ohos-audio", "HarmonyOS AudioRenderer/AudioCapturer", "audio", "supported",
     "HarmonyOS native audio API, replacing ALSA/PulseAudio/CoreAudio"),
    ("iface:ohos-window", "HarmonyOS WindowStage/XComponent", "display", "supported",
     "HarmonyOS window model, replacing direct X11/Wayland"),
    ("iface:ohos-ipc", "HarmonyOS IPC/system service capabilities", "ipc", "supported",
     "HarmonyOS native IPC mechanism, replacing D-Bus"),
]

# ------------------------------------------------------------- KF component deps
# KDE Frameworks component -> {qt: Qt modules, kf: other KF components it depends on, ifaces: platform interfaces}
# Used to analyze KF components recursively as subprojects instead of marking them blocked wholesale.
KF_DEPS: Dict[str, Dict] = {
    "coreaddons": {"qt": ["core"], "kf": [], "ifaces": []},
    "i18n": {"qt": ["core", "gui"], "kf": ["coreaddons"], "ifaces": []},
    "config": {"qt": ["core"], "kf": ["coreaddons"], "ifaces": []},
    "configwidgets": {"qt": ["core", "gui", "widgets"],
                      "kf": ["config", "coreaddons", "i18n", "widgetsaddons",
                             "guiaddons"], "ifaces": []},
    "guiaddons": {"qt": ["core", "gui"], "kf": [], "ifaces": []},
    "widgetsaddons": {"qt": ["core", "gui", "widgets"],
                      "kf": ["coreaddons"], "ifaces": []},
    "itemviews": {"qt": ["core", "gui", "widgets"], "kf": [], "ifaces": []},
    "textwidgets": {"qt": ["core", "gui", "widgets"],
                    "kf": ["iconthemes"], "ifaces": []},
    "iconthemes": {"qt": ["core", "gui"], "kf": ["guiaddons"], "ifaces": []},
    "xmlgui": {"qt": ["core", "gui", "widgets"],
               "kf": ["config", "coreaddons", "i18n", "iconthemes",
                      "widgetsaddons", "itemviews", "textwidgets"],
               "ifaces": []},
    "completion": {"qt": ["core", "gui", "widgets"],
                   "kf": ["config", "coreaddons", "i18n", "widgetsaddons"],
                   "ifaces": []},
    "archive": {"qt": ["core"], "kf": [], "ifaces": []},
    "crash": {"qt": ["core"], "kf": ["coreaddons"], "ifaces": []},
    "jobwidgets": {"qt": ["core", "gui", "widgets"],
                   "kf": ["coreaddons"], "ifaces": []},
    "kio": {"qt": ["core", "gui", "widgets", "network"],
            "kf": ["coreaddons", "config", "i18n", "jobwidgets",
                   "widgetsaddons"], "ifaces": ["iface:dbus"]},
    "colorscheme": {"qt": ["core", "gui"], "kf": ["guiaddons", "config"],
                    "ifaces": []},
    "windowsystem": {"qt": ["core", "gui"], "kf": [],
                     "ifaces": ["iface:x11", "iface:win32"]},
    "dbusaddons": {"qt": ["core", "dbus"], "kf": [], "ifaces": ["iface:dbus"]},
    "dnssd": {"qt": ["core", "network"], "kf": [], "ifaces": ["iface:dbus"]},
    "notifications": {"qt": ["core", "gui", "widgets"],
                      "kf": ["config", "coreaddons", "i18n", "widgetsaddons"],
                      "ifaces": ["iface:dbus"]},
    "notifyconfig": {"qt": ["core", "gui", "widgets"],
                     "kf": ["notifications", "config"], "ifaces": []},
    "bookmarks": {"qt": ["core"], "kf": ["kio", "coreaddons"], "ifaces": []},
    "kcmutils": {"qt": ["core", "gui", "widgets"],
                 "kf": ["coreaddons", "i18n", "config", "service"],
                 "ifaces": []},
    "service": {"qt": ["core"], "kf": ["coreaddons", "config"], "ifaces": []},
    "doctools": {"qt": ["core"], "kf": [], "ifaces": []},
    "statusnotifieritem": {"qt": ["core", "gui", "dbus"], "kf": [],
                           "ifaces": ["iface:dbus"]},
    "screen": {"qt": ["core", "gui"], "kf": ["windowsystem"],
               "ifaces": ["iface:x11"]},
}

# ------------------------------------------------------------- Qt modules

_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|(.*)$")


def normalize_module(name: str) -> str:
    """'Qt Quick Controls' -> 'quickcontrols'; 'Qt WebEngine (all submodules)' -> 'webengine'."""
    n = re.sub(r"[（(].*?[)）]", "", name.strip())
    if n.lower().startswith("qt "):
        n = n[3:]
    elif n.lower().startswith("qt") and len(n) > 2 and n[2].isupper():
        n = n[2:]
    return re.sub(r"[\s\-_]+", "", n).lower()


def _parse_module_tables(text: str) -> List[Dict]:
    """Parse the three kinds of module tables in the knowledge page.

    Accepts the English page headings ("Add-Ons — Completed", "Add-Ons — Out of scope")
    as well as the original Chinese ones (已完成 / 不在范围内)."""
    modules: List[Dict] = []
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            if "Essentials" in s:
                section = "essentials"
            elif "out of scope" in s.lower() or "不在范围内" in s:
                section = "oos"
            elif "已完成" in s or "Add-Ons" in s:
                section = "addons"
            else:
                section = None
            continue
        if section is None or not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= {"-", ":", " "}:
            continue
        # header rows (English page, plus the original Chinese headers)
        if cells[0] in ("Module", "I want to check...", "模块", "我想确认..."):
            continue
        name = cells[0]
        if section == "oos":
            modules.append({"name": name, "status": "blocked",
                            "note": cells[1] if len(cells) > 1 else ""})
        else:
            c512 = cells[1] if len(cells) > 1 else ""
            c515 = cells[2] if len(cells) > 2 else ""
            note = cells[3] if len(cells) > 3 else ""
            ok512, ok515 = "✅" in c512, "✅" in c515
            if ok512 and ok515:
                status = "ported"
            elif ok512 or ok515:
                status = "ported"
                note = ("Partial support: " + ("5.12 only" if ok512 else "5.15 only")
                        + ("; " + note if note else ""))
            else:
                status = "blocked"
            modules.append({"name": name, "status": status, "note": note})
    return modules


def seed_qt_modules(conn) -> List[Dict]:
    text = MODULES_PAGE.read_text(encoding="utf-8")
    modules = _parse_module_tables(text)
    db.upsert_cluster(conn, QT_CLUSTER_ID, "Qt", "framework")
    for m in modules:
        key = normalize_module(m["name"])
        evidence = ("Qt for HarmonyOS module support table: " +
                    ("unsupported - " + m["note"] if m["status"] == "blocked"
                     else "completed" + (" (" + m["note"] + ")" if m["note"] else "")))
        db.upsert_node(conn, "qtmod:%s" % key, "qt-module", m["name"],
                       "kb-seed", m["status"], port_evidence=evidence,
                       cluster_id=QT_CLUSTER_ID)
    return modules


def seed_interfaces(conn) -> None:
    for seed in INTERFACE_SEEDS:
        db.upsert_interface(conn, *seed)


# ------------------------------------------------------------- name alignment

# scan hint name -> candidate package names (in priority order)
ALIASES: Dict[str, List[str]] = {
    "openssl": ["openssl@3", "openssl"],
    "libjpeg": ["jpeg-turbo", "libjpeg-turbo"],
    "liblzma": ["xz", "lzma", "liblzma"],
    "lzma": ["xz", "lzma", "liblzma"],
    "icu": ["icu4c", "icu"],
    "libuuid": ["util-linux", "libuuid", "uuid"],
    "freetype": ["freetype"],
    "harfbuzz": ["harfbuzz"],
    "ffmpeg": ["ffmpeg"],
    "sqlite": ["sqlite"],
    "zlib": ["zlib"],
    "libpng": ["libpng"],
    "curl": ["curl"],
    "boost": ["boost"],
    "protobuf": ["protobuf"],
    "spdlog": ["spdlog"],
    "glm": ["glm"],
    # CMake module name/dependency-list name -> hb package name (reviewed in e2e corpus_b; also used by
    # the e2e names_match reconciliation: oracle name alsa <-> resolved node name alsa-lib)
    "alsa": ["alsa-lib", "alsa"],
    "sndfile": ["libsndfile", "sndfile"],
    "ogg": ["libogg", "ogg"],
    "vorbis": ["libvorbis", "vorbis"],
    "tinyxml": ["tinyxml2", "tinyxml"],
    "glib2": ["glib", "glib2"],
    "dbus1": ["dbus", "dbus1"],
    "png": ["libpng", "png"],
    "nlohmann_json": ["nlohmann-json", "nlohmann_json"],
    "opencv": ["opencv"],
    # graph-side candidates aligned with PKG_ALIASES (hb formula naming; order = priority)
    "ada": ["ada-url"],
    "libudev": ["udev", "systemd"],
    "udev": ["udev", "systemd"],
    "pango": ["pango"],
    "pangocairo": ["pango"],
    "pangoft2": ["pango"],
    "pangomm-1.4": ["pangomm"],
    "pangomm-2.48": ["pangomm"],
    "glibmm-2.4": ["glibmm"],
    "glibmm-2.68": ["glibmm"],
    "giomm-2.4": ["glibmm"],
    "giomm-2.68": ["glibmm"],
    "sigc++-2.0": ["libsigc++"],
    "sigc++-3.0": ["libsigc++"],
    "range-v3": ["range-v3"],
}


# Library name/pkg-config name -> HarmonyOS package name alignment (hb package naming).
# deps_report uses it to merge double declarations of the same library; project_scanner uses it for
# scan-time resolution (eliminating ghost nodes like libavcodec->ffmpeg); both share this one table.
PKG_ALIASES: Dict[str, str] = {
    "swscale": "ffmpeg", "avcodec": "ffmpeg", "avformat": "ffmpeg",
    "avutil": "ffmpeg", "swresample": "ffmpeg", "postproc": "ffmpeg",
    "libswscale": "ffmpeg", "libavcodec": "ffmpeg", "libavformat": "ffmpeg",
    "libavutil": "ffmpeg", "libavdevice": "ffmpeg",
    # the xz toolchain provides liblzma (find_package(LibLZMA) is the official CMake module name;
    # observed in the corpus_a cmake/external/auto_updates/xz wrapper)
    "liblzma": "xz",
    "ssl": "openssl", "crypto": "openssl",
    "sqlite3": "sqlite", "curl": "curl", "gcrypt": "libgcrypt",
    "tag": "taglib", "mtp": "libmtp", "usb-1.0": "libusb",
    "magic": "libmagic", "exif": "libexif", "discid": "libdiscid",
    "chromaprint": "chromaprint", "mp3lame": "lame",
    # observed in gen_d: merge versioned library names from find_library/AC_CHECK_LIB (veal's
    # FindFluidSynth macOS dylib variants / swh's single-precision fftw)
    "fluidsynth-1": "fluidsynth", "fluidsynth-2": "fluidsynth",
    "fluidsynth-3": "fluidsynth",
    "fluidsynth": "fluid-synth",  # cmd-pkgs package name (observed in gen_d: the graph side relied on
                                   # the dashless fallback, invisible to the report side -- inconsistent scope)
    "sfftw": "fftw",
    # observed in libgen_g: OpenCV 4 imported target names (not the OpenCV::core naming form)
    # merged into opencv; jsoncppd is the debug variant name from Findjsoncpp
    "opencv_core": "opencv", "opencv_video": "opencv",
    "opencv_highgui": "opencv", "opencv_dnn": "opencv",
    "opencv_tracking": "opencv",
    "jsoncppd": "jsoncpp",
    # pkg-config module names without the lib prefix -> hb package name (gap confirmed in e2e corpus_c review)
    "xkbcommon": "libxkbcommon", "x11": "libx11",
    # graphviz link libraries (gen_j pkg_check_modules(libgvc) -> graphviz package)
    "libgvc": "graphviz", "libcgraph": "graphviz", "libcdt": "graphviz",
    # PC/SC smart card stack: find_package(PCSC)/pkg-config libpcsclite/find_library
    # pcsclite -> pcsc-lite
    "pcsc": "pcsc-lite", "libpcsclite": "pcsc-lite",
    "pcsclite": "pcsc-lite",
    # pkg-config name -> CMake find_package name (merge double declarations of the same library)
    # Note: libtorrent-rasterbar has no HarmonyOS package, so no alias is needed; merging the same library
    # under different names is covered by separator-free grouping (_dashless_key) and the dashless fallback
    # ---- gaps confirmed in e2e corpus_a (tier C) review ----
    # external_* imported target link names (cmake_helpers convention, bare name after stripping the prefix) -> package name
    "openal": "openal-soft",          # OpenAL Soft (kcat), pkg-config name openal
    "iconv": "libiconv",              # libiconv package (musl built-in iconv also works)
    "boost_regex": "boost",           # boost::regex component link -> boost package
    "cmark_gfm": "cmark-gfm",         # separator difference (_ vs -)
    "qr_code_generator": "libqrcodegen",  # nayuki QR-Code-generator (same origin as cmd-pkgs version 1.8.0)
    # ---- gaps confirmed in e2e corpus_b (tier C) review ----
    "alsa": "alsa-lib",           # find_package(ALSA) -> alsa-lib
    "sndfile": "libsndfile",      # find_package(SndFile) -> libsndfile
    "tinyxml": "tinyxml2",        # FindTinyXml actually looks for tinyxml2
    "glib2": "glib",             # CMake GLib2 module name
    "dbus1": "dbus",             # CMake DBus1 module name
    "ogg": "libogg",             # require_dep(ogg) / pkg-config ogg
    "vorbis": "libvorbis",       # require_dep(vorbis)
    "oggvorbis": "libvorbis",    # gen_d FindOggVorbis composite module name (internally
                                  # it is actually find_package(Ogg/Vorbis))
    "png": "libpng",             # CMake PNG module name
    "brotlidec": "brotli",       # pkg-config component name
    "intl": "gettext",           # CMake Intl module -> gettext(libintl)
    "utfcpp": "utf8cpp",         # require_source_dep(utfcpp) -> hb utf8cpp
    "nlohmann_json": "nlohmann-json",  # require_dep name -> hb nlohmann-json
    # -- observed in generalization tests (gen_b KDE, 2026-09) --
    "ddjvuapi": "djvulibre",     # djvulibre's pkg-config name (FindDjVuLibre
                                  # probes the same library with pkg_check_modules(ddjvuapi))
    "libmarkdown": "discount",   # discount's library/pkg-config name; hb markdown
                                  # is daringfireball's Perl/PHP version -- same name, different thing
    # -- additions from out-of-corpus generalization tests (observed in gen_f/gen_e/gen_a, 2026-09) --
    # glib family pkg-config modules (libgio/gobject/gthread/gmodule ship with the glib
    # package; both cmd-pkgs glib 2.88.0 and the hb glib bottle were verified to contain the .pc files)
    "gio-2.0": "glib", "gio-unix-2.0": "glib", "gobject-2.0": "glib",
    "gthread-2.0": "glib", "gmodule-2.0": "glib",
    "gmodule-no-export-2.0": "glib",
    # gstreamer core modules (the cmd-pkgs gstreamer tarball was verified to contain
    # libgst{base,controller,net,check}-1.0.so and the matching .pc files;
    # gstreamer-app/audio/pbutils/tag belong to gst-plugins-base and are not in the package,
    # so no alias is added and they fall back to the need_port verdict)
    "gstreamer-base-1.0": "gstreamer", "gstreamer-net-1.0": "gstreamer",
    "gstreamer-controller-1.0": "gstreamer",
    # fftw precision/threading variants (inside the same package, cmdpkgs:fftw 3.3.10)
    "fftw3": "fftw", "fftw3f": "fftw", "fftw3l": "fftw", "fftw3q": "fftw",
    "fftw3_omp": "fftw", "fftw3f_omp": "fftw", "fftw3l_omp": "fftw",
    "fftw3q_omp": "fftw", "fftw3_threads": "fftw",
    "fftw3f_threads": "fftw", "fftw3l_threads": "fftw",
    "fftw3q_threads": "fftw",
    # missing libav* entries (the missing libavfilter caused a false need_port in gen_a)
    "libavfilter": "ffmpeg", "libswresample": "ffmpeg",
    "libpostproc": "ffmpeg",
    # common variant names of various libraries (hb/cmd-pkgs package naming)
    "gif": "giflib",                       # gen_a find_package(GIF)
    "jpegxl": "libjxl", "libjxl_threads": "libjxl",  # cmdpkgs:libjxl
    "turbojpeg": "jpeg-turbo", "libturbojpeg": "jpeg-turbo",
    "turbojpeg-static": "jpeg-turbo", "jpeg-static": "jpeg-turbo",
    "webpdecoder": "webp", "webpdemux": "webp", "webpmux": "webp",
    "sharpyuv": "webp", "libsharpyuv": "webp",
    "libopenjp2": "openjpeg", "openjp2": "openjpeg",
    "openjpip": "openjpeg", "openjpip_server": "openjpeg",
    "libopenjpip": "openjpeg", "libopenjpip_server": "openjpeg",
    "harfbuzz-icu": "harfbuzz",
    "eigen3": "eigen",                      # gen_a find_package(Eigen3)
    "botan3": "botan-3",                    # gen_f find_package(Botan3)
    # OpenEXR 3.x components (the hb openexr bottle was verified to contain libIex/IlmThread/
    # OpenEXR/Core/Util; in 3.x Half belongs to imath)
    "iex": "openexr", "iexmath": "openexr", "ilmimf": "openexr",
    "ilmimfutil": "openexr", "ilmthread": "openexr",
    "openexrcore": "openexr", "openexrutil": "openexr",
    "half": "imath",
    # gsl's cblas component (shipped in the same hb/cmd-pkgs gsl package)
    "gslcblas": "gsl", "cblas": "gsl",
    "jpeg": "jpeg-turbo",                   # the hb package name is jpeg-turbo
    # lcms2 (hb package name little-cms2 / cmd-pkgs name lcms2)
    "lcms-2": "lcms2", "lcms2": "lcms2",
    "lcms-2_fast_float": "lcms2", "lcms2_fast_float": "lcms2",
    # Ogg (libogg package)
    # merge the same library under different names (without a package source, ghost nodes use the
    # canonical name, avoiding a duplicate need_port)
    "quazip-qt": "quazip", "kdcrawqt6": "kdcraw",
    # -- observed in the second round of Windows testing (tdesktop 7.4.4): names not matching, not missing libraries --
    # the project uses library names/upper-level aliases, the knowledge base uses upstream formula names
    "ada": "ada-url",              # cmake/external/ada -> hb:ada-url
    # Note: webrtc->tg_owt is tdesktop-specific naming (it uses Telegram's tg_owt).
    # For other projects depending on Google WebRTC this alias would give a wrong verdict, so it only
    # goes through suggest_packages' "possibly not matched" hint and is not normalized.
    "libudev": "udev",             # udev headers, the Linux-side equivalent
    "libudev-zero": "udev",
    # pkg-config module names of the pango family (shipped in one package, hb:pango)
    "pango": "pango", "pangocairo": "pango", "pangoft2": "pango",
    "pangoxft": "pango", "pango1.0": "pango", "pango-1.0": "pango",
    "pangomm-1.4": "pangomm", "pangomm-2.48": "pangomm",
    # versioned pkg-config names of the glibmm / gtkmm family
    "glibmm-2.4": "glibmm", "glibmm-2.68": "glibmm",
    "giomm-2.4": "glibmm", "giomm-2.68": "glibmm",
    "sigc++-2.0": "libsigc++", "sigc++-3.0": "libsigc++",
    # langtag variants of range-v3 and protobuf (measured on the tdesktop dependency list)
    "range-v3": "range-v3", "rangev3": "range-v3",
    "protobuf-lite": "protobuf", "libprotobuf-lite": "protobuf",
}


def _dashless_key(name: str) -> str:
    """Separator-free key: 'libtorrent-rasterbar' and 'libtorrentrasterbar' share a key.

    Used in two places: 1) scan-time merging of one library under different names (find_package's
    flattened CamelCase name vs the hyphenated pkg-config name); 2) fallback matching when resolution fails.
    """
    return re.sub(r"[-_.]+", "", (name or "").lower())


def build_dashless_index(conn) -> Dict[str, str]:
    """Separator-free index of package names: {dashless key: node id}.

    Lets flattened find_package CamelCase names (LibtorrentRasterbar ->
    libtorrentrasterbar) resolve to known HarmonyOS packages (libtorrent-rasterbar).
    Only known package sources (hb:/cmdpkgs:) are indexed -- indexing pkg-unknown ghost nodes would
    create a self-fulfilling loop where "the ghost from the previous scan is resolved as a known
    package by the next scan". On key collisions, the hb source / ported wins.
    """
    best: Dict[str, tuple] = {}
    try:
        rows = conn.execute(
            "SELECT id, name, port_status FROM nodes "
            "WHERE kind='package' AND id NOT LIKE 'pkg-unknown:%'"
        ).fetchall()
    except Exception:
        return {}
    for r in rows:
        key = _dashless_key(r["name"])
        if not key:
            continue
        rank = (r["id"].startswith("hb:"), r["port_status"] == "ported")
        cur = best.get(key)
        if cur is None or rank > cur[0]:
            best[key] = (rank, r["id"])
    return {k: v[1] for k, v in best.items()}


def resolve_package_dashless(conn, hint_name: str,
                             index: Optional[Dict[str, str]] = None) -> Optional[Dict]:
    """Fallback when resolution fails: match known package names by separator-free key.

    Only handles flattened multi-word names (key length >=6) to avoid short-name collisions; the
    typical case is the flattened name from find_package(LibtorrentRasterbar) matching a hyphenated
    package name like libtorrent-rasterbar. Returns None if nothing is found.
    """
    key = _dashless_key(hint_name)
    if len(key) < 6:
        return None
    if index is None:
        index = build_dashless_index(conn)
    nid = index.get(key)
    return db.get_node(conn, nid) if nid else None


def suggest_packages(conn, hint_name: str, limit: int = 3) -> List[str]:
    """Candidate packages when a name does not match (lets the report distinguish "not in the DB" from "name not matched").

    Scoring looks only at name shape and does not guess semantics: containment or prefix relations
    after stripping the lib prefix/version suffix/separators. Returns hb:/cmdpkgs: node names
    (deduplicated, keeping hb first and ported first).
    """
    name = (hint_name or "").lower().strip()
    if not name or len(name) < 2:
        return []
    base = re.sub(r"^lib", "", re.sub(r"-\d+(\.\d+)*$", "", name))
    key = _dashless_key(base)
    if len(key) < 3:
        return []
    try:
        rows = conn.execute(
            "SELECT id, name, port_status FROM nodes "
            "WHERE kind='package' AND id NOT LIKE 'pkg-unknown:%'"
        ).fetchall()
    except Exception:
        return []
    scored: Dict[str, int] = {}
    labels: Dict[str, str] = {}
    for r in rows:
        cand_key = _dashless_key(r["name"])
        if not cand_key:
            continue
        score = 0
        if cand_key == key:
            score = 100
        elif key in cand_key or cand_key in key:
            score = 60 - abs(len(cand_key) - len(key))
        elif len(key) >= 5 and (cand_key.startswith(key[:5])
                                or key.startswith(cand_key[:5])):
            score = 30
        if score <= 0:
            continue
        score += 5 if r["port_status"] == "ported" else 0
        score += 2 if r["id"].startswith("hb:") else 0
        if score > scored.get(cand_key, -1):
            scored[cand_key] = score
            labels[cand_key] = r["name"]
    ranked = sorted(scored.items(), key=lambda kv: -kv[1])[:limit]
    return [labels[k] for k, _ in ranked]


def resolve_package(conn, hint_name: str) -> Optional[Dict]:
    """Third-party library hint -> package node in the DB (hb first, ported first).

    Approximate alignment tries in order: the original name / adding the lib prefix (xkbcommon->libxkbcommon) /
    stripping the lib prefix / stripping the pkg-config version suffix (lilv-0->lilv, glib-2.0->glib)
    and their combinations; consistent with deps_report._resolve (previously only the deps side
    supported this, and the graph-side gap caused the lilv-0/zix-0 ghost nodes in e2e corpus_b).
    """
    name = (hint_name or "").lower()
    if not name:
        return None
    stripped = re.sub(r"-\d+(\.\d+)*$", "", name)
    cands = list(ALIASES.get(name, []))
    for c in (name, "lib" + name if not name.startswith("lib") else None,
              name[3:] if name.startswith("lib") and len(name) > 3 else None,
              stripped if stripped != name else None,
              "lib" + stripped
              if stripped != name and not stripped.startswith("lib") else None,
              stripped[3:]
              if stripped != name and stripped.startswith("lib")
              and len(stripped) > 3 else None):
        if c and c not in cands:
            cands.append(c)
    if not cands:
        return None
    best: Optional[Dict] = None
    for cand in cands:
        if not cand:
            continue
        for prefix in ("hb:", "cmdpkgs:"):
            node = db.get_node(conn, prefix + cand.lower())
            if node is None and prefix == "cmdpkgs:":
                node = db.find_node_by_name(conn, cand)
                if node and not node["id"].startswith("cmdpkgs:"):
                    node = None
            if node:
                if best is None or (node["port_status"] == "ported" and
                                    best["port_status"] != "ported"):
                    best = node
                break
        if best and best["port_status"] == "ported":
            break
    return best


def resolve_pkg_name(conn, name: str,
                      cache: Optional[Dict] = None) -> Optional[Dict]:
    """Library hint name (find_package/pkg-config/bare link) -> package node in the DB.

    The resolution scope shared by deps_report and project_scanner; tries in order:
      1. the alias table PKG_ALIASES (hb package naming, e.g. sqlite3->sqlite,
         libavfilter->ffmpeg; takes precedence over the original name so the same library under
         different names merges into one node, avoiding duplicate sqlite3/sqlite downloads)
      2. the original name / adding the lib prefix (xkbcommon->libxkbcommon) / stripping the lib prefix
      3. stripping the pkg-config version suffix (glib-2.0->glib) and combinations
    Shared by scan time and report time, eliminating the inconsistency where fetch-deps had ghost
    nodes that the deps report could resolve (observed with libsparsehash/gio-2.0).
    cache: per-analysis cache (including None misses; the graph does not change during an analysis).
    """
    if conn is None:
        return None
    key = (name or "").lower()
    if not key:
        return None
    if cache is not None and key in cache:
        return cache[key]
    node = None
    alias = PKG_ALIASES.get(key)
    if alias and alias.lower() != key:
        node = resolve_package(conn, alias.lower())
    if node is None:
        stripped = re.sub(r"-\d+(\.\d+)*$", "", key)
        cands = [key]
        if not key.startswith("lib"):
            cands.append("lib" + key)
        if key.startswith("lib"):
            cands.append(key[3:])
        if stripped != key:
            cands.append(stripped)
            if not stripped.startswith("lib"):
                cands.append("lib" + stripped)
            else:
                # strip both the lib prefix and the version suffix (libpipewire-0.3 -> pipewire;
                # observed in libgen_g, where stripping either alone does not match)
                cands.append(stripped[3:])
        # build-flavor suffixes in find_library NAMES (libFLAC_static / jpeg-static
        # / libFLAC_dynamic) -> base name
        for base in list(cands):
            s2 = re.sub(r"[_-](static|dynamic|debug)$", "", base)
            if s2 != base and s2 not in cands:
                cands.append(s2)
        # expand each candidate's alias (libfftw3 -> strip prefix fftw3 -> alias fftw;
        # libwebpmux -> webpmux -> webp)
        expanded: List[str] = []
        for cand in cands:
            expanded.append(cand)
            a = PKG_ALIASES.get(cand)
            if a and a.lower() not in expanded:
                expanded.append(a.lower())
        for cand in expanded:
            node = resolve_package(conn, cand)
            if node:
                break
    if cache is not None:
        cache[key] = node
    return node


def ingest(conn) -> Dict:
    db.init_db(conn)
    modules = seed_qt_modules(conn)
    seed_interfaces(conn)
    db.set_meta(conn, "ingest_kb_at", db.now())
    db.set_meta(conn, "qt_module_count", str(len(modules)))
    conn.commit()
    return {
        "qt_modules": len(modules),
        "blocked_modules": [m["name"] for m in modules if m["status"] == "blocked"],
        "interfaces": len(INTERFACE_SEEDS),
    }
