---
id: ohos-gstreamer-cross-compile
title: Cross-compiling GStreamer for OHOS
status: active
confidence: 0.5
sources: [{type: experience, name: "Qt KB GStreamer OHOS cross-compilation and application verification", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-13
last_confirmed: 2026-08-05
review_by: null
superseded_by: null
tags: [ohos, gstreamer, meson, cross-compile, multimedia]
refs: [ohos-native-third-party-libraries]
summary: "Cross-compiling GStreamer core/plugins for OHOS, trimming features, deploying dependencies, and verifying a minimal pipeline."
audience: public
---

# Cross-compiling GStreamer for OHOS

## Why:

GStreamer is a combination of core, plugins, a registry, and external codecs. Producing a set of `.so` files alone does not prove the target capability works, and Linux desktop backends, scanners, and runtime plugin discovery cannot simply be carried over.

## How to apply:

1. Pin the GStreamer/subproject versions, the OHOS SDK/NDK, the ABI, and the list of codecs/features you need.
2. Prepare a Meson cross file and make sure the C/C++ compiler, ar, strip, and pkg-config sysroot all point at the OHOS target.
3. Build a minimal core/base first, then enable good/bad/ugly/libav and other components as needed; disable inapplicable backends such as ALSA, X11, and Wayland.
4. Record the origin, license, build flags, and target artifact for every external dependency.
5. Deploy the core, the plugins you need, and every `NEEDED` dependency into the HAP's native library directory.
6. Set a controlled plugin-discovery path on the target device, and verify that the registry builds and a minimal pipeline runs.
7. Verify each real codec/source/sink separately; a successful `gst_init` is not a substitute for accepting media functionality.

## Minimal verification matrix

- Core: initialization, version query, empty pipeline
- Plugins: the target plugin is enumerable and its dependency closure is complete
- typefind/demux/decoder: verify negotiation with one known input
- Sink: choose an OHOS-supported backend or an output adapter provided by the application
- Fresh package: verify from a clean HAP, without relying on the dev machine's registry/cache

## Adapter boundary

How QtMultimedia, a Tauri plugin, Java bindings, or any other framework consumes GStreamer stays in the framework repository. This page does not cover application-specific patches or framework module/plugin behavior.
