---
updated: 2026-08-29
total_problems: 36
description: >
  The error quick-reference index (rebuilt from the problem pages' frontmatter).
---

# Error quick-reference table

> When you hit an execution error, search here for the error_message / error_code first.
> Known Qt platform limitations live in semantic/qt-harmonyos-platform-limits.md.

## By error code

| Error code | Problem file | Summary |
|------------|--------------|---------|
| N/A | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| 00306049 | [build-fail-duplicate-so](build-fail-duplicate-so.md) | The hvigor build fails at the ProcessLibs stage with "Duplicated files found" |
| 00308018 | [build-fail-hvigor-spawn-java-enoent](build-fail-hvigor-spawn-java-enoent.md) | Running `node hvigorw.js assembleHap` from bash for a Qt5 HarmonyOS demo: CMake/ninja compiles the C++ fine and ArkTS compiles fine, but the final PackageHap step fails with `spawn java ENOENT`. Even with DevEco's jbr/bin added to PATH, `which java` in bash can't find it (or finds it, yet node's spawn still reports ENOENT). |
| N/A | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| N/A | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | Chinese characters in a curl POST/PATCH request body show up garbled on the API side (e.g. Cyrillic characters like ֪ʶ⽻) |
| errno=22 (EINVAL) | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | Loading a .so plugin at runtime fails, dlopen returns EINVAL, and the path is under /data/storage/el2/ |

## By symptom

| Symptom keyword | Problem file | Summary |
|-----------------|--------------|---------|
| `C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native` | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| `Build error: enumerators such as QtOhosExtras::AbilityClose can't be found` | [build-fail-closeeventrootcause-path](build-fail-closeeventrootcause-path.md) | Build error: enumerators such as QtOhosExtras::AbilityClose can't be found |
| `The CMake configure stage errors out because find_package can't find OhosExtras` | [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) | The CMake configure stage errors out because find_package can't find the OhosExtras package |
| `The hvigor build fails at the ProcessLibs stage with "Duplicated files f` | [build-fail-duplicate-so](build-fail-duplicate-so.md) | The hvigor build fails at the ProcessLibs stage with "Duplicated files found" |
| `An "undeclared identifier" error when compiling FFmpeg-related code` | [build-fail-ffmpeg9-removed-api](build-fail-ffmpeg9-removed-api.md) | An "undeclared identifier" error when compiling FFmpeg-related code |
| `Porting a Linux application to OHOS, the build reports unknown type name '__pid_t'/` | [build-fail-glibc-internal-symbols-ohos-musl](build-fail-glibc-internal-symbols-ohos-musl.md) | Porting a Linux application to OHOS, the build reports unknown type name '__pid_t'/'__uid_t' or in6_addr has no member 's6_addr32' |
| `Running `node hvigorw.js assembleHa` from bash for a Qt5 HarmonyOS demo` | [build-fail-hvigor-spawn-java-enoent](build-fail-hvigor-spawn-java-enoent.md) | Running `node hvigorw.js assembleHap` from bash for a Qt5 HarmonyOS demo: CMake/ninja compiles the C++ fine and ArkTS compiles fine, but the final PackageHap step fails with `spawn java ENOENT`. Even with DevEco's jbr/bin added to PATH, `which java` in bash can't find it (or finds it, yet node's spawn still reports ENOENT). |
| `Porting a Linux Qt application to OHOS, the build can't find uuid/uuid.h or the link can't find -lu` | [build-fail-libuuid-missing-ohos-musl](build-fail-libuuid-missing-ohos-musl.md) | Porting a Linux Qt application to OHOS, the build can't find uuid/uuid.h or the link can't find -luuid |
| `"bracket depth exceeded" when compiling a source file that uses magic_enum` | [build-fail-magic-enum-bracket-depth](build-fail-magic-enum-bracket-depth.md) | "bracket depth exceeded" when compiling a source file that uses magic_enum |
| `A Qt OHOS app whose entry shim uses extern "C" main and which has .qrc resources` | [build-fail-qinitresource-extern-c-main](build-fail-qinitresource-extern-c-main.md) | A Qt OHOS app whose entry shim uses extern "C" main and which has .qrc resources fails to link with undefined symbol: qInitResources_<name> |
| `unable to find library -licui18n / ICU=no / ures` | [build-fail-qt515-icu-detection](build-fail-qt515-icu-detection.md) | unable to find library -licui18n / ICU=no / ures.h not found / UCNV_FROM_U_CALLBACK_SUBSTITUTE undeclared |
| `no member named 'nullptr_t' in the global namesp` | [build-fail-qt6-libcpp-musl-isystem](build-fail-qt6-libcpp-musl-isystem.md) | no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; the injected -isystem sysroot/usr/include makes musl shadow the clang builtins) |
| `fatal error: 'QtOhosExtras/QOhosAppContext' file` | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| `spawn java ENOENT; BuildNativeWithCmake finished` | [build-hvigor-native-skip](build-hvigor-native-skip.md) | spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing) |
| `CMake Error: find_package(Qt5 COMPONENTS Widgets` | [build-missing-qt5uitools-ohos](build-missing-qt5uitools-ohos.md) | CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) fails (the OHOS Qt5 SDK lacks the Qt5UiTools module) |
| `A HAP packaged by the hvigor CLI crashes at startup after installation, while DevEco Studio IDE Run ` | [deploy-fail-hvigor-cli-hap-crash](deploy-fail-hvigor-cli-hap-crash.md) | A HAP packaged by the hvigor CLI crashes at startup after installation, while DevEco Studio IDE Run works fine |
| `Q_ASSERT(receiver->d_func()->threadData.loadAcqu` | [ohos-mainthread-mismatch](ohos-mainthread-mismatch.md) | Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (triggered by a mouse click in a debug build) |
| `Developers mistakenly assume QFileDialog needs a \#ifdef Q_OS_OHOS workaround` | [ohos-qfiledialog-native-support](ohos-qfiledialog-native-support.md) | Developers mistakenly assume QFileDialog needs a \#ifdef Q_OS_OHOS workaround on OHOS (QInputDialog/hard-coded paths) and add unnecessary guard code, creating maintenance burden and conflicting with the native support; in reality QOhosPlatformIntegrationPlugin already provides native support, so the standard QFileDialog API can be used directly. |
| `Qt3D entity textures render pure black (the cloud shell / Saturn's rings / Uranus's rings) while lighting` | [render-black-rgba8-zink-mipmap](render-black-rgba8-zink-mipmap.md) | Qt3D entity textures render pure black (the cloud shell / Saturn's rings / Uranus's rings) while lighting and shadows are correct; entities using RGB8 JPGs under the same effect look fine; the only distinguishing variable is the texture format, RGBA8 (alpha) vs RGB8 (JPG). |
| `A QDialog won't close and won't scroll (both at once), especially in the matplotlib three-level window scenario` | [runtime-blocked-by-modal-window-no-parent](runtime-blocked-by-modal-window-no-parent.md) | A QDialog won't close and won't scroll (both at once), especially in the matplotlib three-level window scenario |
| `The HAP installs successfully but crashes when launched, reporting handleAbil` | [runtime-crash-arkts-template-modules-mismatch](runtime-crash-arkts-template-modules-mismatch.md) | The HAP installs successfully but crashes when launched, reporting handleAbilityStageOnCreate undefined in QAbilityStage.ets |
| `The signed HAP installs successfully, but after aa start the process disappears within 1-9 s. The faultlog shows a js` | [runtime-crash-libqohos-libqt5core-version-mismatch](runtime-crash-libqohos-libqt5core-version-mismatch.md) | The signed HAP installs successfully, but after aa start the process disappears within 1-9 s. The faultlog shows a jscrash TypeError (handleAbilityStageOnCreate of undefined, or a missing deviceType property). |
| `The signed HAP installs successfully, but after aa start the process disappears within 1-2 seconds (a crash at startup); no application` | [runtime-crash-libqohos-modules-mismatch](runtime-crash-libqohos-modules-mismatch.md) | The signed HAP installs successfully, but after aa start the process disappears within 1-2 seconds (a crash at startup); no application window appears on the desktop, or it flashes and exits. |
| `The application crashes while the user is typing a path into the Load File field (before clicking the Load button)` | [runtime-crash-loadfile-textchanged-no-debounce](runtime-crash-loadfile-textchanged-no-debounce.md) | The application crashes while the user is typing a path into the Load File field (before clicking the Load button) |
| `The application crashes about a second after launch (a C++ SIGSEGV); the QtMainThread stack frames show a null-pointer dereference` | [runtime-crash-null-pointer-entry-shim](runtime-crash-null-pointer-entry-shim.md) | The application crashes about a second after launch (a C++ SIGSEGV); the QtMainThread stack frames show a null-pointer dereference |
| `The signed HAP installs successfully and the application launches after aa start (the Qt window appears and QtWatchdog runs)` | [runtime-crash-ohos-deviceinfo-global-expression](runtime-crash-ohos-deviceinfo-global-expression.md) | The signed HAP installs successfully and the application launches after aa start (the Qt window appears and QtWatchdog runs), but the process crashes when onAcceptWant fires (multi-instance / window recreate / a second QApplication construction); the faultlog's LAST_FATAL_MESSAGE is the Napi::Error above. Note: this error and "object has no property named 'deviceType'" are two different generational errors in the @ohos.deviceInfo crash family (see below). |
| `The application crashes a short while after launch (SIGABRT); the crash stack shows exit(1) being called after a configuration-file write failure` | [runtime-crash-sandbox-readonly-path](runtime-crash-sandbox-readonly-path.md) | The application crashes a short while after launch (SIGABRT); the crash stack shows exit(1) being called after a configuration-file write failure |
| `Chinese characters in a curl POST/PATCH request body show up garbled on the API side (e.g. Cyrillic` | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | Chinese characters in a curl POST/PATCH request body show up garbled on the API side (e.g. Cyrillic characters like ֪ʶ⽻) |
| `Loading a .so plugin at runtime fails, dlopen returns EINVAL, and the path is under /data/storag` | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | Loading a .so plugin at runtime fails, dlopen returns EINVAL, and the path is under /data/storage/el2/ |
| `Opening Add Qt Versions shows an invalid-path po` | [runtime-fail-file-dialog-invalid-default-uri](runtime-fail-file-dialog-invalid-default-uri.md) | Opening Add Qt Versions shows an invalid-path popup, or the system picker does not list a qmake file without an extension. |
| `The application crashes immediately after launch (a JSCrash TypeError), with logs showing libQt5DBus.so ` | [runtime-fail-libqtdbus-missing](runtime-fail-libqtdbus-missing.md) | The application crashes immediately after launch (a JSCrash TypeError), with logs showing libQt5DBus.so failing to load |
| `The application crashes immediately after launch, with logs reporting dlopen failed or platform plugin no` | [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) | The application crashes immediately after launch, with logs reporting dlopen failed or platform plugin not found |
| `On launch the application shows a QMessageBox reading "Cannot create the local database!" and then exits (actually a native` | [runtime-fail-sqlite-open-database](runtime-fail-sqlite-open-database.md) | On launch the application shows a QMessageBox reading "Cannot create the local database!" and then exits (actually a native cppcrash); the Login window never appears |
| `The application crashes immediately after launch, with hilog showing dlopen failed or symbol not fo` | [runtime-ffmpeg-versioned-soname-transitive-deps](runtime-ffmpeg-versioned-soname-transitive-deps.md) | The application crashes immediately after launch, with hilog showing dlopen failed or symbol not found |
| `A Qt QML application running on an OHOS device with the dark theme: buttons and text fields have pure-black default backgrounds and the widgets merge into the background` | [runtime-style-dark-palette-pure-black](runtime-style-dark-palette-pure-black.md) | A Qt QML application running on an OHOS device with the dark theme: buttons and text fields have pure-black default backgrounds, and the widgets merge into the background with indistinguishable boundaries (though the text is visible). |
| `SurfaceHolder_Create returns null when setting the XComponent surface opaque` | [surfaceholder-nativexcomponent-incompatibility](surfaceholder-nativexcomponent-incompatibility.md) | SurfaceHolder_Create returns null when setting the XComponent surface opaque; or GetNativeXComponent returns null before the node is mounted, causing a startup crash. |

