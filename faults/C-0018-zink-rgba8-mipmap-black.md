---
id: fault-C-0018
cid: C-0018
type: cause
title: "Mesa ZINK implements glGenerateMipmap via vkCmdBlitImage, which fails / produces a bad mipchain for GL_RGBA8: the texture is incomplete and sampling silently returns black"
nature: defect
domain: render
fault_type: bug
responsible: third-party
co_responsible: []
component: "Mesa ZINK GL→Vulkan translation layer (glGenerateMipmap→vkCmdBlitImage path) × Qt3D Texture2D sampling (LinearMipMapLinear)"
severity: high
evidence_type: both
status: workaround
fix_route: "Wait for Mesa/ZINK to fix RGBA8 mipmap generation and for the fix to arrive with an OHOS SDK graphics stack update, then remove the application-side mipmap switch"
review_note: "No Mesa upstream ticket filed yet (no ticket number in this KB; ticket material = the planets-qml controlled experiment, ready to use); whether the Qt6 OHOS GL path still goes through ZINK is to be confirmed; whether W-0015 needs to cover QtQuick 3D scenarios"
depends_on: []
affects_qt: ["Qt 5.12.12 (OHOS SDK, Mesa ZINK)"]
affects_ohos: ["real device HUAWEI MateBook Fold (NEED_OPENGL=1; API version not recorded)"]
qoh: []
first_seen: 2026-07-14
review_due: 2026-12-15
created: 2026-09-15
updated: 2026-09-15
tags: [zink, mesa, rgba8, mipmap, glgeneratemipmap, texture-incomplete, qt3d, render, black-texture, third-party, ohos]
audience: public
refs: [problem-render-black-rgba8-zink-mipmap, semantic-qt-harmonyos-platform-limits, fault-C-0001]
summary: >
  Mesa ZINK (OpenGL-over-Vulkan) implements glGenerateMipmap with vkCmdBlitImage,
  which fails / produces a bad mipchain for GL_RGBA8 (alpha channel) textures, leaving the texture's mipmaps incomplete;
  LinearMipMapLinear sampling then silently returns (0,0,0,1) black per the GL specification (RGB8 is fine).
  defect/third-party (a third-party graphics stack defect); W-0015 (disable mipmaps for alpha-PNG entities)
  is verified on a real device and adopted; no upstream ticket filed.
---

# C-0018 ZINK RGBA8 mipmap generation fails → incomplete texture samples black

> nature: defect | responsible: third-party | status: workaround | symptoms: S-0017 | workarounds: W-0015 | tickets: none yet | review: 2026-12-15

## Symptoms

### S-0017 Qt3D entities textured with alpha PNGs (RGBA8) render solid black

planets-qml (the Qt3D solar system demo) running on an OHOS real device:

- **entities that go black**: the earth cloud layer (`earthcloudmapcolortrans.png`), the saturn ring
  (`saturnringcolortrans.png`), the uranus ring (`uranusringcolortrans.png`)
  -- all three are **RGBA8 alpha PNGs** (PNG colortype 6, with an alpha channel), and the textures are
  **solid black** (the user first reported "the earth texture isn't loaded and is covered in black"; it was actually an opaque
  black cloud shell around the earth); Phong lighting/shadows are fine;
- **entities that are fine**: the mercury/venus/earth/mars/jupiter/saturn/uranus/neptune
  planet textures -- all **RGB8 JPGs** (no alpha);
- both go through **the same** diffuseTexture Texture2D block of `PlanetMaterial.qml`
  (`generateMipMaps:true` + `LinearMipMapLinear` + `maximumAnisotropy:16.0`
  + `Repeat`);
