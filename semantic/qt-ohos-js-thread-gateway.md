---
id: semantic-qt-ohos-js-thread-gateway
type: semantic
domain: tech
tags: [qt, harmonyos, ohos, qpa, threading, node-api, arkts, napi, private-api, oauth, sync]
created: 2026-06-26
updated: 2026-07-27
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-ohos-extras, problem-ohos-mainthread-mismatch, semantic-qt-harmonyos-qt6-status, episodic-quit-deadlock-tsfn]
summary: >
  The private API for bridging Qt and ArkTS/JS threads: the QOhosJsThreadGateway namespace (invoke/runAndWait/eval/
  evalWithPromise/invokeAndWaitForContinue) is the entry point for safely marshalling calls from Qt threads onto the single JS main thread,
  and QOhosJsThreadOps is the abstract interface behind it (the QPA plugin registers a JsThreadOpsImpl implementation). It lives in QtCore's private header
  qcore_ohos_p.h and is not public API. Developers use the namespace's free functions and don't touch QOhosJsThreadOps directly.
---

# Bridging Qt and JS threads: QOhosJsThreadGateway / QOhosJsThreadOps

## Background: why this interface exists

Qt for HarmonyOS uses a **dual-thread model** (see [[ohos-mainthread-mismatch]] for details):

| Thread | Purpose |
|--------|---------|
| The ArkTS UI thread (the JS thread) | Runs ArkTS lifecycle callbacks and Node-API callbacks, and holds the `napi_env` |
| QtMainThread | Runs the Qt event loop, the user's `main()`, and QPA event dispatch |

**The core constraint**: Node-API objects (`napi_value` / `napi_ref` / `QNapi::Value`) **can only be accessed on the JS main thread**. So whenever a Qt thread needs to call any ArkTS/system API (getting font paths, wifi, standard paths, calling an `@ohos.*` module, and so on), the call must be marshalled onto the JS thread. `QOhosJsThreadGateway` is the entry point for that direction; for the reverse direction (JS thread → Qt thread), use `QtOhos::invokeInQtThread`.

## How the two relate (verified in the source)

| | `QOhosJsThreadGateway` | `QOhosJsThreadOps` |
|---|---|---|
| Nature | A **namespace** (a façade of free functions) | An **abstract class** (a virtual interface + a `static instance()/registerInstance()` singleton) |
| Defined in | `qtbase/src/corelib/kernel/qcore_ohos.cpp:36-54` | `qtbase/src/corelib/kernel/qcore_ohos.cpp:19-34` |
| Header | `QtCore/private/qcore_ohos_p.h` | Same |
| Who uses it | **Callers** (developers / Qt modules) | **Implementers** (the OHOS QPA plugin) |

The delegation chain (the namespace functions are a thin façade that forwards to the singleton):

```cpp
// qcore_ohos.cpp
void QOhosJsThreadGateway::runAndWait(
    const std::function<void(QOhosJsState &)> &task, std::string callerContextName)
{
    QOhosJsThreadOps::instance().runAndWait(task, std::move(callerContextName));
}
// invoke / invokeAndWaitForContinue forward to instance() the same way
```

The backend implementation is the OHOS QPA plugin's `JsThreadOpsImpl` (`qtbase/src/plugins/platforms/ohos/qohosplugincore.cpp:780-821`), registered as the singleton at startup by `initJsThreadState()` via `QOhosJsThreadOps::registerInstance(&jsThreadOpsImpl)` (:920), which internally forwards to the real task-queueing functions `QtOhos::runInJsThreadAndWait / invokeInJsThread / invokeInJsThreadAndWaitForContinue`.

**Conclusion**: developers use the `QOhosJsThreadGateway::*` free functions; `QOhosJsThreadOps` is the interface for "someone replacing the backend implementation" — don't call `instance().xxx()` directly. `runAndWait` exists on both sides, so application/module code should always use the namespace version.

## ⚠️ The private API boundary