## Grouped by domain

### Build

| Severity | Problem file | Summary |
|:--------:|--------------|---------|
| 🟡 medium | [build-fail-bash-path-escape](build-fail-bash-path-escape.md) | C:PROGRA~1HuaweiDEVECO~1sdkdefaultOPENHA~1native/llvm/bin/clang++: No such file or directory |
| 🟠 high | [build-fail-closeeventrootcause-path](build-fail-closeeventrootcause-path.md) | Build error: enumerators such as QtOhosExtras::AbilityClose can't be found |
| 🟠 high | [build-fail-cmake-ohosextras](build-fail-cmake-ohosextras.md) | The CMake configure stage errors out because find_package can't find the OhosExtras package |
| 🟡 medium | [build-fail-duplicate-so](build-fail-duplicate-so.md) | The hvigor build fails at the ProcessLibs stage with "Duplicated files found" |
| 🟡 medium | [build-fail-ffmpeg9-removed-api](build-fail-ffmpeg9-removed-api.md) | An "undeclared identifier" error when compiling FFmpeg-related code |
| 🟡 medium | [build-fail-glibc-internal-symbols-ohos-musl](build-fail-glibc-internal-symbols-ohos-musl.md) | Porting a Linux application to OHOS, the build reports unknown type name '__pid_t'/'__uid_t' or in6_addr has no member 's6_addr32' |
| 🟠 high | [build-fail-hvigor-spawn-java-enoent](build-fail-hvigor-spawn-java-enoent.md) | Running `node hvigorw.js assembleHap` from bash for a Qt5 HarmonyOS demo: CMake/ninja compiles the C++ fine and ArkTS compiles fine, but the final PackageHap step fails with `spawn java ENOENT`. Even with DevEco's jbr/bin added to PATH, `which java` in bash can't find it (or finds it, yet node's spawn still reports ENOENT). |
| 🟠 high | [build-fail-libuuid-missing-ohos-musl](build-fail-libuuid-missing-ohos-musl.md) | Porting a Linux Qt application to OHOS, the build can't find uuid/uuid.h or the link can't find -luuid |
| 🟡 medium | [build-fail-magic-enum-bracket-depth](build-fail-magic-enum-bracket-depth.md) | "bracket depth exceeded" when compiling a source file that uses magic_enum |
| 🟡 medium | [build-fail-qinitresource-extern-c-main](build-fail-qinitresource-extern-c-main.md) | A Qt OHOS app whose entry shim uses extern "C" main and which has .qrc resources fails to link with undefined symbol: qInitResources_<name> |
| 🟠 high | [build-fail-qt515-icu-detection](build-fail-qt515-icu-detection.md) | unable to find library -licui18n / ICU=no / ures.h not found / UCNV_FROM_U_CALLBACK_SUBSTITUTE undeclared |
| ⬜ blocker | [build-fail-qt6-libcpp-musl-isystem](build-fail-qt6-libcpp-musl-isystem.md) | no member named 'nullptr_t' in the global namespace; use of undeclared identifier '__promote'; call to 'hypot' is ambiguous (libcxx-ohos c++/v1/cstddef, cmath; the injected -isystem sysroot/usr/include makes musl shadow the clang builtins) |
| 🟡 medium | [build-fail-qtohosextras-camelcase-headers](build-fail-qtohosextras-camelcase-headers.md) | fatal error: 'QtOhosExtras/QOhosAppContext' file not found |
| 🟠 high | [build-hvigor-native-skip](build-hvigor-native-skip.md) | spawn java ENOENT; BuildNativeWithCmake finished after 1ms with no .so artifact (DEVECO_SDK_HOME missing) |
| 🟡 medium | [build-missing-qt5uitools-ohos](build-missing-qt5uitools-ohos.md) | CMake Error: find_package(Qt5 COMPONENTS Widgets UiTools OpenGL QUIET) fails (the OHOS Qt5 SDK lacks the Qt5UiTools module) |

### caveat

| Severity | Problem file | Summary |
|:--------:|--------------|---------|
| 🟢 low | [ohos-qfiledialog-native-support](ohos-qfiledialog-native-support.md) | Developers mistakenly assume QFileDialog needs a \#ifdef Q_OS_OHOS workaround on OHOS (QInputDialog/hard-coded paths) and add unnecessary guard code, creating maintenance burden and conflicting with the native support; in reality QOhosPlatformIntegrationPlugin already provides native support, so the standard QFileDialog API can be used directly. |

### Deployment and installation

| Severity | Problem file | Summary |
|:--------:|--------------|---------|
| 🟡 medium | [deploy-fail-hvigor-cli-hap-crash](deploy-fail-hvigor-cli-hap-crash.md) | A HAP packaged by the hvigor CLI crashes at startup after installation, while DevEco Studio IDE Run works fine |

### errors

| Severity | Problem file | Summary |
|:--------:|--------------|---------|
| 🟠 high | [surfaceholder-nativexcomponent-incompatibility](surfaceholder-nativexcomponent-incompatibility.md) | SurfaceHolder_Create returns null when setting the XComponent surface opaque; or GetNativeXComponent returns null before the node is mounted, causing a startup crash. |

### Runtime

| Severity | Problem file | Summary |
|:--------:|--------------|---------|
| 🟠 high | [ohos-mainthread-mismatch](ohos-mainthread-mismatch.md) | Q_ASSERT(receiver->d_func()->threadData.loadAcquire()->thread.loadRelaxed() == mainThread()) in QCoreApplicationPrivate::sendThroughApplicationEventFilters (triggered by a mouse click in a debug build) |
| 🟠 high | [render-black-rgba8-zink-mipmap](render-black-rgba8-zink-mipmap.md) | Qt3D entity textures render pure black (the cloud shell / Saturn's rings / Uranus's rings) while lighting and shadows are correct; entities using RGB8 JPGs under the same effect look fine; the only distinguishing variable is the texture format, RGBA8 (alpha) vs RGB8 (JPG). |
| 🟠 high | [runtime-blocked-by-modal-window-no-parent](runtime-blocked-by-modal-window-no-parent.md) | A QDialog won't close and won't scroll (both at once), especially in the matplotlib three-level window scenario |
| 🟠 high | [runtime-crash-arkts-template-modules-mismatch](runtime-crash-arkts-template-modules-mismatch.md) | The HAP installs successfully but crashes when launched, reporting handleAbilityStageOnCreate undefined in QAbilityStage.ets |
| 🔴 critical | [runtime-crash-libqohos-libqt5core-version-mismatch](runtime-crash-libqohos-libqt5core-version-mismatch.md) | The signed HAP installs successfully, but after aa start the process disappears within 1-9 s. The faultlog shows a jscrash TypeError (handleAbilityStageOnCreate of undefined, or a missing deviceType property). |
| 🔴 critical | [runtime-crash-libqohos-modules-mismatch](runtime-crash-libqohos-modules-mismatch.md) | The signed HAP installs successfully, but after aa start the process disappears within 1-2 seconds (a crash at startup); no application window appears on the desktop, or it flashes and exits. |
| 🟠 high | [runtime-crash-loadfile-textchanged-no-debounce](runtime-crash-loadfile-textchanged-no-debounce.md) | The application crashes while the user is typing a path into the Load File field (before clicking the Load button) |
| 🔴 critical | [runtime-crash-null-pointer-entry-shim](runtime-crash-null-pointer-entry-shim.md) | The application crashes about a second after launch (a C++ SIGSEGV); the QtMainThread stack frames show a null-pointer dereference |
| 🔴 critical | [runtime-crash-ohos-deviceinfo-global-expression](runtime-crash-ohos-deviceinfo-global-expression.md) | The signed HAP installs successfully and the application launches after aa start (the Qt window appears and QtWatchdog runs), but the process crashes when onAcceptWant fires (multi-instance / window recreate / a second QApplication construction); the faultlog's LAST_FATAL_MESSAGE is the Napi::Error above. Note: this error and "object has no property named 'deviceType'" are two different generational errors in the @ohos.deviceInfo crash family (see below). |
| 🔴 critical | [runtime-crash-sandbox-readonly-path](runtime-crash-sandbox-readonly-path.md) | The application crashes a short while after launch (SIGABRT); the crash stack shows exit(1) being called after a configuration-file write failure |
| 🟡 medium | [runtime-curl-chinese-garbled](runtime-curl-chinese-garbled.md) | Chinese characters in a curl POST/PATCH request body show up garbled on the API side (e.g. Cyrillic characters like ֪ʶ⽻) |
| 🟠 high | [runtime-fail-dlopen-writable-path](runtime-fail-dlopen-writable-path.md) | Loading a .so plugin at runtime fails, dlopen returns EINVAL, and the path is under /data/storage/el2/ |
| 🟠 high | [runtime-fail-file-dialog-invalid-default-uri](runtime-fail-file-dialog-invalid-default-uri.md) | Opening Add Qt Versions shows an invalid-path popup, or the system picker does not list a qmake file without an extension. |
| 🔴 critical | [runtime-fail-libqtdbus-missing](runtime-fail-libqtdbus-missing.md) | The application crashes immediately after launch (a JSCrash TypeError), with logs showing libQt5DBus.so failing to load |
| 🔴 critical | [runtime-fail-qpa-plugin-not-found](runtime-fail-qpa-plugin-not-found.md) | The application crashes immediately after launch, with logs reporting dlopen failed or platform plugin not found |
| 🟠 high | [runtime-fail-sqlite-open-database](runtime-fail-sqlite-open-database.md) | On launch the application shows a QMessageBox reading "Cannot create the local database!" and then exits (actually a native cppcrash); the Login window never appears |
| 🔴 critical | [runtime-ffmpeg-versioned-soname-transitive-deps](runtime-ffmpeg-versioned-soname-transitive-deps.md) | The application crashes immediately after launch, with hilog showing dlopen failed or symbol not found |
| 🟡 medium | [runtime-style-dark-palette-pure-black](runtime-style-dark-palette-pure-black.md) | A Qt QML application running on an OHOS device with the dark theme: buttons and text fields have pure-black default backgrounds, and the widgets merge into the background with indistinguishable boundaries (though the text is visible). |