- hilog shows **no GL errors** (only `MESA: ZINK: SSBO is readonly in vertex stage!`,
  an unrelated red herring from PlanetEffect's light UBO/SSBO binding) -- the failure is completely silent;
- **the decisive control**: the saturn planet (`shadowMapEffect` + `saturnmap.jpg` RGB8)
  is fine vs the saturn ring (**the same** `shadowMapEffect` +
  `saturnringcolortrans.png` RGBA8) is solid black -- same effect / same shader / same material
  class / same mipmap configuration; the only variable is the texture format RGBA8 vs RGB8.

## Root cause / classification basis

**Mechanism**: OHOS Mesa ZINK (OpenGL-over-Vulkan, `NEED_OPENGL=1`) implements
`glGenerateMipmap` via `vkCmdBlitImage`, and **mipmap generation for GL_RGBA8 (alpha channel) textures
fails / produces a bad mipchain** → the texture's mipmaps are incomplete → combined with
`minificationFilter=LinearMipMapLinear` (which requires every mip level to be defined), the OpenGL
specification by design **silently returns (0,0,0,1) black** for every sample (including the base level),
without reporting a GL error -- hence the clean hilog.

- **For GL_RGB8 (no alpha, JPG) textures, mipmaps are generated correctly by the same ZINK** → the texture is
  complete → sampled normally → the JPG planet textures are fine;
- ZINK maps both GL_RGB8 and GL_RGBA8 to the same VkFormat
  (`VK_FORMAT_R8G8B8A8_UNORM`), so there is no difference at VkImage creation; the RGB8/RGBA8
  asymmetry is in ZINK's **GL-level completeness/mip-blit layer** (exactly where
  glGenerateMipmap operates), not in VkImage creation.

**Other hypotheses ruled out** (pixel-level evidence; the full version is in the problems page):

| Hypothesis | Test | Conclusion |
|------|------|------|
| Blending not enabled → black RGB in transparent areas covers things | The ring's opaque areas are tan (RGB≈87/82/85); with blending off a tan band would still show, not solid black | Ruled out (not the cause of the black; missing blending is a separate minor defect, see Related) |
| RGBA8 upload / VkImage creation fails | RGB8/RGBA8 map to the same VkFormat; no basis for a format-level failure | Low |
| PNG decoding / ICC / sRGB | The cloud has no iCCP and the ring has iCCP=sRGB, with identical symptoms; no iCCP warning from libpng | Ruled out |
| NPOT textures | The 1024×512 POT ring is also black; the NPOT earthmap2k.jpg is fine | Ruled out |
| anisotropy 16 | Qt3D's double guard (`gltexture.cpp:514` + `qopengltexture.cpp:4288`) silently skips it when the extension is missing | Ruled out |

**Solid black (rather than a colored band + transparent gaps) is the key criterion**: the ring's opaque areas are colored, so
blending-off alone would show a colored band; solid black means the texture sampling itself returns 0 = an incomplete texture.

**Evidence form**: the planets-qml-ohos real-device project + the single-variable controlled experiment with the same effect described above
(demo level); hilog reading (silent failure without GL errors + identifying the red herring) (logs level)
→ both.

## Responsibility

`third-party` (the Mesa/ZINK third-party graphics stack): the defect is in ZINK's GL→Vulkan translation layer
-- the mipmap blit is asymmetric for GL formats with alpha (RGBA8 fails, RGB8 works).
Qt is not responsible: Qt3D's `generateMipMaps:true + LinearMipMapLinear` is a legal configuration that works on
desktop GL. OHOS is not responsible: the Vulkan layer behaves correctly; the defect is in the GL translation layer,
not in the system's Vulkan implementation. Fix route: a Mesa release (arriving with an OHOS SDK graphics stack update).

## Permanent fix (defect)

Wait for Mesa/ZINK to fix `glGenerateMipmap` for RGBA8 (the `vkCmdBlitImage` path).
The ticket material is ready: the planets-qml controlled experiment (same effect, the texture format is the only variable) + the silent
repro criteria + the source path location; not yet filed with Mesa bugzilla (no ticket number recorded; none invented).

## Workarounds

