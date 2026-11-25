# corpus-b Dependency Reconciliation Report (portgraph E2E)

> Generated: 2026-09-19T15:12:53Z | Corpus: corpus.json#corpus-b | Build system: cmake+qmake | Source files: 5729
> Oracle: buildscripts/cmake/DependencyManifest.cmake + corpus-b-core/buildscripts/cmake/ExtDepsManifest.cmake + corpus-b-core/framework/{midi,audio/driver}/CMakeLists.txt + corpus-b-core/framework/cmake/CorpusBOptions.cmake (compiled by hand) (review: reviewed, 25 entries; origin: Rewritten for master 2b540fe (the corpus-b-deps dependency-engine era): the README has no dependency section (it points to an external project wiki), so the oracle was compiled by hand from the in-repo dependency manifests. Scope = dependencies that need external artifacts in the default build: require_dep(...) (prebuilt/system mode) and the project's own find_package are runtime/optional; require_source_dep (liblouis/kddockwidgets/picojson/pugixml/utfcpp/googletest/crashpad_client/vst3sdk/lodepng/asiosdk) and mnxdom's FetchContent source mode are vendored, built with the project source and needing no external artifacts, so they are not in the oracle; require_tool/find_package(Git) are host build tools, listed as build. Optionality follows the CorpusBOptions.cmake defaults: CB_MODULE_AUDIO_JACK OFF, CB_MODULE_AUDIO_PIPEWIRE OFF, CB_MODULE_DRAW_USE_QTTEXTDRAW ON (-> msdfgen not enabled), CB_USE_SYSTEM_MNXDOM OFF (-> mnxdom is bundled as source by default; pkg_check only in system mode); CB_MODULE_AUDIO_EXPORT ON, CB_BUILD_IMPEXP_MNX_MODULE ON. The old oracle's (CI setup.sh + CB_COMPILE_USE_SYSTEM_* era) pulseaudio/openssl/tinyxml/ffmpeg no longer exist on master: direct PulseAudio use survives only in the embedded fluidsynth optional driver, and openssl is not referenced by any manifest.)

## 1. Summary

| Metric | Value |
|---|---|
| Portability verdict | **blocked** (blocked 8 / unknown 4 / platform-excluded 1) |
| Detection recall | 100% (16/16 README runtime deps) |
| Detection precision | 95% |
| Bug candidates | **0** (none) |
| Dependency closure | 89 items (cmd_only 1, need_port 4, provided 16, target 1, vendored 10, would_download 57) |

**Agent review notes**:

- Oracle rewritten for master 2b540fe (corpus-b-deps dependency engine): require_dep manifests (DependencyManifest/ExtDepsManifest) + project find_package (ALSA/Jack/mnxdom) + SetupQt6.cmake; optionality follows CorpusBOptions.cmake defaults. The 10 source-bundled require_source_dep dependencies (liblouis/kddockwidgets/picojson/pugixml/utfcpp/googletest/crashpad_client/vst3sdk/lodepng/asiosdk) are out of oracle scope (built with the project source, no external artifacts needed); portgraph expresses them as vendored edges + fetch-deps status=vendored.
- The 10 ALIASES gaps from the previous round (old repo, CI setup.sh era) were fixed and committed in this round (alsa->alsa-lib, sndfile->libsndfile, tinyxml->tinyxml2, glib2->glib, dbus1->dbus, ogg->libogg, vorbis->libvorbis, png->libpng, brotlidec->brotli, utfcpp->utf8cpp, nlohmann_json->nlohmann-json, intl->gettext); false positives from fluidsynth/KDDockWidgets embedded third-party code and corpus-b-deps recipes were fixed by skipping vendored paths; find_package false matches on comment lines were fixed by comment stripping; the wrongful exclusion of the buildscripts/ directory (build* prefix) was fixed.
- Residual (not fixed in this round): require_dep conditional blocks are not evaluated (declarations off by default such as msdfgen/pipewire/asiosdk still enter the closure, so the fetch-deps overview is conservative); project-internal target names in the deps report's raw_libs (engraving/global/cb_* etc., created by functions like declare_module and invisible to the add_library scan) resolve to hb:global by coincidence, which is noise.

## 2. Portability Verdict (analyze)

| Blocker kind | Node | Reason |
|---|---|---|
| unsupported-interface | app:corpus-b | uses platform interface Direct ALSA unsupported on HarmonyOS (audio) HarmonyOS audio goes through AudioRenderer/AudioCapturer; ALSA is unavailable; HarmonyOS al |
| unsupported-interface | app:corpus-b | uses platform interface macOS CoreAudio unsupported on HarmonyOS (audio) macOS-only audio framework; HarmonyOS alternative interfaces in the same category: Harm |
| unsupported-interface | app:corpus-b | uses platform interface D-Bus IPC unsupported on HarmonyOS (ipc) HarmonyOS has no D-Bus (the Qt D-Bus module is out of scope); switch to system services/IPC; Ha |
| unsupported-interface | app:corpus-b | uses platform interface Direct PulseAudio unsupported on HarmonyOS (audio) HarmonyOS has no PulseAudio service; HarmonyOS alternative interfaces in the same cat |
| unsupported-interface | app:corpus-b | uses platform interface systemd unsupported on HarmonyOS (os-api) HarmonyOS has no systemd service management; HarmonyOS alternative interfaces in the same cate |
| unsupported-interface | app:corpus-b | uses platform interface Win32 API unsupported on HarmonyOS (os-api) Windows-only system interface; HarmonyOS alternative interfaces in the same category: dlopen |
| unsupported-module | qtmod:dbus | Qt for HarmonyOS module support table: unsupported - HarmonyOS has no D-Bus |
| unsupported-module | qtmod:x11extras | Qt for HarmonyOS module support table: unsupported - X11-only |

4 unconfirmed items:
- [unknown-package] pkg-unknown:msdfgen: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:opusenc: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:pipewire: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list
- [unknown-package] pkg-unknown:json-schema-validator: no HarmonyOS prebuilt artifact, must be cross-compiled and ported yourself; not in the Harmonybrew/cmd-pkgs known list

## 3. Difference Attribution Details (oracle x portgraph direct deps)

| Class | README side | portgraph side | Type/depth | Evidence/notes |
|---|---|---|---|---|
| README omitted | — | global | package d1 | referenced by build files but not listed in README -> README incomplete (portgraph correct) |
| Optional, not enabled | jack | — | optional | optional dependency, not enabled in the default build |
| Optional, not enabled | mnxdom | — | optional | optional dependency, not enabled in the default build |
| Build tool | git | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | crashpad_handler | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | sentry-cli | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | dump_syms | — | build | build tool; fetch-deps does not collect build edges |
| Build tool | uncrustify | — | build | build tool; fetch-deps does not collect build edges |
| Granularity folded | — | Qt Core | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt D-Bus | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt GUI | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Network | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Network Authorization | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Print Support | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt QML | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Quick | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Quick Widgets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt SVG | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Test | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt WebSockets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt Widgets | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt X11 Extras | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Granularity folded | — | Qt XML | qt-module d1 | Qt module granularity: README usually just says 'Qt' |
| Matched | qt | Qt Concurrent | qt-module d1 |  |
| Matched | alsa | alsa-lib | package d1 |  |
| Matched | ogg | libogg | package d1 |  |
| Matched | vorbis | libvorbis | package d1 |  |
| Matched | flac | flac | package d1 |  |
| Matched | opus | opus | package d1 |  |
| Matched | libsndfile | libsndfile | package d1 |  |
| Matched | zlib | zlib | package d1 |  |
| Matched | freetype | freetype | package d1 |  |
| Matched | harfbuzz | harfbuzz | package d1 |  |
| Matched | libpng | libpng | package d1 |  |
| Matched | fdk-aac | fdk-aac | package d1 |  |
| Matched | lame | lame | package d1 |  |
| Matched | opusenc | opusenc | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) [agent: No bottle confirmed: neither hb-core nor cm |
| Matched | nlohmann_json | nlohmann-json | package d1 |  |
| Matched | json_schema_validator | json_schema_validator | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) [agent: No bottle confirmed: neither hb-core nor cm |
| Matched (optional) | msdfgen | msdfgen | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) [agent: No bottle confirmed: neither hb nor cmd-pkg |
| Matched (optional) | pipewire | pipewire | package d1 | matched a ghost node: real external dependency with no known HarmonyOS package (fetch-deps reports need_port/needs a source port; detection correct) [agent: No bottle confirmed: hb/cmd-pkgs indeed hav |

Class counts: Build tool×5, Matched×16, Matched (optional)×2, Optional, not enabled×2, Granularity folded×15, README omitted×1

## 4. Dependency Closure Overview (fetch-deps --dry-run)

- Closure total 89 items: cmd_only 1, need_port 4, provided 16, target 1, vendored 10, would_download 57
- Bottle directly downloadable: alsa-lib, freetype, zlib, harfbuzz, libpng, libogg, fdk-aac, flac, lame, opus, libvorbis, libsndfile, nlohmann-json, global, zlib-ng-compat, cairo, glib, graphite2, icu4c@78, mpg123, libtool, ncurses, python@3.14, sqlite, universal-ctags, fontconfig, libx11, libxcb, libxext, libxrender, lzo, pixman, bison, python-setuptools, pcre2, dbus, util-linux, m4, mpdecimal, openssl@3
- Command-only fetch (cmd_only): ca-certificates
- Needs own port (need_port): msdfgen, opusenc, pipewire, json_schema_validator
  - msdfgen: ?
  - opusenc: ?
  - pipewire: ?
  - json_schema_validator: ?

## 5. Full Direct Dependency List (portgraph depth-1)

| Node | Type | Edge | port_status | Depth |
|---|---|---|---|---|
| alsa-lib | package | runtime | ported | 1 |
| fdk-aac | package | runtime | ported | 1 |
| flac | package | runtime | ported | 1 |
| freetype | package | runtime | ported | 1 |
| global | package | runtime | ported | 1 |
| harfbuzz | package | runtime | ported | 1 |
| json_schema_validator | package | runtime | unknown | 1 |
| lame | package | runtime | ported | 1 |
| libogg | package | runtime | ported | 1 |
| libpng | package | runtime | ported | 1 |
| libsndfile | package | runtime | ported | 1 |
| libvorbis | package | runtime | ported | 1 |
| msdfgen | package | runtime | unknown | 1 |
| nlohmann-json | package | runtime | ported | 1 |
| opus | package | runtime | ported | 1 |
| opusenc | package | runtime | unknown | 1 |
| pipewire | package | runtime | unknown | 1 |
| zlib | package | runtime | ported | 1 |
| Qt Concurrent | qt-module | uses-module | ported | 1 |
| Qt Core | qt-module | uses-module | ported | 1 |
| Qt D-Bus | qt-module | uses-module | blocked | 1 |
| Qt GUI | qt-module | uses-module | ported | 1 |
| Qt Network | qt-module | uses-module | ported | 1 |
| Qt Network Authorization | qt-module | uses-module | ported | 1 |
| Qt Print Support | qt-module | uses-module | ported | 1 |
| Qt QML | qt-module | uses-module | ported | 1 |
| Qt Quick | qt-module | uses-module | ported | 1 |
| Qt Quick Widgets | qt-module | uses-module | ported | 1 |
| Qt SVG | qt-module | uses-module | ported | 1 |
| Qt Test | qt-module | uses-module | ported | 1 |
| Qt WebSockets | qt-module | uses-module | ported | 1 |
| Qt Widgets | qt-module | uses-module | ported | 1 |
| Qt X11 Extras | qt-module | uses-module | blocked | 1 |
| Qt XML | qt-module | uses-module | ported | 1 |

## 6. Methodology

- Comparison scope: portgraph direct deps (depth-1 edges) vs deps declared in README/INSTALL; the closure is only an artifact overview.
- Attribution evidence: for unmatched items, automatically grep the cloned repo's build files (find_package/pkg_check_modules/target_link_libraries/vcpkg, etc.).
- ★ classes (missed-dep / resolution-gap / false-positive) are bug candidates requiring manual confirmation; the rest are expected differences.
- Agent-readable report: `tests/e2e/reports/corpus-b.report.json`
