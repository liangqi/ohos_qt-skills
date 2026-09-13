---
id: problem-render-black-rgba8-zink-mipmap
type: problem
domain: runtime
tags: [zink, rgba8, mipmap, texture-incomplete, qt3d, alpha-png, ohos]
created: 2026-07-14
updated: 2026-07-14
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-platform-limits]
summary: >
  Under OHOS ZINK (Qt5's OpenGL-over-Vulkan), when a Qt3D Texture2D uses an RGBA8 alpha PNG with generateMipMaps:true,
  glGenerateMipmap fails for RGBA8 / produces a broken mip chain → the texture's mipmaps are incomplete → the sampler returns black (0,0,0,1) → the entity renders pure black;
  RGB8 JPG planet textures under the same effect are fine. Fix: disable mipmaps for alpha-PNG entities (generateMipMaps:false + minificationFilter:Texture.Linear),
  guarded by Qt.platform.pluginName!=="ohos" (note that Qt.platform.os returns "linux" on OHOS).
leader_summary: >
  Captured reusable troubleshooting for a silent bug in the OHOS ZINK rendering pipeline (incomplete mipmaps for RGBA8 alpha textures → pure black),
  directly applicable when porting Qt3D/QtQuick 3D applications to HarmonyOS.
impact: [Migration efficiency, Qt6 support, Commercial response]
deliverables: [problem record, patch]
evidence: [The planets-qml-ohos project fix (SolarSystem.qml + PlanetMaterial.qml), a clean hilog with no GL errors (the failure is silent)]

# ====== Search keywords ======
error_message: >
  No GL error logs (the failure is silent). Symptom: Qt3D sphere/ring/cloud textures render pure black and invisible,
  while Phong lighting/shadows work and other entities with RGB8 JPG textures are fine.
error_code: ""
keywords: [zink, rgba8, mipmap, glGenerateMipmap, alpha-png, colortrans, texture-incomplete, black, qt3d, planets-qml, blending-off]
symptoms: >
  Qt3D entity textures render pure black (the cloud shell / Saturn's rings / Uranus's rings) while lighting and shadows are correct;
  entities using RGB8 JPGs under the same effect look fine; the only distinguishing variable is the texture format, RGBA8 (alpha) vs RGB8 (JPG).

# ====== Problem details ======
environment: >
  The OHOS Qt 5.12.12 OHOS SDK; a HUAWEI MateBook Fold device; Mesa ZINK (OpenGL-over-Vulkan, NEED_OPENGL=1);
  main.cpp's QSurfaceFormat 3.2 CoreProfile → Qt3D selects gl3 shaders; Qt3D Texture2D (QOpenGLTexture).
---

# Qt3D RGBA8 alpha-PNG textures render pure black under OHOS ZINK (incomplete mipmaps)

## Error message

```
(no error logs — the failure is completely silent)
The only hilog line is: MESA: ZINK: SSBO is readonly in vertex stage!  (an unrelated red herring, from PlanetEffect's light UBO/SSBO binding)
No GL_INVALID / texture / mipmap error lines (per the OpenGL spec, sampling an incomplete texture silently returns (0,0,0,1) by design rather than raising an error)
Symptom: the cloud shell / Saturn's rings / Uranus's rings render pure black; Saturn the planet (saturnmap.jpg, RGB8) under the same effect is fine
```

## Scenario

Running the OHOS port of planets-qml (the Qt3D solar system demo) on a real device:

- **The black entities**: Earth's cloud layer (`earthcloudmapcolortrans.png`), Saturn's rings (`saturnringcolortrans.png`), and Uranus's rings (`uranusringcolortrans.png`) — all three are **RGBA8 alpha PNGs** (PNG color type 6, "colortrans" = color + transparency, with an alpha channel).
- **The working entities**: the Mercury/Venus/Earth/Mars/Jupiter/Saturn/Uranus/Neptune planet textures — all **RGB8 JPGs** (no alpha).
- Both go through **the same** diffuseTexture Texture2D block in `PlanetMaterial.qml` (`generateMipMaps:true` + `LinearMipMapLinear` + `maximumAnisotropy:16.0` + `Repeat`).

**The decisive comparison**: Saturn the planet (`shadowMapEffect` + `saturnmap.jpg`, RGB8) is fine, while Saturn's rings (**the same** `shadowMapEffect` + `saturnringcolortrans.png`, RGBA8) are pure black — the same effect, shader, material class, and mipmap configuration; the only variable is RGBA8 vs RGB8.

> The user's initial report was "the earth texture didn't load and is covered in black" — the root cause is that the cloud shell (an RGBA8 alpha PNG) renders pure black and sits over the earth, hiding it. Disabling the cloud makes the earth texture appear immediately.

## Cause

**Mechanism (a)**: OHOS Mesa ZINK (OpenGL-over-Vulkan) implements `glGenerateMipmap` with `vkCmdBlitImage`, and for **GL_RGBA8 (alpha channel) textures, mipmap generation fails / produces a broken mip chain**, leaving the texture's mipmaps incomplete. Combined with `minificationFilter=LinearMipMapLinear` (which requires every mip level to be defined), the OpenGL spec **silently returns black (0,0,0,1)** for **all** samples by design (the base level included) — with no GL error (hence the clean hilog).

- **GL_RGB8 (no alpha, JPG) texture mipmaps generate fine under the same ZINK** → the texture is complete → sampling works → the JPG planet textures are fine.
- ZINK maps both GL_RGB8 and GL_RGBA8 to the same VkFormat (`VK_FORMAT_R8G8B8A8_UNORM`), so there's no difference at VkImage creation; the RGB8/RGBA8 asymmetry is in ZINK's **GL-level completeness/mip-blit layer** (exactly where mechanism (a) operates), not in VkImage creation.

**Other hypotheses ruled out** (with pixel-level evidence):

| Hypothesis | How it was tested | Conclusion |
|------------|-------------------|------------|
| (b) Blending isn't enabled → black RGB in transparent regions covers things | The opaque region of the rings is tan (RGB≈87/82/85), so with blending off you'd see a tan band, not pure black | **Ruled out** (not the cause of the black; though the missing blending is an independent secondary defect, see below) |
| (c) RGBA8 upload / VkImage creation fails | ZINK maps RGB8/RGBA8 to the same VkFormat, so there's no basis for a format-level failure | Unlikely (it would only be escalated to this if it were still black with mipmaps off) |
| (d) PNG decode / ICC / sRGB | The cloud has no iCCP while the rings have iCCP=sRGB, and the symptoms are identical; libpng emits no iCCP warning (only the 2D thumbnails do) | Ruled out |
| NPOT | The rings are 1024×512 (POT) and still black; earthmap2k.jpg is NPOT and fine | Ruled out |
| anisotropy 16 | Qt3D has two guards (`gltexture.cpp:514` + `qopengltexture.cpp:4288`) that silently skip it when the extension is missing | Ruled out (not the culprit) |

**Pure black (rather than a colored band with transparent gaps) is the key diagnostic**: the rings' opaque regions have color, so blending being off would show a colored band; pure black means texture sampling itself returns 0 = an incomplete texture.

## Solution

Add a backward-compatible mipmap toggle property to `PlanetMaterial.qml` so that **only the alpha-PNG entities disable mipmaps on OHOS**, while the JPG planets keep their mipmap quality:

```qml
// PlanetMaterial.qml
property bool diffuseGenerateMipMaps: true  // defaults to true (preserving upstream mipmap behavior; the JPG planets are untouched)

// The diffuseTexture block (bound to the toggle; specularTexture/normalTexture are untouched — they're all RGB8 JPGs whose mipmaps work)
Texture2D {
    id: diffuseTexture
    minificationFilter: root.diffuseGenerateMipMaps ? Texture.LinearMipMapLinear : Texture.Linear
    // ...
    generateMipMaps: root.diffuseGenerateMipMaps
    // ...
}

// SolarSystem.qml — the 3 alpha-PNG entities (cloud + 2 ring sets) disable mipmaps on OHOS
PlanetMaterial {
    id: materialSaturnRing
    // ...
    diffuseMap: "qrc:/images/solarsystemscope/saturnringcolortrans.png"
    diffuseGenerateMipMaps: Qt.platform.pluginName !== "ohos"  // disable mipmaps on OHOS
}
```

**Key point**: `generateMipMaps:false` **must** be accompanied by changing `minificationFilter` from `LinearMipMapLinear` to `Texture.Linear` — otherwise a base-level-only texture with a mipmap min filter is still incomplete and still black.

**Guard with `Qt.platform.pluginName !== "ohos"`** (⚠️ see the notes).

## Notes

### ⚠️ Qt.platform.os returns "linux" on OHOS, not "ohos"

`qsystemdetection.h:115-117` defines both `Q_OS_OHOS` and `Q_OS_LINUX` (the same pattern as Android); `qqmlplatform.cpp` has no `Q_OS_OHOS` branch → it falls through to `Q_OS_LINUX` → `Qt.platform.os` returns **"linux"**. **A guard using `Qt.platform.os === "ohos"` will never fire (a silent bug)**. In QML, detect OHOS with `Qt.platform.pluginName === "ohos"` (the QPA plugin key is "ohos", exposed through `Qt.platform.pluginName`).

### Blending is an independent secondary defect (not the cause of the black)

Qt3D's `PlanetEffect`/`ShadowEffect`/`SunEffect` all note "no special render state => use default set of states" and have **no BlendEquation/BlendEquationArguments/NoDepthMask**. Qt3D's `opacity` is just a shader uniform and **doesn't enable GL_BLEND automatically**. So the cloud (opacity 0.2) and rings (opacity 0.4), which should be semi-transparent, actually render opaque.

- Once the black is fixed (mipmaps off), the cloud/rings show their textures but are **opaque** (the cloud layer covers the earth, and the gaps in the rings are solid).
- For real transparency, add an explicit blend state to the relevant RenderPasses:
  ```qml
  // The gl3 forward RenderPass in PlanetEffect.qml / ShadowEffect.qml
  renderStates: [
      BlendEquation { blendFunction: BlendEquation.Add },
      BlendEquationArguments {
          sourceRgb: BlendEquationArguments.SourceAlpha
          destinationRgb: BlendEquationArguments.OneMinusSrcAlpha
          sourceAlpha: BlendEquationArguments.One
          destinationAlpha: BlendEquationArguments.OneMinusSrcAlpha
      },
      NoDepthMask {}
  ]
  ```
  A cheaper shader-only alternative: `if (texture(diffuseTexture, uv).a < 0.5) discard;` (a hard cutout, losing soft opacity).
- The cloud should **stay disabled** (its components commented out) until blending is fixed, or the opaque cloud layer hides the earth.

### Keeping upstream pristine

`PlanetMaterial.qml` and the shaders are byte-identical to upstream (only the PlanetFrameGraph shadow-sampler comment and the ×1000 scaling are OHOS-required changes). This fix adds a property and overrides it per entity, so it **doesn't touch the shared upstream shader/effect files**, and desktop keeps its mipmap quality. Opaque rings are acceptable for the demo; add the blending fix if you need real transparency.

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured reusable troubleshooting for a silent bug in the OHOS ZINK rendering pipeline (incomplete mipmaps for RGBA8 alpha textures → pure black), directly applicable when porting Qt3D/QtQuick 3D applications to HarmonyOS |
| Scope of impact | Qt3D application ports to HarmonyOS, Qt6 HarmonyOS support, responses on commercial Qt 3D applications |
| Deliverables | problem record + the planets-qml-ohos patch (PlanetMaterial.qml + SolarSystem.qml) |
| Evidence | The planets-qml-ohos fix commit, a clean hilog (the failure is silent with no GL errors), and on-device verification showing the colored ring band |
| How to reuse | When a Qt3D/QtQuick 3D application on an OHOS device shows "textures pure black but lighting fine, JPGs fine, only alpha PNGs black", apply this directly: disable mipmaps for the alpha-PNG entities |

## Related

- See the _lookup quick-reference table — another OHOS ZINK rendering pipeline problem (EGL_BAD_CONFIG 12293 with setSamples(4), fixed with a `#ifndef Q_OS_OHOS` guard)
- [[semantic-qt-harmonyos-platform-limits]] — the ZINK GL-level limitations are added to that page's "OpenGL/ZINK rendering" section
- [[semantic-qt-harmonyos-project-structure]] — The qrc/Texture2D deployment model for Qt3D applications
