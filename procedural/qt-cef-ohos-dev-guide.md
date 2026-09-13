---
id: procedural-qt-cef-ohos-dev-guide
type: procedural
domain: workflow
tags: [qt, cef, chromium, harmonyos, ohos, webengine, migration, webview, cmake, hap, arkweb, js-bridge, version-adaptation, component-pack]
created: 2026-08-25
updated: 2026-08-26
status: active
audience: public
refs: [semantic-qt-harmonyos-modules, semantic-qt-harmonyos-qt6-status, semantic-qt-harmonyos-window-model, semantic-qt-harmonyos-third-party-libs, semantic-qt-harmonyos-build-run-workflow, semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-api-mapping, procedural-demo-generation]
summary: >
  A Qt + CEF HarmonyOS development guide (public, self-contained, version-neutral): Qt on HarmonyOS has no QtWebEngine (out of scope), and CEF for OpenHarmony
  (chromium_cef) is the full-Chromium-engine replacement for web embedding. **Not tied to a specific Qt version** (works for Qt 5.12/5.15/Qt6 — adapt by reading your
  Qt OHOS SDK headers per §5.1). CEF is delivered as a **de-versioned component package**: the maintainer strips the engine layer out of a versioned chromium_cef download (libcef.so +
  wrapper + include + cmake + the OHOS adapter), labels it by version, decouples it from the application and the glue code, and puts it in a known location for developers to download; integration is version-neutral
  (find_package(CEF) + CEF_ROOT, reading the component's include/ to find that version's API). Part 1 is the version-stable core and Part 2 is a worked integration (given a CEF component package +
  your Qt OHOS SDK). Includes a WebEngine→CEF API mapping, migration steps, and §5's methodology for adapting to a version upgrade.
leader_summary: >
  Fills the gap left by Qt on HarmonyOS having no WebEngine-class web engine: building on Huawei's official open-source CEF for OpenHarmony, it captures a Qt + CEF HarmonyOS development guide +
  a WebEngine→CEF migration; **not tied to a Qt version, with CEF distributed as a de-versioned component package** (stripping / downloading / version-neutral integration), plus a version-upgrade adaptation
  methodology, so migrations go faster, developer questions get answered, and upgrades don't leave you stranded.
impact: [faster migration, framework support, commercial responses, developer guidance]
deliverables: [a development guide page, a WebEngine→CEF migration plan, an API mapping table, the CEF component package stripping method, a version-upgrade adaptation methodology, an AI end-to-end checklist]
evidence: [verification of the chromium_cef 114 release branch source structure (41 OHOS adaptation files in libcef + tests/cefsimple + cmake/FindCEF + the include API headers), Huawei guidebook solution6 §5 CEF for OpenHarmony]
---

# A Qt + CEF HarmonyOS development guide (public, self-contained, version-neutral)

> **In one line**: Qt on HarmonyOS (5.12/5.15/Qt6) **has no QtWebEngine** (Chromium is out of scope). Applications that need a full Chromium web engine should use Huawei's official open-source **CEF for OpenHarmony** (`gitcode.com/openharmony-tpc/chromium_cef`) instead.
>
> **This page deliberately isn't tied to a specific Qt version**: it works for Qt 5.12 / 5.15 / Qt6. The Qt OHOS QPA/Ability launch APIs and the `main` export contract for your .so vary with your Qt SDK version — find yours by reading your SDK's headers per §5.1.
>
> **CEF is distributed as a de-versioned component package**: the maintainer **strips** the CEF engine layer (libcef.so + the wrapper sources + include + cmake + the OHOS adapter) out of a versioned chromium_cef download, labels it by version, decouples it from the application and the glue code, and puts it in a known location for developers to download. Integration is **version-neutral**: `find_package(CEF)` + a `CEF_ROOT` pointing at the component package, and you read the component's `include/` to find that version's API.
>
> **Structure**: Part 1 is the version-stable core (§1–§5) + Part 2 is a worked integration (version-neutral, given a CEF component package + your Qt OHOS SDK).
>
> The version-sensitive parts (the node manager API, the IoC container, the subprocess entry symbol, the Ability→Qt launch API, the `main` export contract) are **deliberately not hardcoded here as universal interfaces** — they change with the Qt OHOS QPA / CEF component / glue layer version, so read the authoritative source for your version per §5.

---

## 0. Version neutrality and the stability map

### Three independent version layers (none tied to another)

| Layer | Whose version decides it | The authoritative source (where the correct API for your version lives) |
|-------|--------------------------|-------------------------------------------------------------------------|
| **The CEF component** | The CEF version you downloaded/stripped (e.g. cef114-ohos5.1 / cef132-ohos6.0) | Your CEF component package's `include/`, `cmake/`, `libcef_dll/` (§2) |
| **The Qt OHOS SDK** | The Qt version you use (5.12 / 5.15 / Qt6) | Your SDK's `libqohos.d.ts` / `qohos*.h` / `templates/EntryAbility.ets` (§5.1) |
| **The glue layer** | The glue layer version you use (the CEF↔ArkTS↔Qt bridge, a separate project) | The glue layer repository itself (the native adapter headers + the ArkTS IoC module) (§5.3) |

> The three layers are **mutually independent**: the CEF component package isn't tied to a Qt version (it's pure C ABI, Qt-agnostic); your Qt SDK version isn't tied to CEF; the glue layer version isn't tied to either. Upgrading any one layer doesn't affect the other two.

### The stability table

| Content | Stability | Notes |
|---------|:---------:|-------|
| The five-layer CEF architecture concept (engine/wrapper/client/Qt window/Ability) | ✅ Stable | It's CEF's design, across versions |
| CEF's public API in `include/` (CefClient/CefBrowser/handlers) | ✅ Stable | The main API is stable across versions; for the OHOS extension methods, your component's `include/` is authoritative |
| The `find_package(CEF)` + `CEF_ROOT` cmake pattern | ✅ Stable | It comes from the component's `cmake/FindCEF.cmake` |
| The iron rule of CEF's own thread + its own message loop + marshalling | ✅ Stable | A CEF architectural baseline |
| `.so` deployment + the dependency chain + permissions + HAP packaging | ✅ Stable | An OHOS mechanism |
| The WebEngine→CEF API mapping + migration steps | ✅ Stable | CEF's API roles ≈ WebEngine's |
| ② The native node manager's API names | ⚠️ Version-sensitive | Varies with the glue layer version, see §5.3 |
| ③ The IoC container module name + binding API + init parameters | ⚠️ Version-sensitive | Varies with the glue layer version, see §5.3 |
| ③ The subprocess entry symbol name + the QPA dlsym contract | ⚠️ Version-sensitive | Varies with the Qt OHOS QPA + CEF version, see §5.1/§5.2 |
| ⑤ The Ability→Qt launch API | ⚠️ Version-sensitive | Varies with the Qt OHOS QPA version, see §5.1 |
| The `main` export contract for your .so | ⚠️ Version-sensitive | Varies with the Qt OHOS QPA version, see §5.1 |
| The OHOS adapter `.so` name | ⚠️ Version-sensitive | Varies with the CEF component version, see §5.2 |

