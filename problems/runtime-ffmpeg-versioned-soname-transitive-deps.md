---
id: problem-runtime-ffmpeg-versioned-soname-transitive-deps
type: problem
domain: runtime
tags: [ffmpeg, dlopen, soname, stub, harmonybrew, arm64-ohos]
created: 2026-08-24
updated: 2026-08-24
status: solved
severity: critical
audience: public
refs: [semantic-qt-harmonyos-third-party-libs, procedural-fetch-ohos-third-party-lib]
summary: >
  The NEEDED entries of Harmonybrew's prebuilt FFmpeg .so files reference versioned SONAMEs (libavcodec.so.63 and friends)
  plus a long list of transitive dependencies (libvpx/libdav1d/liblzma/libx264/libx265/libopus/libSvtAv1Enc/libbz2/libasound/libxcb/libz.so.1).
  The OHOS dynamic linker resolves every NEEDED entry and symbol immediately at load time, so any missing one makes dlopen fail.
  Fix: copy all the versioned .so files + pull libz.so.1 from the device + create empty stub .so files for unavailable codecs.
leader_summary: >
  Captured a complete transitive-dependency deployment approach for prebuilt FFmpeg bottles on OHOS, avoiding cascading dlopen failures.
impact: [Migration efficiency, Build troubleshooting, Runtime troubleshooting]
deliverables: [problem record, HAP]
evidence: [QCTools running on device, devecocli run logs]

error_message: >
  dlopen() failed to open library 'libOhosApp.so': Error loading shared library libavcodec.so.63
  dlopen() failed to open library 'libOhosApp.so': Error loading shared library libvpx.so.12
  dlopen() failed to open library 'libOhosApp.so': Error loading shared library libz.so.1
  Error relocating libavcodec.so.63: opus_multistream_decoder_create: symbol not found
  Error relocating libavcodec.so.63: svt_av1_enc_parse_parameter: symbol not found
error_code: ""
keywords: [ffmpeg, dlopen, NEEDED, SONAME, stub, harmonybrew, libz, libvpx, libopus, libx264]
symptoms: The application crashes immediately after launch, with hilog showing dlopen failed or symbol not found
environment: Qt 5.15.16 OHOS SDK (arm64-v8a), FFmpeg 9.0.1 (Harmonybrew), OHOS 5.0.0(12) device
---

# Deploying prebuilt FFmpeg .so files and their transitive dependencies on OHOS

## Error messages

```
# Stage 1: the versioned SONAME wasn't deployed
dlopen() failed: Error loading shared library libavcodec.so.63: (needed by libOhosApp.so)

# Stage 2: a transitive dependency is missing
dlopen() failed: Error loading shared library libvpx.so.12: (needed by libavcodec.so.63)

# Stage 3: the system library isn't visible in the namespace
dlopen() failed: Error loading shared library libz.so.1: (needed by libavcodec.so.63)

# Stage 4: the stub library is missing symbols (OHOS resolves symbols eagerly)
Error relocating libavcodec.so.63: opus_multistream_decoder_create: symbol not found
```

## Scenario

Linking a Harmonybrew prebuilt FFmpeg bottle (`fetch-ohos-bottle.sh -f ffmpeg`) into a Qt OHOS application: the build succeeds, but dlopen fails at runtime.

## Cause

1. **Versioned SONAMEs**: the FFmpeg `.so` NEEDED entries reference `libavcodec.so.63` (versioned), while CMakeLists.txt only copied `libavcodec.so` (no version suffix)
2. **Transitive dependencies**: `libavcodec.so.63` NEEDs `libvpx.so.12`/`libdav1d.so.7`/`liblzma.so.5`/`libx264.so.165` and others; Harmonybrew fetched some but not all of them
3. **libz namespace**: the device has `/usr/lib/libz.so.1`, but the application namespace (`namespace=ndk no inherits`) can't reach system library paths
4. **Eager symbol resolution on OHOS**: the OHOS dynamic linker resolves every symbol at dlopen time (no lazy binding), so an empty stub library with no exported symbols fails relocation

