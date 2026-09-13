---
id: semantic-qt-harmonyos-platform-limits
type: semantic
domain: tech
tags: [qt, harmonyos, platform-limits, chmod, symlink, dlopen, timezone, font, xcomponent, zink, rgba8, mipmap]
created: 2026-06-02
updated: 2026-08-15
status: active
audience: public
refs: [semantic-qt-harmonyos-overview, semantic-qt-harmonyos-api]
summary: >
  The Qt/QPA/QML adapter for HarmonyOS platform limitations: records the observable symptoms, Qt workarounds, and QTBUGs for
  QFile/QStandardPaths/QPluginLoader/QTimeZone, fonts, XComponent, ZINK, and Qt.platform; the platform status and underlying causes are maintained in the common knowledge base.
---

# The Qt adapter for HarmonyOS platform limitations

> Source: [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations)
> Parent issue: [QTBUG-146618](https://bugreports.qt.io/issues/?jql=project%20%3D%20QTBUG%20AND%20parent%20%3D%20QTBUG-146618)
>
> For platform limitations that hold across frameworks, their evidence boundaries, and how to use them, the authority is the common knowledge base's [[ohos-common-kb/semantic/harmonyos-platform-limits|HarmonyOS platform limitations]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/semantic/harmonyos-platform-limits.md)). This page keeps the symptoms and fixes at the `QFile`, `QStandardPaths`, `QPluginLoader`, QML, Qt rendering, and QTBUG level.

## Mapping platform limitations to Qt APIs

The table below records only the observable results at the Qt layer and the adapter; whether a limitation holds, the platform-level cause, error codes, and confirmation status all come from the common knowledge base.

| Qt consumption point | Symptom at the Qt layer | Qt adapter / routing | Qt tracking |
|---|---|---|---|
| `QFile::setPermissions()` | Returns failure for an existing file | Don't use it as a success condition for your feature; hand permission requirements to the platform packaging contract | [QTBUG-146619](https://bugreports.qt.io/browse/QTBUG-146619) |
| `QFile::link()` | Can't create the link the application needs | Expand it into a real file at build/packaging time rather than creating links at runtime | [QTBUG-146621](https://bugreports.qt.io/browse/QTBUG-146621) |
| `QFileInfo` / `QStandardPaths::findExecutable()` | System executable detection is unreliable | Don't pick programs by scanning PATH desktop-style; use the entry points the platform declares | [QTBUG-146625](https://bugreports.qt.io/browse/QTBUG-146625) |
| Trailing slashes in Qt file IO | Different error branches than on desktop | Normalize and validate the target path in the Qt business layer first | [QTBUG-146578](https://bugreports.qt.io/browse/QTBUG-146578) |
| Non-blocking streams wrapped by `QFile` | The EOF state can appear early | Check both the Qt IO state and the underlying error, and add regression tests | [QTBUG-146579](https://bugreports.qt.io/browse/QTBUG-146579) |
| `QTimeZone` | The libc backend can't provide complete data | Build Qt with the ICU backend and verify the target time zones | [QTBUG-146717](https://bugreports.qt.io/browse/QTBUG-146717) / [QTBUG-146559](https://bugreports.qt.io/browse/QTBUG-146559) |
| Qt/third-party workers | Code relying on thread cancellation isn't portable | Use Qt interruption / cooperative cancellation | [QTBUG-146708](https://bugreports.qt.io/browse/QTBUG-146708) |
| `QPluginLoader` / runtime `.so` | Dynamic plugin loading fails | Ship plugins as part of the final HAP's native library closure, or link statically when the set is fixed; see [runtime-fail-dlopen-writable-path](../problems/runtime-fail-dlopen-writable-path.md) | [QTBUG-146624](https://bugreports.qt.io/browse/QTBUG-146624) |
| Qt/third-party shared library deployment | A post-processed ELF won't load | Have the Qt packaging pre-check preserve what the loader needs and verify a fresh HAP | [QTBUG-146620](https://bugreports.qt.io/browse/QTBUG-146620) |

## Standard paths

### QStandardPaths constraints
- `standardLocations()` and `writableLocation()` return the same single path
- `AppLocalDataLocation` maps to HarmonyOS's `preferencesDir`
- **Unsupported** (returns empty): `PublicShareLocation`, `TemplatesLocation`, `StateLocation`, `GenericStateLocation`
- `findExecutable()` doesn't work because of `stat()` restrictions
- **QTBUG**: [QTBUG-146625](https://bugreports.qt.io/browse/QTBUG-146625)

### The resource directory
- Path: `<bundleCodeDir>/entry/resources/resfile`
- Currently **no** QStandardPaths enumerator maps to this path
- **QTBUG**: [QTBUG-146626](https://bugreports.qt.io/browse/QTBUG-146626)

## The font system

### No monospace font
- **Impact**: `QFontDatabase::systemFont(FixedFont)` returns a non-monospace font
- **Workaround**: the application must bundle its own monospace font and register it with `QFontDatabase::addApplicationFont()`
- **QTBUG**: [QTBUG-146623](https://bugreports.qt.io/browse/QTBUG-146623)

## ArkUI/ArkTS APIs

### XComponent (ARKUI_XCOMPONENT_TYPE_SURFACE) is deprecated in API 20
- **Status**: deprecated by Huawei
- **Impact**: Qt uses ARKUI_XCOMPONENT_TYPE_SURFACE as its native OpenGL rendering surface
- **Migration direction**: the ContentSlot component
- **Reference**: [ContentSlot documentation](https://developer.huawei.com/consumer/en/doc/harmonyos-guides/arkts-rendering-control-contentslot)
- **QTBUG**: [QTBUG-146622](https://bugreports.qt.io/browse/QTBUG-146622)

## References

- [HarmonyOS Platform Limitations](https://wiki.qt.io/Qt_for_HarmonyOS/platform_limitations)
- [HarmonyOS MUSL doesn't export peculiar symbols](https://developer.huawei.com/consumer/en/doc/harmonyos-references/musl-peculiar-symbol)

## OpenGL / ZINK rendering

> OHOS Qt 5.12 provides desktop OpenGL through Mesa ZINK (OpenGL-over-Vulkan, `NEED_OPENGL=1`); main.cpp's `QSurfaceFormat(3,2 CoreProfile)` → Qt3D selects gl3 shaders. ZINK has a few silent pitfalls in its GL→Vulkan translation layer.

### glGenerateMipmap fails for RGBA8 alpha textures (incomplete mipmaps → black sampling)
- **Status**: confirmed by testing (planets-qml on a real device, 2026-07-14)
- **Symptom**: when a Qt3D/QtQuick `Texture2D` uses an **RGBA8 alpha PNG** with `generateMipMaps:true` and `LinearMipMapLinear`, the entity's texture renders **pure black** (lighting/shadows are fine); the same configuration with an **RGB8 JPG works**. hilog shows **no GL errors** (per the OpenGL spec, an incomplete texture silently returns `(0,0,0,1)` by design rather than raising an error)
- **Cause**: ZINK implements `glGenerateMipmap` with `vkCmdBlitImage`, and mipmap generation for **GL_RGBA8 (with an alpha channel)** fails or produces a broken mip chain → the texture is incomplete → `LinearMipMapLinear` sampling returns black. **GL_RGB8 (no alpha) mipmaps work fine.** ZINK maps both RGB8 and RGBA8 to `VK_FORMAT_R8G8B8A8_UNORM`, so the asymmetry lives at the GL-level completeness/mip-blit layer, not in VkImage creation
- **How to tell**: pure black (rather than a colored band with transparent gaps) is the key signal — an alpha PNG's opaque regions have color, so blending being off alone would show a colored band; pure black means texture sampling returned 0 = incomplete
- **Workaround**: turn off mipmaps for alpha-PNG entities (`generateMipMaps:false` + `minificationFilter:Texture.Linear` — **both must change**, since base-level-only with a mipmap min filter is still incomplete and still black); keep mipmaps for JPG entities. See [problems/render-black-rgba8-zink-mipmap](../problems/render-black-rgba8-zink-mipmap.md)
- **A related secondary defect**: transparent entities (`opacity<1`) also need explicit `BlendEquation` + `BlendEquationArguments` + `NoDepthMask` RenderStates — Qt3D's `opacity` is just a shader uniform and **doesn't enable GL_BLEND automatically**. That's an independent defect, not the cause of the black rendering

### Qt.platform.os returns "linux" on OHOS (not "ohos")
- **Status**: confirmed in the source
- **Cause**: `qsystemdetection.h:115-117` defines both `Q_OS_OHOS` and `Q_OS_LINUX` (the same pattern as Android); `qqmlplatform.cpp` has no `Q_OS_OHOS` branch → it falls through to `Q_OS_LINUX` → `Qt.platform.os` returns **"linux"**
- **Impact**: a QML guard like `Qt.platform.os === "ohos"` will **never fire** (a silent bug)
- **Workaround**: detect OHOS in QML with `Qt.platform.pluginName === "ohos"` (the QPA plugin key is "ohos", exposed through `Qt.platform.pluginName`)