> **The principle**: for the ⚠️ version-sensitive items, this page only gives the "what to do / why" (the invariants) and **does not** give specific API names or signatures (they'd go stale); the authoritative source for your version (§5.4) is what counts.

---

# Part 1 — The version-stable core

## 1. Background and positioning

### 1.1 Why you need CEF

| Aspect | Status on Qt for HarmonyOS | Notes |
|--------|:--------------------------:|-------|
| **QtWebEngine** (the Chromium engine, QWebEngineView/QWebEnginePage) | ❌ **Out of scope** | Chromium is only ported to the Windows/Linux/macOS desktops; none of Qt 5.12/5.15/Qt6 on HarmonyOS provides it. See [[qt-harmonyos-modules]] |
| **Qt WebView** (a bridge to the native ArkWeb) | ✅ Supported | Wraps HarmonyOS's system Web component (ArkWeb); lightweight |
| **CEF for OpenHarmony** (full Chromium embedding) | ✅ Officially open-source | `chromium_cef`, the complete Chromium content layer; heavyweight but the closest in capability to WebEngine |

Applications that depend on `QWebEngineView` and need a full Chromium engine (DevTools, extensions, offscreen rendering, complex JS/Blink behavior, fine-grained cookie/download control) should pick **CEF**; if you only need lightweight page display, first evaluate the ✅ **Qt WebView** in [[qt-harmonyos-modules]] (see §4.2).

### 1.2 Official guidance sources

| Source | Link | Nature |
|--------|------|--------|
| Huawei's guidebook "Third-party cross-platform framework solutions" §5 CEF for OpenHarmony | https://developer.huawei.com/consumer/cn/doc/guidebook/solution6-0000002601573495 | Official; an overview of porting Chromium/CEF/Electron/Qt and other frameworks to HarmonyOS |
| The CEF for OpenHarmony source repository | https://gitcode.com/openharmony-tpc/chromium_cef | Officially open-source (2025-06); branches 114 (HarmonyOS 5.x) / 132 (HarmonyOS 6.0) |
| The forum article "CEF framework HarmonyOS development guide" | https://developer.huawei.com/consumer/cn/forum/topic/0204189797656362142 | An official technical article (a forum page; you need to be logged in to read it) |
| The Chromium for OpenHarmony source repository | https://gitcode.com/openharmony-tpc/chromium_src | Officially open-source; the foundation CEF sits on |
| The upstream CEF project | https://bitbucket.org/chromiumembedded/cef | The original CEF documentation/tutorial/API docs |

---

## 2. The CEF component package: de-versioning, stripping, and obtaining it (the core)

### 2.1 What a CEF component package is

A CEF component package = **the CEF engine layer**, de-versioned, independent of Qt and of your application, labelled by version, and downloadable:

| Content | Purpose |
|---------|---------|
| `libcef.so` | The CEF engine (the Chromium content layer), prebuilt and heavyweight |
| `libcef_dll/` (source) | The C++ wrapper layer (the C API → `CefRefPtr<CefBrowser>` and friends), rebuilt with your application |
| `include/` | CEF's public C++ API headers — **the correct API for your component version lives here** |
| `cmake/` | `FindCEF.cmake` + `cef_macros` + `cef_variables` (the `find_package(CEF)` pattern) |
| The OHOS adapter `.so` | The CEF↔OHOS adaptation bridge (its name varies with the CEF component version, see §5.2) |
| `tests/cefsimple` (optional) | A reference example |
| `tools/kb-cef-graft.py` + `tools/kb-cef-graft.config.example.json` (bundled) | The grafting script + its config: grafts CEF onto a Qt OHOS template project (§2.3 one-command grafting; `--run` does signing + install + launch + a crash check; it lives under the external knowledge base's `tools/` and is renamed to `tools/graft_cef.py` when the CEF component package is stripped) |

> What **de-versioned** means: the version is labelled in the **package/directory name** (e.g. `cef-component-ohos-cef114/`) while the **contents are a version-neutral engine layer** — no Qt, application or glue code mixed in. The integration method (`find_package(CEF)` + `CEF_ROOT`) is the same across versions. Whichever version you download, you use that version's API (by reading its `include/`).

### 2.2 Stripping a component package out of a versioned chromium_cef download (the de-versioning method)

Each branch of the `chromium_cef` repository is a **versioned CEF** (114 / 132 / ...). Stripping means extracting the engine layer, labelling it by version, and decoupling it from the application and the glue code:

```bash
# 1. Get a versioned chromium_cef (the branch for the version you chose)
git clone https://gitcode.com/openharmony-tpc/chromium_cef.git
cd chromium_cef
git checkout <the version branch you chose>   # e.g. 114_trunk_5.1.0-Release / 132_trunk_6.0-Release

# 2. Materialize the CMake files (.in templates → usable .cmake; needs the upstream CEF toolchain)
bash cef_create_projects.sh

# 3. Strip the component package into its own directory (the version goes in the directory name)
VER=<the version label, e.g. cef114-ohos5.1 or cef132-ohos6.0>
PKG=cef-component-ohos-$VER
mkdir -p $PKG/libs/arm64-v8a
cp -r include cmake libcef_dll $PKG/                         # the API + cmake + the wrapper sources (Qt-agnostic)
cp -r tests/cefsimple $PKG/                                   # the reference example (optional)
# The prebuilt engine (from the build output or from a prebuilt binary distribution):
cp <libcef.so + the OHOS adapter .so + the dependency .so files (icu/freetype/fontconfig/expat/brotli/jpeg/png)> $PKG/libs/arm64-v8a/
# 4. Bundle the grafting tool (kb-cef-graft.py, shipped with the component package; the maintainer takes it from the KB repo's _scripts/)
mkdir -p $PKG/tools
cp <the KB repo>/_scripts/kb-cef-graft.py $PKG/tools/graft_cef.py
# → $PKG/ is now the "de-versioned CEF component package": the version is in the directory name and the contents are a version-neutral engine layer + the bundled grafting tool
```

> **The key points of de-versioning**:
> - **Extract the engine layer only** (libcef.so + the wrapper sources + include + cmake + the OHOS adapter) — these are Qt- and application-agnostic, pure C ABI + the CEF API.
> - **Don't mix in Qt/application/glue code** (the node manager, the CefClient business implementation and the ArkTS IoC are not in the component package; developers implement them per §B/§5.3).
> - **Label the version in the package name** (`cef-component-ohos-<ver>/`), not hardcoded in the contents.
> - **Bring the dependency chain along** (libcef.so's DT_NEEDED: icu/freetype/fontconfig/expat/brotli/jpeg/png); check it's complete with `llvm-readelf -d libcef.so`.
>
> The maintainer packages `$PKG/` and puts it in the agreed download location (§2.3 option A). Building CEF from source in full (gclient fetch Chromium, several GB) is only necessary when there's no prebuilt binary — see CEF upstream's `BranchesAndBuilding` wiki.

### 2.3 Getting a CEF component package

- **Option A (recommended, maintainer-distributed)**: download `cef-component-ohos-<ver>/` from the maintainer's location → extract it → point `CEF_ROOT` at it.
  - Download URL: `<the CEF component package download URL provided by the maintainer (fill this in before release)>`
  - **One-command grafting**: use the grafting script to graft CEF onto your Qt OHOS template project (the right way round: graft onto the template, don't modify a CEF demo). The script is in the **external knowledge base at `tools/kb-cef-graft.py`** (renamed to `tools/graft_cef.py` when the CEF component package is stripped) with the config `tools/kb-cef-graft.config.example.json`:
    ```bash
    # 1. Copy the config and edit the values (deveco/device/qt_libs etc.; see the _comment fields)
    cp tools/kb-cef-graft.config.example.json .config.json  # edit the values inside
    # 2. One command: graft + sign + install + launch + crash check (verified end to end with the full --ohqtcef-glue overlay)
    python tools/kb-cef-graft.py --config .config.json \
      --template <the Qt OHOS template project> --qt-sdk <your Qt OHOS SDK> \
      --ohqtcef-glue <the OpenQtCef glue> --output <the output project> --run
    ```
    (`--run` automatically does devecocli signature generate + run + log --crash; see the script's `--help` + §B/§5. All the environment configuration lives in `.config.json`, so moving to another machine only means editing the config, not the script.)
- **Option B (strip it yourself)**: follow §2.2 to strip the version you chose out of `chromium_cef`.

> Either way, the integration is the same: `find_package(CEF)` + a `CEF_ROOT` pointing at the component package; read `CEF_ROOT/include/` to find that version's API (§5.2).

### 2.4 Version-neutral integration

- Point `CEF_ROOT` at your CEF component package (any version); `find_package(CEF)` loads its `cmake/`.
- Your .so links `${CEF_ROOT}/libs/arm64-v8a/libcef.so` + `libcef_dll_wrapper` (rebuilt) + the OHOS adapter.
- For your CEF version's API: read `${CEF_ROOT}/include/` (§5.2).
- For the OHOS extension methods (`NotifyJavaScriptResult`/`OnScaleChanged`/`PutAcceptCookieEnabled` etc.), your component's `include/` is authoritative.

---

## 3. The CEF-for-OHOS engine architecture (version-stable)

### 3.1 The CEF engine layer (pure C ABI / Qt-agnostic)

See §2.1 for the component package contents. The `*_ohos.cc` files inside `libcef` (the OHOS implementations of browser/net/ssl/safe_browsing/printing/cookie/applink) are already compiled into `libcef.so`, so you don't have to care about them.

> **OHOS-specific extensions** (verified against the 114 release source; **they may change, be added or be removed across CEF versions, so your component's `include/` is authoritative** — see §5.2):
> - `CefClient` has built-in **JS object binding**: `NotifyJavaScriptResult` / `HasJavaScriptObjectMethods` / `GetJavaScriptObjectMethods` / `RemoveTransientJavaScriptObject` (the equivalent of QWebChannel/`registerJavaScriptObject`).
> - `CefCookieManager` cookie policy control: `IsAcceptCookieAllowed`/`PutAcceptCookieEnabled`, `IsThirdPartyCookieAllowed`/`PutAcceptThirdPartyCookieEnabled` and so on.
> - `CefDisplayHandler` OHOS-specific: `OnScaleChanged`/`OnScaleInited`/`OnContentsBrowserZoomChange`.
> - `CefLoadHandler` OHOS-specific: `OnPageVisible`/`OnRefreshAccessedHistory`/`OnFirstContentfulPaint`/`OnNavigationEntryCommitted` and so on.

### 3.2 CEF's public API (`include/`, the main API that's stable across versions)

The core objects: `CefApp` (process-level, `cef_app.h`), `CefClient` (**the client aggregator** that returns the handlers, ≈ `QWebEnginePage`, `cef_client.h`), `CefBrowser`/`CefBrowserHost` (`CreateBrowser`/`LoadURL`/`ExecuteJavaScript`/`ShowDevTools`, ≈ `QWebEngineView` + page), `CefFrame` (`ExecuteJavaScript` runs on a frame), and the handlers (≈ QWebEnginePage's signals).

The handlers `CefClient` aggregates (`cef_client.h`): `GetDisplayHandler`/`GetLifeSpanHandler`/`GetLoadHandler`/`GetRequestHandler`/`GetDownloadHandler`/`GetContextMenuHandler`/`GetFocusHandler`/`GetJSDialogHandler`/`GetKeyboardHandler`/`GetDragHandler`/`GetFindHandler`/`GetPermissionHandler`/`GetPrintHandler`/`GetRenderHandler`/`GetAudioHandler`/`GetMediaHandler`/`GetFormHandler`/`GetFrameHandler` + `OnProcessMessageReceived` (IPC) + the JS object binding methods.

### 3.3 The cefsimple learning example (`tests/cefsimple` in the component package)

The minimal CEF client worth studying (verified against the `simple_handler.h` source):

```cpp
// One class implements CefClient plus several handlers at once (the typical style)
class SimpleHandler : public CefClient,
                      public CefDisplayHandler, public CefLifeSpanHandler, public CefLoadHandler {
  CefRefPtr<CefDisplayHandler>  GetDisplayHandler() override  { return this; }
  CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler() override { return this; }
  CefRefPtr<CefLoadHandler>     GetLoadHandler() override      { return this; }
  void OnTitleChange(CefRefPtr<CefBrowser>, const CefString&) override;
  void OnAfterCreated(CefRefPtr<CefBrowser>) override;
  bool DoClose(CefRefPtr<CefBrowser>) override;
  void OnBeforeClose(CefRefPtr<CefBrowser>) override;
  void OnLoadError(...) override;
};
```

> **The key point**: the comment on `SimpleHandler` says "Only accessed on the CEF UI thread" — **every CEF callback runs on CEF's own UI thread**, not on the Qt main thread. This is the single biggest thing to watch out for when integrating with Qt (§4 marshalling, §D pitfalls).
>
> `simple_app.cc` uses CEF's **Views framework** (`CefWindow`/`CefBrowserView`) for windowed rendering — a desktop approach. **OHOS doesn't use Views** (there's no traditional window reparenting, see [[qt-harmonyos-window-model]]); instead you use an XComponent surface + a native node manager (§B). The `CefClient`/handler style from cefsimple is reusable; only the windowing part changes.

### 3.4 CMake integration (`cmake/FindCEF.cmake`, a pattern that's stable across versions)

The entry point is `find_package(CEF REQUIRED)`: it needs a CEF component package (materialized `cmake/*.cmake` + `CMakeLists.txt` + `libcef_dll/CMakeLists.txt` + a prebuilt `libcef.so`). `FindCEF.cmake` requires `CEF_ROOT` (a CMake or environment variable) pointing at the component package root; `ADD_LOGICAL_TARGET("libcef_lib" ...)` registers libcef, `add_subdirectory(libcef_dll)` builds the wrapper, and your target links `libcef_dll_wrapper` + `libcef_lib` + `libcef.so`. It requires CMake ≥ 3.19.

### 3.5 The key mechanism: CEF's own thread + its own message loop

CEF's initialization starts its own thread running `CefRunMessageLoop` (its own message loop), which is **completely separate from the Qt main thread's `QEventLoop`, with no event loop integration**. Qt↔CEF communication uses CEF's `PostTask` for cross-thread dispatch plus callbacks. This is the architectural baseline that drives §4's marshalling and §D's pitfalls.

---

## 4. Migrating from WebEngine to Qt + CEF (version-stable)

### 4.1 Why migrate

`QWebEngineView`/`QWebEnginePage` are **unavailable** on Qt for HarmonyOS (out of scope, [[qt-harmonyos-modules]]). CEF provides the complete Chromium content layer, and its API roles map closely onto WebEngine's, making it the replacement with the least rework.

### 4.2 First assess whether Qt WebView would do

| Scenario | Pick |
|----------|------|
| Just displaying pages, basic navigation, simple JS interaction | **Qt WebView** (the native ArkWeb bridge, ✅ in [[qt-harmonyos-modules]], lightweight) |
| You need DevTools, extensions, offscreen rendering, specific Blink behavior, fine-grained cookie/download/permission control, or complex injected JS objects | **CEF** (full Chromium) |
| The code depends heavily on `QWebEnginePage`'s handler/signal model | **CEF** (the handler model maps one to one) |

### 4.3 The API mapping table (QWebEngine* → CEF)

> The CEF callback signatures come from verifying `chromium_cef/include/*.h` (the 114 release) against the source; **the main API is stable across versions**, and for the OHOS extension methods your component's `include/` is authoritative (§5.2).

**Views and browser instances**

| QtWebEngine | CEF | Notes |
|-------------|-----|-------|
| `QWebEngineView` (construction/`setPage`) | `CefBrowserHost::CreateBrowser` / `CreateBrowserSync` | Creates a browser on a `CefWindowInfo`/client; on OHOS the windowInfo's surface comes from the node manager |
| `view->page()` | `CefClient` | The client is the handler aggregator, ≈ the page |
| `setUrl` / `page->load(url)` | `browser->GetMainFrame()->LoadURL(url)` | Loads on the main frame |
| `setHtml` / `setContent` | `frame->LoadString(html, url)` | |
| `back/forward/stop` | `browser->GoBack/GoForward/StopLoading` | |
| `reload` | `browser->Reload` | |
| `runJavaScript(code)` | `frame->ExecuteJavaScript(code, url, callback)` | CEF can take a callback to get the return value; it fires on the CEF UI thread, so marshal it |
| `setDevToolsPage` / `inspect` | `browser->GetHost()->ShowDevTools(...)` | DevTools |

**Signals → handler callbacks (aggregated by `CefClient`)**

| The QWebEnginePage signal | The CEF handler method | Header |
|---------------------------|------------------------|--------|
| `urlChanged(url)` | `CefDisplayHandler::OnAddressChange(browser, frame, url)` | `cef_display_handler.h` |
| `titleChanged(title)` | `CefDisplayHandler::OnTitleChange(browser, title)` | same |
| `iconUrlChanged`/`iconChanged` | `CefDisplayHandler::OnFaviconURLChange(browser, icon_urls)` | same |
| `linkHovered(text)` | `CefDisplayHandler::OnStatusMessage(browser, value)` | same |
| `consoleMessage` | `CefDisplayHandler::OnConsoleMessage(...)` | same |
| `loadProgress(p)` | `CefDisplayHandler::OnLoadingProgressChange(browser, p)` | same |
| `loadStarted` | `CefLoadHandler::OnLoadStart` or `OnLoadingStateChange(isLoading=true)` | `cef_load_handler.h` |
| `loadFinished(ok)` | `CefLoadHandler::OnLoadEnd` / `OnLoadingStateChange(isLoading=false)` | same |
| `loadFailed` | `CefLoadHandler::OnLoadError(browser, frame, errorCode, errorText, failedUrl)` | same |
| `createWindow(type)` | `CefLifeSpanHandler::OnBeforePopup(...)` (return false to let CEF create it) | `cef_life_span_handler.h` |
| (closing) | `CefLifeSpanHandler::DoClose` / `OnBeforeClose` | same |
| `pdfPrintingFinished` | `CefPrintHandler` (libcef has an `ohos_print_manager`) | `cef_print_handler.h` |
| `featurePermissionRequested` | `CefPermissionHandler` / `CefPermissionRequest` | `cef_permission_handler.h` |

**Cookies / downloads / the JS bridge**

| QtWebEngine | CEF | Header / OHOS extension |
|-------------|-----|-------------------------|
| `QWebEngineProfile::cookieStore()` / `setCookie/getCookie/deleteCookie` | `CefCookieManager` (`VisitAllCookies`/`VisitUrlCookies`/`SetCookie`/`DeleteCookies`/`FlushStore`) | `cef_cookie.h`; the OHOS extensions `PutAcceptCookieEnabled`/`PutAcceptThirdPartyCookieEnabled` |
| `downloadRequested` | `CefDownloadHandler::OnBeforeDownload`/`OnDownloadUpdated` + `CefBeforeDownloadCallback::Continue(path)` | `cef_download_handler.h` |
| `QWebChannel`/`registerObject` (C++↔JS objects) | **CEF's built-in `CefClient` JS object binding** (`NotifyJavaScriptResult`/`HasJavaScriptObjectMethods`/`GetJavaScriptObjectMethods`/`RemoveTransientJavaScriptObject`) + `OnProcessMessageReceived` (IPC) / CEF's `MessageRouter` | `cef_client.h` |
| `QWebEngineUrlRequestInterceptor` | `CefRequestHandler::GetResourceRequestHandler` | `cef_request_handler.h` |

> **The iron rules where the models diverge (important, stable across versions)**:
> 1. **Threading**: every CEF callback runs on **CEF's UI thread**. Any callback that touches a Qt object (`QWidget`/a signal/a `QObject`) must marshal back to the Qt main thread — use CEF's `CefPostTask` to dispatch onto the CEF thread, and `QMetaObject::invokeMethod(obj, ..., Qt::QueuedConnection)` to get from the CEF thread back onto the Qt main thread. **Never touch a Qt object directly inside a CEF callback.**
> 2. **The event loop**: CEF has its own `CefRunMessageLoop` (on its own thread) and **doesn't integrate with Qt's `QEventLoop`**.
> 3. **Subprocesses**: CEF's subprocesses require you to export a subprocess entry point from your .so (§B), with `browser_subprocess_path` pointing at your .so — **the exact symbol name and the QPA dlsym contract vary by version, see §5.1/§5.2**.
> 4. **Window embedding**: `QWebEngineView` is a QWidget displayed directly; CEF's browser surface has to be attached to the ArkUI node tree through the node manager (§B) rather than reparented directly.

### 4.4 The migration step checklist (executable by an AI)

1. **Scan for WebEngine usage**: `grep -rnE 'QWebEngine(View|Page|Profile|CookieStore|UrlRequest|DownloadRequest|Settings|Script)' <src>`.
2. **Replace the classes per the §4.3 mapping table**: `QWebEngineView`→`CefBrowser`, `QWebEnginePage`→a `CefClient` subclass.
3. **Implement `CefClient` + the handlers**: follow the multiple-inheritance pattern in the component package's `tests/cefsimple/simple_handler.{h,cc}`, rewriting the signal slots as handler callbacks.
4. **Marshal across threads**: add `QMetaObject::invokeMethod(..., Qt::QueuedConnection)` back to the Qt main thread in every callback that touches a Qt object; use `CefPostTask` for Qt→CEF.
5. **Port the JS bridge**: `QWebChannel`/`registerObject` → CEF's `CefClient` JS object binding or the `MessageRouter`.
6. **Cookies/downloads/permissions**: `QWebEngineProfile`/`cookieStore`/`downloadRequested` → `CefCookieManager`/`CefDownloadHandler`/`CefPermissionHandler`.
7. **Rework the CMake**: `find_package(Qt<ver> WebEngineWidgets)` → `find_package(CEF)` + linking libcef.so/the wrapper/the adapter (§C).
8. **Deploy the .so files + the permissions + package the HAP** (§C).
9. **Verify**: page loading (`LoadURL`) / JS execution (`ExecuteJavaScript`) / navigation / popups (`OnBeforePopup`) / cookies / downloads / DevTools / thread marshalling with no crashes.

---

## 5. Adapting to a version upgrade (the core methodology — how to find the correct API after an upgrade)

> The version-sensitive parts (the ⚠️ items in the §0 table) vary with the Qt OHOS QPA / CEF component / glue layer version. After an upgrade, don't copy the API names from §B/§C — reread the authoritative sources as described in this section and find the correct API for your version.

### 5.1 The Qt OHOS SDK (not tied to a version: Qt 5.12 / 5.15 / Qt6 all work)

After your Qt OHOS SDK version changes, reread your SDK's QPA headers/templates to find these contracts:

| What to adapt | Where to find it (in your SDK) | Hints on the variants |
|---------------|--------------------------------|-----------------------|
| The Ability→Qt launch API | The SDK's `templates/EntryAbility.ets` + whatever entry point in `libqohos.d.ts`/`qohos*.h` "starts Qt from the Ability" | Qt5: something like `qpa.startQtApplication(this)`; Qt6: `harmonydeployqt6` generates a `QAbility` + libqohos.so's `handleAbilityOn*` |
| The `main` export contract for your .so | The `dlsym("main")` convention in the QPA source/headers + how your .so exports main as GLOBAL DEFAULT | Qt5: `add_library(SHARED)` + a hand-written `__attribute__((visibility("default")))`; Qt6: `qt_add_executable` does it automatically |
| The subprocess loading contract | The QPA's subprocess loading convention (which symbol it dlsyms) | See both the CEF side in §5.2 and the QPA side together |

> ⚠️ **A known QPA version break**: the `modulesFactories` (5.12 template) vs. `modules` (5.15 `libqohos.so`) API contract mismatch crashes the launch (a 5.12 template with a 5.15 libqohos crashes with "object has no property named 'modules'"). After upgrading or mixing SDKs, verify this contract (check that your SDK's `libqohos.d.ts` and its `templates` agree).

### 5.2 The CEF component (the version you downloaded/stripped)

After switching CEF component package versions (cef114 ↔ cef132 etc.), read the component package at your `CEF_ROOT`:

| What to adapt | Where to find it (in your CEF component) |
|---------------|------------------------------------------|
| Changed/added/removed APIs | Scan all of `$CEF_ROOT/include/` (`cef_client.h`/`cef_browser.h`/`cef_display_handler.h`/`cef_load_handler.h`/`cef_cookie.h`/`cef_download_handler.h`...) against the §4.3 mapping table |
| The OHOS extension methods | grep `$CEF_ROOT/include/` for `*_ohos.*` or OHOS-named methods (`NotifyJavaScriptResult`/`OnScaleChanged`/`PutAcceptCookieEnabled` etc.) — they may be added or removed between versions |
| The `browser_subprocess_path` mechanism + the subprocess entry point | `$CEF_ROOT/tests/cefsimple` + libcef's subprocess loading convention |
| The OHOS adapter `.so` name | The name of the CEF↔OHOS adaptation bridge .so in `$CEF_ROOT/libs/arm64-v8a/` |

> The principle: the CEF component package you downloaded/stripped is the truth for your CEF version. The API names in §3.2/§4.3 are a cef114 baseline snapshot — **your `$CEF_ROOT/include/` is authoritative**.

### 5.3 The glue layer (the native node manager + the ArkTS IoC)

After the glue layer (the CEF↔ArkTS↔Qt bridge, a separate project that's neither in the CEF component package nor in the Qt SDK) is upgraded, reread the glue layer repository itself:

| What to adapt | Where to find it (in your glue layer version) |
|---------------|-----------------------------------------------|
| ② The native node manager's API (the move/resize/focus/remove family) | The glue layer's native adapter headers (`.h`) |
| ③ The IoC container module + the binding API + the init parameters | The glue layer's ArkTS IoC module |
| The ArkTS cooperation layer (the napi bridge, the JS bindings) | The glue layer's ArkTS module |

> The principle: the glue layer is a separate project, and its API names/signatures/module names follow its own versioning. **The glue layer repository's headers/sources are always authoritative**; §B here only gives the "what to do / why".

### 5.4 The list of authoritative sources (where the correct API for your version lives)

| Side | The authoritative source | How to use it |
|------|--------------------------|---------------|
| CEF | The CEF component package you downloaded/stripped (`$CEF_ROOT`: `include/`, `cmake/`, `libcef_dll/`, `tests/cefsimple`) | `grep`/read the headers |
| The Qt OHOS QPA | Your Qt OHOS SDK (`libqohos.d.ts` / `qohos*.h` / `templates/EntryAbility.ets`) | `grep`/read the headers |
| The glue layer | The glue layer repository itself (the native adapter headers + the ArkTS IoC module) | Read that repository |
| The OHOS platform | The OHOS NDK + [[qt-harmonyos-platform-limits]] / [[qt-harmonyos-window-model]] | The platform mechanisms are stable |

> **In one line**: every API name on this page is a cef114 baseline snapshot. For the version-sensitive items (the ⚠️ rows in the §0 table), **the authoritative source for your version always wins**; this page gives you "what to do / why / where to look", not "copy this symbol name".

---

# Part 2 — A worked integration (version-neutral, given a CEF component package + your Qt OHOS SDK)

## A. Prerequisites (not tied to a version)

- You have a **CEF component package** (any version, obtained per §2) at `CEF_ROOT`.
- You have your **Qt OHOS SDK** (Qt 5.12 / 5.15 / Qt6, any of them) at `QT_SDK`.
- The glue layer follows §5.3 (your version).

## B. The five-layer glue integration (version-neutral, with the version-sensitive parts pointing at §5)

The five layers that embed CEF into a Qt HarmonyOS HAP. ① ② ③ are Qt-agnostic (the CEF engine/native/client layers); only ④ and ⑤ are the Qt integration surface.

| Layer | What it consists of | Depends on Qt? | How to handle it |
|-------|---------------------|:--------------:|------------------|
| **① The CEF engine layer** | libcef.so + libcef_dll_wrapper + the OHOS adapter .so + the dependency .so files | ❌ Pure C ABI | Reuse the component package's prebuilt artifacts; don't rebuild (§2.1) |
| **② The native ArkUI node manager** | A native adapter that organizes the parent/child, z-order and focus relationships of Qt's and CEF's XComponent surface nodes within one ArkUI node tree | ❌ Pure OHOS NDK | Implement it yourself (pattern below) |
| **③ The CEF client layer** | `CefClient` + the handler subclasses + your .so exporting the CEF subprocess entry point | ❌ Pure CEF API | Implement it yourself (follow §3.3 cefsimple) |
| **④ The Qt application window layer** | `QMainWindow`/`QWidget` forwarding resize/focus/close events to the CEF node | ✅ Basic Qt | Almost no changes (for Qt6 compatibility see §5.1) |
| **⑤ The ArkTS Ability/launch layer** | A `UIAbility` that launches Qt + IoC container initialization binding the CEF adapter services | ✅ Coupled to launching Qt | The main thing you have to change |

### B.1 ② The native ArkUI node manager (the core pattern)

HarmonyOS has no traditional `SetParent` reparenting (surfaces are organized by the ArkUI node tree). Write a native adapter (with the OHOS NDK):

- **The invariants (stable across versions)**: within a single ArkUI node tree, establish the parent/child, z-order and focus ownership of Qt's and CEF's respective XComponent surface nodes (use a marker to distinguish which node belongs to whom, e.g. "QT"/"CEF"); expose move/resize/focus/remove operations to the Qt window layer; the Qt `QMainWindow` calls those operations from `resizeEvent`/`focusInEvent`/`closeEvent` to keep the CEF node in sync.
- **`[version-sensitive]`**: the node manager's method names/signatures vary with the glue layer version. **For the exact method names in your version, read your glue layer's native adapter headers (§5.3)** — don't copy any specific name from this page.

> Background: OHOS rendering goes through XComponent + the ArkUI node tree; see [[qt-harmonyos-window-model]]. The Qt HarmonyOS QPA is itself XComponent-based, which is why Qt's and CEF's surfaces can be organized in the same node tree.

### B.2 ③ The CEF client layer + the subprocess entry point

- Implement your own `CefClient` subclass (aggregating the handlers you need, following the `SimpleHandler` multiple-inheritance style in §3.3).
- **The invariant**: CEF spawns subprocesses (render, GPU, etc.); the desktop version calls `CefExecuteProcess` in the subprocess's main. OHOS HAPs load subprocesses differently — `settings.browser_subprocess_path` points at your .so, the OHOS loader dlsyms the subprocess entry symbol that .so exports, and that entry calls `CefExecuteProcess`.
- **`[version-sensitive]`**: the subprocess entry symbol name your .so exports and the QPA dlsym contract vary with the Qt OHOS QPA + CEF version. **Read your Qt OHOS QPA's subprocess loading convention + your CEF component's `browser_subprocess_path` mechanism (§5.1/§5.2)** — don't copy.
- **CEF's own thread**: `CefInitialize` + `CefRunMessageLoop` run on a (detached) thread, separate from the Qt main thread's event loop (§3.5, stable).

### B.3 ⑤ The ArkTS Ability + IoC initialization

- **The invariant**: a `UIAbility` launches the Qt application; CEF's ArkTS cooperation layer (the adapter napi bridge, the JS bindings etc.) uses an IoC container to bind the services the CEF adapter needs early in the Ability's startup, or the client layer crashes with "no binding" when it fetches those services in `onCreate`; it also calls the node manager's initialization function.
- **`[version-sensitive]`**: the IoC container module name + the binding API + the init parameters vary with the glue layer version; the Ability→Qt launch API varies with the Qt OHOS QPA version. **For the former read the glue layer's ArkTS IoC module (§5.3); for the latter read the Qt OHOS SDK (§5.1, Qt5's `qpa.startQtApplication` / Qt6's `harmonydeployqt6` + `QAbility`)**.

> §B's literal implementation is a detail of a specific project version — **the authoritative source for your version (§5.4) wins**; this page stops at the invariants + "where to look".

## C. The build process (version-neutral; the Qt5/Qt6 CMake variants are examples, not a commitment)

> Paths use ENV variable placeholders (the real values live in your local `ENV.local.md`): the CEF component package `CEF_ROOT`, the Qt OHOS SDK `QT_SDK` (any of Qt 5.12/5.15/Qt6), the OHOS NDK `${OHOS_SDK_NATIVE}`, DevEco `${DEVECO_PATH}`.

### C.1 Environment

```bash
export DEVECO_PATH=<DevEco>
export OHOS_SDK_NATIVE=$DEVECO_PATH/sdk/default/openharmony/native
export CEF_ROOT=<the path to your CEF component package>   # obtained per §2, any version
export QT_SDK=<your Qt OHOS SDK>                            # any of Qt 5.12/5.15/Qt6
export PATH="$DEVECO_PATH/jbr/bin:$DEVECO_PATH/tools/node/bin:$DEVECO_PATH/tools/hvigor/bin:$DEVECO_PATH/tools/ohpm/bin:$PATH"
HDC=$OHOS_SDK_NATIVE/../toolchains/hdc.exe
```

### C.2 Your CMake (two variants, Qt5 / Qt6 — pick the one you use; not a commitment)

```cmake
cmake_minimum_required(VERSION 3.19)          # CEF requires ≥3.19
project(QtCefOhosDemo)
set(CMAKE_AUTOMOC ON); set(CMAKE_AUTOUIC ON); set(CMAKE_AUTORCC ON)

# --- The CEF component package (a pattern stable across versions) ---
set(CEF_ROOT "$ENV{CEF_ROOT}" CACHE PATH "")
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CEF_ROOT}/cmake")
find_package(CEF REQUIRED)
add_subdirectory(${CEF_ROOT}/libcef_dll libcef_dll_wrapper)   # build libcef_dll_wrapper (Qt-agnostic)

# --- The OHOS system libraries ---
find_library(native-window-lib native_window)
find_library(hilog-lib hilog_ndk.z)
find_library(ace-napi-lib ace_napi.z)
find_library(ace-ndk-lib ace_ndk.z)

# --- ② The native node manager (§B.1, Qt-agnostic) ---
add_library(node_adapter SHARED node_adapter.cpp)
target_link_libraries(node_adapter PUBLIC ${hilog-lib} ${ace-napi-lib} ${ace-ndk-lib})

# --- Your .so: pick either Qt5 or Qt6 (whichever you use); not a commitment ---
# ▶ The Qt5 variant:
#   find_package(Qt5 REQUIRED COMPONENTS Core Widgets)
#   add_library(qtmodule SHARED main.cpp mainwindow/mainwindow.cpp
#       cefclient/my_client.cpp cefclient/my_display_handler.cpp
#       cefclient/my_lifespan_handler.cpp cefclient/my_load_handler.cpp)
#   # [version-sensitive] The Qt5 OHOS QPA: hand-write main + the subprocess entry with __attribute__((visibility("default"))) for the QPA to dlsym (§5.1)
# ▶ The Qt6 variant:
#   find_package(Qt6 REQUIRED COMPONENTS Core Widgets)
#   qt_add_executable(qtmodule main.cpp mainwindow/mainwindow.cpp
#       cefclient/my_client.cpp cefclient/my_display_handler.cpp
#       cefclient/my_lifespan_handler.cpp cefclient/my_load_handler.cpp)
#   # Qt6: qt_add_executable produces a MODULE .so + main GLOBAL DEFAULT + the deployment json + the bundled Qt6 ets automatically (§5.1)

target_link_libraries(qtmodule PRIVATE
    Qt::Core Qt::Widgets
    node_adapter
    ${CEF_ROOT}/libs/arm64-v8a/libcef.so          # reuse the component package's prebuilt engine (pure C ABI)
    libcef_dll_wrapper                             # rebuilt (Qt-agnostic)
    ${CEF_ROOT}/libs/arm64-v8a/<the OHOS adapter .so> # [version-sensitive] the name varies with the CEF component version, see §5.2
    ${native-window-lib} ${hilog-lib} ${ace-napi-lib} ${ace-ndk-lib})
```

> `[version-sensitive]`: Qt5's `add_library` + hand-written main/subprocess entry vs. Qt6's `qt_add_executable` (automatic main + `harmonydeployqt6` generating the Qt6 template's `QAbility` + `libqohos.so`) — **see §5.1 for the exact contract in your Qt version** ([[qt-harmonyos-qt6-status]] covers the Qt6 differences in detail). The CEF engine layer (libcef.so/the wrapper/the adapter) is Qt-agnostic and reusable across Qt versions.

### C.3 Build + deploy the CEF .so files + permissions + package the HAP (mechanisms stable across versions)

```bash
# Build your .so
mkdir build && cd build && cmake -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=$OHOS_SDK_NATIVE/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a -DCMAKE_PREFIX_PATH=$QT_SDK -DCEF_ROOT=$CEF_ROOT ../ && cmake --build . -j8

# Deploy the CEF .so files into the HAP (hvigorw only picks up entry/libs/<abi>/ + the Qt libraries, not .so files CMake linked by absolute path, so copy them by hand)
cp "$CEF_ROOT"/libs/arm64-v8a/libcef.so "$CEF_ROOT"/libs/arm64-v8a/<the OHOS adapter .so> entry/libs/arm64-v8a/  # [version-sensitive] for the adapter name see §5.2
# ★ Deploy CEF's dependency chain too (libcef.so's DT_NEEDED):
cp "$CEF_ROOT"/libs/arm64-v8a/libicudata.so "$CEF_ROOT"/libs/arm64-v8a/libicui18n.so "$CEF_ROOT"/libs/arm64-v8a/libicuuc.so entry/libs/arm64-v8a/
cp "$CEF_ROOT"/libs/arm64-v8a/libfreetype.so "$CEF_ROOT"/libs/arm64-v8a/libfontconfig.so "$CEF_ROOT"/libs/arm64-v8a/libexpat.so entry/libs/arm64-v8a/
cp "$CEF_ROOT"/libs/arm64-v8a/libbrotlicommon.so "$CEF_ROOT"/libs/arm64-v8a/libbrotlidec.so "$CEF_ROOT"/libs/arm64-v8a/libbrotlienc.so entry/libs/arm64-v8a/
cp "$CEF_ROOT"/libs/arm64-v8a/libjpeg.so "$CEF_ROOT"/libs/arm64-v8a/libpng.so entry/libs/arm64-v8a/
cp build/libqtmodule.so build/libnode_adapter.so entry/libs/arm64-v8a/
# Use llvm-readelf -d to verify every .so's NEEDED entries are bare names (no absolute Windows path prefixes)

# The ArkTS Ability + IoC initialization (§B.3; for the version-sensitive APIs see §5.1/§5.3) + the CEF permissions:
# Add INTERNET/GET_NETWORK_INFO to requestPermissions in entry/src/main/module.json5, with reason+usedScene for user_grant permissions
#   (LOCATION/CAMERA/MICROPHONE must have reason+usedScene or you get error 00303218 — see [[qt-harmonyos-platform-limits]])

# Package the HAP + install + launch
hvigorw assembleHap --mode module -p product=default --no-daemon
"$HDC" install -r entry/build/default/outputs/default/entry-default-signed.hap
"$HDC" shell "aa start -b <bundleName> -a EntryAbility"
"$HDC" shell "hilog 2>/dev/null | grep -iE 'cef|libcef|chromium|inject|qtmodule'"
```

> libcef.so is heavy (~160 MB+) and the HAP is large (~250 MB+). For deploying heavyweight .so files and handling the DT_NEEDED dependency chain see [[qt-harmonyos-third-party-libs]]. For the full DevEco/hvigorw flow see [[qt-harmonyos-build-run-workflow]].

## D. The pitfall list (marked stable / version-sensitive)

| # | Pitfall | Symptom | Fix | Nature |
|---|---------|---------|-----|:------:|
| 1 | The CEF .so files aren't packaged into the HAP | `dlopen(libcef.so) failed` at runtime | Manually copy libcef.so + its dependencies into `entry/libs/arm64-v8a/` (§C.3) | Stable |
| 2 | CEF's dependency chain is incomplete | `dlopen(libcef.so) → libicui18n/libfreetype/... not found` | Deploy the dependencies (icu/freetype/fontconfig/expat/brotli/jpeg/png) too; check completeness with `llvm-readelf -d` | Stable |
| 3 | `find_package(CEF)` fails | `Must specify a CEF_ROOT value` | Set `CEF_ROOT` before `find_package(CEF)` (§3.4/§C.2) | Stable |
| 4 | Touching Qt objects directly inside a CEF callback | Occasional crashes / data races | Marshal back to the Qt main thread: `QMetaObject::invokeMethod(..., Qt::QueuedConnection)` (§4.3 divergence 1) | Stable |
| 5 | Driving CEF with a QEventLoop | Deadlocks / doesn't work | CEF has its own `CefRunMessageLoop` (on its own thread) and doesn't integrate with the Qt event loop (§3.5) | Stable |
| 6 | A user_grant permission with no reason | `00303218 reason and usedScene mandatory` | Give LOCATION/CAMERA/MICROPHONE a `reason` + `usedScene` ([[qt-harmonyos-platform-limits]]) | Stable |
| 7 | A mismatched `browser_subprocess_path` | The CEF subprocess fails to load | Point it at your .so and export the subprocess entry point (§B.2); **the symbol name and contract vary by version, see §5.1/§5.2** | Version-sensitive |
| 8 | A QPA contract mismatch crashes the launch | `object has no property named 'modules'` and similar | Align the SDK template with libqohos.so's contract (`modulesFactories` vs. `modules`, see §5.1) | Version-sensitive |
| 9 | QPA leftovers (mixing old ets / a cross-version QPA) | `Error loading libQt5Gui.so (needed by libplugins_platforms_qopenharmony.so)` | Launch with the right version of the Qt OHOS QPA; when deploying the CEF libraries, don't accidentally copy a cross-version QPA | Version-sensitive |

## E. An AI-executable end-to-end checklist

> An AI following this page can get the whole Qt + CEF HarmonyOS integration working (not tied to a Qt/CEF version; first find the correct API for your version per §5):

- [ ] **Get the CEF component package**: download it from the maintainer's location (§2.3 option A) or strip it out of chromium_cef per §2.2; point `CEF_ROOT` at it; verify it contains `include/` + `cmake/` + `libcef_dll/` + `libcef.so` + the OHOS adapter.
- [ ] **Environment**: `CEF_ROOT`, the Qt OHOS SDK `QT_SDK` (any of Qt 5.12/5.15/Qt6), the OHOS NDK `${OHOS_SDK_NATIVE}` and DevEco `${DEVECO_PATH}` are ready.
- [ ] **§5 version adaptation**: read the authoritative sources for your version per §5.1/§5.2/§5.3 to find the Ability→Qt launch API / the main contract / the subprocess entry symbol / the node manager API / the IoC module / the OHOS adapter .so name.
- [ ] **CMake** (§C.2): `find_package(CEF)` + `CEF_ROOT` + `add_subdirectory(libcef_dll)` + your .so linking libcef.so/the wrapper/the adapter + node_adapter (pick the Qt5 or Qt6 variant you use).
- [ ] **The five architectural layers** (§B): ① reuse the component package's libcef.so ② implement the node manager (API per §5.3) ③ implement CefClient + the handlers and export the subprocess entry (symbol per §5.1/§5.2) ④ forward the Qt window events ⑤ the ArkTS Ability + IoC (the launch API per §5.1, the IoC per §5.3).
- [ ] **Build**: your .so + node_adapter.so + libcef_dll_wrapper are produced and link successfully.
- [ ] **Deploy the .so files**: libcef.so + the adapter + the dependency chain + your .so go into `entry/libs/arm64-v8a/`; `llvm-readelf -d` shows every NEEDED entry is a bare name (§C.3).
- [ ] **Permissions**: INTERNET/GET_NETWORK_INFO + reason + usedScene for the user_grant permissions.
- [ ] **Package the HAP + install + launch**: `hvigorw assembleHap` → signed.hap → `hdc install` → `aa start` → CEF starting up visible in hilog.
- [ ] **The WebEngine migration** (if you're porting an existing application): follow the nine steps in §4.4, replacing each kind of usage per the §4.3 mapping table and adding the marshalling.

---

## Related context

- [[qt-harmonyos-modules]] — The HarmonyOS porting status of the Qt modules (WebEngine out of scope / WebView ✅, the basis for choosing a migration target)
- [[qt-harmonyos-window-model]] — The window model (XComponent/the ArkUI node tree, explaining why §B.1's node manager doesn't use traditional reparenting)
- [[qt-harmonyos-third-party-libs]] — Third-party library cross-compilation and .so deployment (handling the dependency chain of CEF as a heavyweight prebuilt .so)
- [[qt-harmonyos-build-run-workflow]] — The full build-and-run flow, DevEco/hvigorw/hdc
- [[qt-harmonyos-platform-limits]] — Platform limitations (permissions / the user_grant reason etc.)
- [[qt-harmonyos-api-mapping]] — The API replacement methodology (this page's §4 is one specific application of it: WebEngine→CEF)
- [[qt-harmonyos-qt6-status]] — The Qt6 HarmonyOS status and the Qt5→Qt6 differences (§5.1's upgrade path, Qt6's `qt_add_executable` + `harmonydeployqt6`)
- [[procedural-demo-generation]] — The demo generation flow (the process framework for this page's §E checklist)

## Results summary

| Field | Content |
|-------|---------|
| Leadership summary | Fills the gap left by Qt on HarmonyOS having no WebEngine-class web engine: building on Huawei's official open-source CEF for OpenHarmony, it captures a Qt + CEF development guide + the WebEngine→CEF API mapping and migration steps; **not tied to a Qt version, with CEF distributed as a de-versioned component package** (stripping / downloading / version-neutral integration) + §5's version-upgrade adaptation methodology, so migrations go faster, developer questions get answered, and upgrades don't leave you stranded |
| Impact | Faster migration (porting WebEngine applications), framework support (CEF as the WebEngine replacement), commercial responses, developer guidance (publicly shareable) |
| Deliverables | The development guide page, the WebEngine→CEF migration plan, the API mapping table, **the CEF component package stripping method**, **the version-upgrade adaptation methodology**, the AI end-to-end checklist |
| Evidence | Verification of the chromium_cef 114 release branch source structure (41 OHOS adaptation files in libcef + tests/cefsimple + cmake/FindCEF + the include API headers), Huawei guidebook solution6 §5 |
| How to reuse it | Whenever a "port a WebEngine application to HarmonyOS" / "Qt on HarmonyOS needs a web engine" / "CEF integration" request comes in, load this page and run the §E checklist; **after upgrading Qt/CEF/the glue layer, read §5 to find the correct API before touching anything** |