- Both live in `QtCore/private/qcore_ohos_p.h`, whose header comment states explicitly that it is **"not part of the Qt API. It may change from version to version without notice, or even be removed."**
- The symbols are exported from QtCore via `Q_CORE_EXPORT` and are linkable, but come with **no ABI/API compatibility guarantee**
- Qt itself uses them widely in internal modules: the font database (`qohosplatformfontdatabase.cpp`), QStandardPaths (`qstandardpaths_ohos.cpp`), the wifi bearer (`qohoswifi.cpp`), and the QPA plugin itself
- To use them from the application layer you need `#include <QtCore/private/qcore_ohos_p.h>`, to link the Qt private headers (CMake `Qt5::CorePrivate` / `find_package(Qt5 ... COMPONENTS ... Private)`), and to accept the upgrade risk yourself

## ⚠️ Build prerequisites (easy to miss; every example here hits them)

Every example on this page (and any TU that names `QNapi::*` types directly) **must** satisfy two things beyond `Qt5::CorePrivate`, or compilation/linking fails (verified 2026-07-27 against a Qt 5.15.16 full SDK installation tree):

1. **node-addon-api's `napi.h`**: `qcore_ohos_p.h` → `qnapi_p.h:24 #include <napi.h>`. The 5.15.16 full SDK **doesn't ship** `napi.h` (a whole-tree `find` gives 0 matches); the `Qt5::CorePrivate` target only carries `Qt5Core_OWN_PRIVATE_INCLUDE_DIRS` (the private header directories) and **not** the node-addon-api path (`Qt5CoreConfigExtras.cmake` has no `3rdparty`/`node-addon` entries). You must take it from the Qt5 source tree's `qtbase/src/3rdparty/node-addon-api/` and add it by hand with `target_include_directories(<tgt> PRIVATE <path>/node-addon-api)`, or via a `QT5_SRC_3RDPARTY` environment variable.
2. **Linking `ace_napi.z`**: node-addon-api is a header-only inline wrapper, and the `napi_*` C functions are provided by the OHOS runtime's `libace_napi.z.so` (in the sysroot at `<OHOS_SDK_NATIVE>/sysroot/usr/lib/aarch64-linux-ohos/libace_napi.z.so`). `Qt5::Core` **doesn't propagate** this dependency (`Qt5CoreConfigExtras.cmake` has no `INTERFACE_LINK_LIBRARIES` containing ace_napi), so the application must add `ace_napi.z` explicitly to `target_link_libraries` or you get `undefined reference to napi_*`.

> 💡 Even if your application code never uses `QNapi::*` types and only calls `jsState.eval<T>(expr)` for POD return values, napi.h is still transitively included by `qcore_ohos_p.h` (unavoidable); and linking ace_napi.z is required by any TU that uses this gateway.

## The current way to get the main window / a window id (5.15.16, easy to get wrong)