- **W-0015 (adopted, verified 2026-07-14 on a real device)**: on OHOS, disable mipmaps for alpha-PNG entities
  -- add a backward-compatible switch property to `PlanetMaterial.qml` so that only alpha-PNG entities disable mipmaps on
  OHOS, while the JPG planets keep their mipmap quality:

  ```qml
  // PlanetMaterial.qml
  property bool diffuseGenerateMipMaps: true  // default true (upstream behavior unchanged, JPG planets unchanged)

  // diffuseTexture block (bound to the switch; specular/normalTexture unchanged -- they are all RGB8 JPGs)
  Texture2D {
      id: diffuseTexture
      minificationFilter: root.diffuseGenerateMipMaps ? Texture.LinearMipMapLinear : Texture.Linear
      generateMipMaps: root.diffuseGenerateMipMaps
  }

  // SolarSystem.qml -- the 3 alpha-PNG entities (cloud + 2 rings) disable mipmaps on OHOS
  PlanetMaterial {
      id: materialSaturnRing
      diffuseMap: "qrc:/images/solarsystemscope/saturnringcolortrans.png"
      diffuseGenerateMipMaps: Qt.platform.pluginName !== "ohos"  // disable mipmaps on OHOS
  }
  ```

  **Three key points**:

  1. `generateMipMaps:false` **must be accompanied** by changing `minificationFilter` from
     `LinearMipMapLinear` to `Texture.Linear` -- otherwise a base-level-only texture
     with a mipmap min filter is still incomplete → still black;
  2. the QML guard must use `Qt.platform.pluginName !== "ohos"` -- `Qt.platform.os`
     returns "linux" on OHOS, so a check on os would never trigger (silently fails, see
     [C-0001](C-0001-qqmlplatform-os-ohos-branch.md));
  3. implemented via a property + per-entity overrides, **without touching the upstream shared shader/effect
     files**; desktop keeps the mipmap quality (the pristine fix strategy).

  Cost: alpha-PNG entities lose mipmaps (lower minification quality: aliasing on distant textures);
  needs a per-entity switch. Retirement condition: once Mesa ZINK fixes RGBA8 mipmap generation and the fix arrives in the OHOS SDK
  in use, remove the `diffuseGenerateMipMaps` switch, restore the upstream
  mipmap behavior and rerun the verification.

## Tickets

None yet. No ticket filed with Mesa bugzilla (neither the source page nor the platform-limits page records a ticket number); if
filed later, use the planets-qml controlled experiment as the repro material.

## Version verification log

| Date | Environment (Qt/OHOS) | Action | Result | Status change |
|------|----------------|------|------|---------|
| 2026-07-14 | Qt 5.12.12 OHOS SDK / HUAWEI MateBook Fold real device / Mesa ZINK (NEED_OPENGL=1) | planets-qml real-device repro: with the same effect, RGB8 JPG planets are fine vs RGBA8 alpha-PNG (cloud + 2 rings) solid black; the texture format is the only variable; no GL errors in hilog (silent failure) | Classification holds (ZINK GL translation layer defect, third-party) | → diagnosed |
| 2026-07-14 | Same as above | Applied W-0015 (disable mipmaps for alpha-PNG entities + Texture.Linear, pluginName guard) | The rings show colored bands, textures display correctly | → workaround |

## Related

- Symptoms (S): S-0017
- Workarounds (W): W-0015
- Tickets (T): none yet
- problems: [render-black-rgba8-zink-mipmap](../problems/render-black-rgba8-zink-mipmap.md)
- semantic: [qt-harmonyos-platform-limits](../semantic/qt-harmonyos-platform-limits.md) §OpenGL / ZINK rendering
- Related causes (C): [C-0001](C-0001-qqmlplatform-os-ohos-branch.md) (no depends_on relationship; W-0015's QML guard is written this way because of it, avoiding the `Qt.platform.os` check)
- Note: transparent entities (`opacity<1`) additionally need explicit
  `BlendEquation`+`BlendEquationArguments`+`NoDepthMask` RenderStates -- Qt3D's
  `opacity` is only a shader uniform and doesn't enable GL_BLEND automatically. This behavior is the same across platforms
  (not OHOS-specific), so it has no page of its own; see the notes in the problems page.