## Solution

### 1. Copy all the versioned .so files
In CMakeLists.txt, use `file(GLOB ... *.so*)` instead of hard-coded file names so you cover `libavcodec.so`, `libavcodec.so.63`, `libavcodec.so.63.1.101`, and so on.

### 2. Copy the Harmonybrew transitive dependencies
```cmake
file(GLOB _ALL_SO_FILES
    "${_OHOS_LIBS_ROOT}/ffmpeg/*/lib/lib*.so*"
    "${_OHOS_LIBS_ROOT}/dav1d/*/lib/lib*.so*"
    "${_OHOS_LIBS_ROOT}/lame/*/lib/lib*.so*"
    "${_OHOS_LIBS_ROOT}/libvpx/*/lib/lib*.so*"
    "${_OHOS_LIBS_ROOT}/mpg123/*/lib/lib*.so*"
    "${_OHOS_LIBS_ROOT}/libvmaf/*/lib/lib*.so*"
    "${_OHOS_LIBS_ROOT}/openssl/*/lib/lib*.so*"
)
```

### 3. Pull libz.so.1 from the device
```bash
hdc file recv /usr/lib/libz.so.1.2.13 ohos-stubs/libz.so.1
```
The device has libz.so.1, but it isn't visible in the application's namespace, so copy it into `entry/libs/arm64-v8a/`.

### 4. Create stub .so files that export symbols for unavailable codecs
Use the OHOS cross-compiler to create empty implementations containing every NEEDED symbol:
```bash
CLANG=aarch64-unknown-linux-ohos-clang
# libopus stub
cat > opus_stub.c << 'EOF'
#define S(x) int x(){return -1;}
S(opus_multistream_decode) S(opus_multistream_decoder_create) ...
EOF
$CLANG -shared -o libopus.so.0 opus_stub.c -Wl,-soname,libopus.so.0
```
You'll need stubs for libopus, liblzma (with versioned symbols @XZ_5.0), libbz2, libasound (with versioned symbols @ALSA_0.9), libSvtAv1Enc, libx264, libx265, libxcb, libxcb-shm, libxcb-shape, and libxcb-xfixes.

Scan the UND symbols of every FFmpeg `.so` with `llvm-readelf --dyn-syms`, group them by library-name prefix, and generate complete stubs.

## Notes

- **The FFmpeg .a files are unusable**: Harmonybrew's `.a` files weren't compiled with `-fPIC`, so linking them into a `.so` reports `relocation R_AARCH64_ADR_PREL_PG_HI21 cannot be used`. You must use the `.so` files.
- **Runtime risk from stubs**: stubs return 0/-1, so FFmpeg calls into the x264/x265 encoders will fail — but decoding and analysis features are unaffected.
- **libz.so.1 version**: it must be pulled from the target device; different devices may have different versions.
- **Versioned symbols**: liblzma's symbols carry the `@XZ_5.0` version tag and libasound has `@ALSA_0.9` and `@ALSA_0.9.0rc4`, so the stubs must match using `-Wl,--version-script`.

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured a complete transitive-dependency deployment approach for prebuilt FFmpeg bottles on OHOS, solving cascading dlopen failures |
| Scope of impact | Every Qt OHOS application migration that depends on FFmpeg |
| Deliverables | problem record, QCTools HAP running on a device |
| Evidence | QCTools running on a device with a live PID, and hilog free of dlopen errors |
| How to reuse | Match against this page whenever you hit `dlopen failed` together with an FFmpeg-related error |

## Related

- [[semantic-qt-harmonyos-third-party-libs]] — Guide to porting third-party libraries to HarmonyOS
- [[procedural-fetch-ohos-third-party-lib]] — Fetching Harmonybrew bottles