- **The main window**: `jsState.defaultWindowStageOrEmpty().call<QNapi::Object>("getMainWindowSync")` (synchronous; `@ohos.window.d.ts`'s `WindowStage.getMainWindowSync(): Window`; the source does the same at `qohosqabilityinstancesmanager.cpp:312` / `qohoswindowproxydatafactory.cpp:267`).
- **Accessing the window id**: `window.get<QNapi::Number>("getWindowProperties().id")`, **not** `.get<QNapi::Number>("id")` — in 5.15.16, `id` isn't a direct property of the Window object and must go through `getWindowProperties().id` (source: `qohoswindowproxy.cpp:489/518`).
- **Enumerating subwindows**: `windowStage.call<QNapi::Promise>("getSubWindow")` takes **no arguments** and returns `Promise<Array<Window>>` (`@ohos.window.d.ts:8480`); match by `getWindowProperties().id` inside `onThen`. **Don't** pass an id argument to `getSubWindow` (older code that did was simply ignored).
- **A GC warning**: `getSubWindow` is asynchronous and `onThen` runs in a different JS turn. Any `QNapi::Object` you need in there (a policy object, say) **must be constructed inside that callback using `info.Env()`** rather than captured by value from the outer task — a non-persistent `napi_value` gets garbage-collected across turns. The synchronous path (e.g. calling `call` right after `getMainWindowSync`) doesn't have this problem.

## The 5 entry points (all in the `QOhosJsThreadGateway` namespace)

| Scenario | Interface | Blocking | Returns a value |
|---|---|:---:|:---:|
| Post asynchronously, no result needed | `invoke(task)` | No | No |
| Block synchronously, no result needed | `runAndWait(task, ctx)` | Yes | No |
| Block synchronously and get a value | `eval(func, ctx)` (a template that deduces the return type) | Yes | Yes |
| JS returns a Promise; block for the side effect | `invokeAndWaitForContinue(task, ctx)` | Yes | No |
| JS returns a Promise; block and get the value | `evalWithPromise<T>(func, ctx)` | Yes | `T` |

`ctx` (`callerContextName`) is for error localization; the convention is to pass `Q_FUNC_INFO`.

### Usage examples (mirroring Qt's own implementations)

```cpp
#include <QtCore/private/qcore_ohos_p.h>

// 1) Asynchronous fire-and-forget
QOhosJsThreadGateway::invoke([](QOhosJsState &) {
    // do something on the JS thread whose result you don't need
});

// 2) Synchronous, blocking, no return value (the pattern Qt's font database uses for font paths)
QStringList fontPaths;
QOhosJsThreadGateway::runAndWait(
    [&](QOhosJsState &jsState) {
        fontPaths.append(getSystemFontPaths(jsState)); // must be fetched on the JS thread
    }, Q_FUNC_INFO);

// 3) Synchronous, blocking, with a return value (the most common; the QStandardPaths/wifi pattern)
QString family = QOhosJsThreadGateway::eval(
    [&](QOhosJsState &jsState) {
        return QString::fromStdString(getDefaultFontFamily(jsState));
    });

// 4) The JS side returns a Promise; block and get the value (the wifi getLinkedInfo pattern)
auto linked = QOhosJsThreadGateway::evalWithPromise<QOhosOptional<WifiLinkedInfo>>(
    [&](QOhosJsState &jsState, QOhosTaskPromise<QOhosOptional<WifiLinkedInfo>> p) {
        auto branches = std::move(p).makeThenCatchBranches(Q_FUNC_INFO);
        jsState.evalToPromiseOrRejectOnThrow("@ohos.wifiManager.getLinkedInfo()")
            .then(std::move(branches.thenFunc))
            .catch(std::move(branches.catchFunc));
    });

// 5) The JS side returns a Promise; you only want the side effect, not the value
QOhosJsThreadGateway::invokeAndWaitForContinue(
    [&](QOhosJsState &jsState, QOhosTaskPromise<> done) {
        jsState.evalToPromiseOrRejectOnThrow("doSomethingAsync()")
            .then([done]() { done(); })
            .catch([done](QNapi::Value) { done(); });
    }, Q_FUNC_INFO);
```

The `QOhosJsState &` the task receives provides:
- `env()` — the `napi_env`
- `eval(expr, args)` — evaluate a JS expression, with a templated return type
- `evalToPromiseOrRejectOnThrow(expr, args)` — get a `QNapi::Promise`
- `defaultWindowStageOrEmpty()` / `defaultUiContextOrEmpty()` — ArkUI objects
- `mapOhosEnumToJs / mapOhosEnumFromJs / tryMapOhosEnumFromJs` — bidirectional HarmonyOS enum mapping

## A key constraint

`eval` / `evalWithPromise` contain a `static_assert`: **the return type must not be a NAPI value** such as `napi_value` / `napi_ref` / `QNapi::Value` — you must convert to an ordinary C++ type on the JS thread (`std::string` / `int` / `bool` / `std::vector` / `QOhosOptional<T>` and so on) before returning. Violations are caught at compile time. That's why Qt's wifi proxy returns `std::vector<ScanInfo>` / `QOhosOptional<WifiLinkedInfo>` rather than NAPI objects.

## The reverse direction (JS thread → Qt thread)

The same file `qcore_ohos_p.h` also provides the reverse-direction tools, completing the cross-thread picture:

- `QtOhos::invokeInQtThread(task)` — callable from any thread; queues the task for execution on the Qt thread (this is what "ArkTS UI thread callbacks can't use Qt APIs directly" in [[ohos-mainthread-mismatch]] refers to)
- `QtOhos::QThreadSafeRef<T>::visitInQtThreadIfAlive(func)` / `QObjectThreadSafeRef` — a thread-safe reference to a QObject that internally uses `QPointer` to check liveness before accessing it on the Qt thread
- `QtOhos::makeProxyWithJsThreadDeleter(shared_ptr)` — wraps a shared_ptr with a custom deleter so the managed object is destroyed on the JS thread (implemented internally with `QOhosJsThreadGateway::runAndWait`)
- `QtOhos::initQtThreadState(qpaFunctions)` — called once from the Qt thread at startup to initialize the `QtState`

## Decision table

| What I want to do | Which to use |
|---|---|
| Any Qt thread → the JS thread, asynchronously, no result | `QOhosJsThreadGateway::invoke` |
| Any Qt thread → the JS thread, blocking, no return value | `QOhosJsThreadGateway::runAndWait` |
| Any Qt thread → the JS thread, blocking, with a return value | `QOhosJsThreadGateway::eval` |
| Any Qt thread → calling a JS-thread API that returns a Promise, blocking for the value | `QOhosJsThreadGateway::evalWithPromise<T>` |
| The same, but only for the side effect | `QOhosJsThreadGateway::invokeAndWaitForContinue` |
| The JS thread (inside a NAPI callback) → the Qt thread | `QtOhos::invokeInQtThread` |
| Holding a QObject reference across threads and accessing it safely | `QtOhos::QThreadSafeRef<T>` |

## Use case: synchronizing an asynchronous Ability result (the OAuth scenario)

`startAbilityForResult` has **no sync variant** in the OHOS SDK (grepping the whole `interface_sdk-js` tree gives 0 matches), and the Stage `UIAbility` has no `onAbilityResult` lifecycle override; `QtOhosExtras` **does have** `startAbilityForResult` (asynchronous, returning a `requestId` with the result delivered through the `startAbilityForResultResponseReceived` signal), but **no synchronous blocking variant** ([[qt-ohos-extras]]). To wait synchronously for a result on the Qt side (an OAuth authorization code, a picker result, and so on), use `evalWithPromise<T>` on a **worker thread** to block until the ArkTS Promise resolves:

```cpp
// On a worker thread (never call this from the GUI thread)
QString code = QOhosJsThreadGateway::evalWithPromise<QString>(
    [&](QOhosJsState &js, QOhosTaskPromise<QString> p) {
        auto br = std::move(p).makeThenCatchBranches(Q_FUNC_INFO);
        js.evalToPromiseOrRejectOnThrow("globalThis.__qtStartOAuthForResult('...')")
          .then(std::move(br.thenFunc))
          .catch(std::move(br.catchFunc));
    });
```

**Three hard constraints**:

1. **It must be a worker thread**: `evalWithPromise` genuinely blocks on `std::future::wait()` internally, so calling it from the GUI thread freezes the UI and triggers appfreeze; calling it from the JS main thread means the tsfn callback never fires and you deadlock ([[ohos-mainthread-mismatch]]).
2. **Exposing the context**: `startAbilityForResult` is a `UIAbilityContext` instance method that the eval context can't reach — the calling host Ability must first register a global helper (such as `globalThis.__qtStartOAuthForResult = async (wantJson) => await ctx.startAbilityForResult(...)`), or, where `globalThis` is restricted under pure ArkTS NEXT, inject it through a NAPI tsfn callback (holding a function reference with `napi_create_reference`). `evalWithPromise` works out of the box for module-level calls (`@ohos.wifiManager.getLinkedInfo()`), but you must expose the symbol yourself for instance methods.
3. **A timeout fallback**: during OAuth the host Ability isn't destroyed and the tsfn pumps normally — but never depend on the tsfn on the exit path. [[quit-deadlock-tsfn]] proves that the ArkTS runtime doesn't pump tsfn callbacks during Ability destruction, so the Promise never settles and the blocking call hangs for ~2 minutes. `wait_for(timeout)` + `std::make_shared<std::promise<T>>` (to avoid broken_promise) are mandatory. OHOS musl has no `pthread_cancel`, so a blocking call can't be forcibly interrupted.

**An alternative**: if you're porting an existing synchronous `doOAuth()` and don't want to bind to Qt's private API, hand-write a NAPI tsfn + `std::promise<QString>` + a requestCode-keyed `OAuthStore` singleton, and `wait_for` on a worker thread the same way. **Don't use a nested `QEventLoop`** to make async look synchronous: on OHOS that means mid-wait reentrancy plus relying on the JS thread to pump the tsfn — fragile. Qt's own gateway deliberately uses `std::promise::wait()` rather than a nested loop.

## Source references (Qt 5.15.16 / tqtc/harmonyos-5.15.16)

| File | Lines | Description |
|------|-------|-------------|
| `qtbase/src/corelib/kernel/qcore_ohos_p.h` | 51-167 | The declarations of `QOhosJsState` / the `QOhosJsThreadGateway` namespace / `QOhosJsThreadOps` |
| `qtbase/src/corelib/kernel/qcore_ohos.cpp` | 19-54 | The `QOhosJsThreadOps` singleton + the `QOhosJsThreadGateway` façade forwarding |
| `qtbase/src/plugins/platforms/ohos/qohosplugincore.cpp` | 780-821, 920 | The `JsThreadOpsImpl` implementation + `registerInstance` |
| `qtbase/src/platformsupport/fontdatabases/ohos/qohosplatformfontdatabase.cpp` | 86, 169, 235 | Real-world uses of `evalWithPromise` / `runAndWait` / `eval` |
| `qtbase/src/corelib/io/qstandardpaths_ohos.cpp` | 22 | A real-world use of `eval` |
| `qtbase/src/plugins/bearer/ohos/src/ohosinterfaces/qohoswifi.cpp` | 90, 144, 187, 271, 285, 310, 332, 348 | Many real-world uses of `eval` / `evalWithPromise` |

## References

This page is verified against the Qt 5.15.16 source (tqtc/harmonyos-5.15.16, commit 962aa625) rather than distilled from external documentation — this is Qt private API with no official external documentation.

| Source | Notes |
|--------|-------|
| 🛠️ Qt source | `qtbase/src/corelib/kernel/qcore_ohos.{cpp,p.h}` — the gateway and interface declarations/implementations |
| 🛠️ Qt source | `qtbase/src/plugins/platforms/ohos/qohosplugincore.cpp` — the `JsThreadOpsImpl` backend implementation |
| 🛠️ Qt source | `qohosplatformfontdatabase.cpp` / `qstandardpaths_ohos.cpp` / `qohoswifi.cpp` — real-world usage references |
| 📦 Installed headers | `<LOCAL_PATH>` |

## Related context

- [[qt-harmonyos-overview]] — An overview of the QPA plugin architecture
- [[qt-ohos-extras]] — The public HarmonyOS-specific APIs (`startAbility`/`QOhosWant` and so on), complementing this private bridging layer
- [[ohos-mainthread-mismatch]] — The dual-thread architecture and the `theMainThread` assertion crash; the use case for the reverse-direction `invokeInQtThread`
- [[qt-harmonyos-qt6-status]] — Qt6 HarmonyOS porting status; note that this private API may be restructured in Qt6 when migrating
