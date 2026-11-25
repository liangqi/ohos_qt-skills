# fetch-deps — one-step fetching of HarmonyOS artifacts for an app's dependencies (agent tool)

Given a Qt application that has already been scanned into the database, fetches in one step runnable artifacts on HarmonyOS (arm64-v8a /
OpenHarmony) for **all of its dependencies**, and generates a machine-readable manifest. Aimed at AI agents
automating cross-compilation: no HarmonyOS device and no brew needed; it runs directly on any platform (Windows/Linux/macOS).

```bash
python portgraph.py fetch-deps <app> [--out DIR] [--force] [--dry-run] [--json]
```

---

## Typical agent workflow

```bash
# ① Preview first: what's in the closure, what can be downloaded, what needs porting (nothing written to disk)
python portgraph.py fetch-deps sample-app --dry-run

# ② Once acceptable, run the download (artifacts land in workspace/ohos-libs/, a cache shared across apps)
python portgraph.py fetch-deps sample-app

# ③ Read the manifest to get integration parameters (CMAKE_PREFIX_PATH, etc.)
python portgraph.py fetch-deps sample-app --json        # or read the manifest file directly
#   → workspace/ohos-libs/manifest-sample-app.json

# ④ For need_port dependencies (no artifact): take the source link and cross-compile yourself
#    (source_url / repo_url are given in each manifest entry)
```

## Parameters

| Parameter | Description |
|---|---|
| `app` | App ID or name: `sample-app` / `app:sample-app` (fuzzy match) |
| `--out DIR` | Download/unpack directory, default `workspace/ohos-libs/` (shared across apps; existing artifacts are skipped automatically) |
| `--force` | Re-download even if present (overwrites old artifacts, including brew read-only files) |
| `--jobs N` | **Number of parallel download threads (default 8)**: bottle tarballs are first prefetched in parallel into `.cache/` (cache hits are skipped automatically; reruns only fill in what's missing), then unpacked and installed serially. Measured on a weak network: serial at 57KB/s once timed out after 90 minutes; 8 parallel threads did the same amount in about 8 minutes. `0`/`1` = disable parallel prefetch |
| `--dry-run` | Only print the classified list; no download, no disk writes, no manifest |
| `--json` | At the end, print the full manifest JSON to stdout (combine with `--dry-run` for a machine-readable preview) |

## Classification semantics and agent decision table

Each dependency entry in the manifest has a `status`; the agent decides according to this table:

| status | Meaning | What the agent should do |
|---|---|---|
| `downloaded` | Downloaded and unpacked successfully in this run (the bottle passed sha256 verification) | Nothing; the path is in `installed` |
| `already_local` | Already available locally (an artifact from a previous fetch, or `artifact_local`) | Nothing; the path is in `installed` |
| `covered` | The artifact for a same-named package was already fetched by another data source's node (hb:/cmdpkgs: dedup; the dedup key is the normalized name with the lib prefix stripped, so aliases of the same library such as qrencode/libqrencode are downloaded only once) | Nothing; the path is in `installed` |
| `provided` | Qt module / platform API, provided by the Qt SDK / HarmonyOS framework; CMake built-in modules (OpenMP/Threads/iconv/dl) also fall here (they ship with the OHOS NDK/SDK; explained in `note`) | Don't download; deployed with Qt for HarmonyOS / the NDK |
| `cmd_only` | No direct link (the formula's version couldn't be resolved), only a command to obtain it | Run `artifact_cmd` on a HarmonyOS device; or look up the formula, fill in the version, and construct the direct bottle link |
| `need_port` | No HarmonyOS artifact; you must cross-compile it yourself | Take `source_url`/`repo_url`, fetch the source and port it; whether it can be ported to HarmonyOS depends on `port_status` and the recursive analysis |
| `test` | Test framework (GTest/Catch2, etc.), not shipped | Nothing for the release package; prepare it only if you need to run tests on a HarmonyOS device |
| `failed` | Download failed (404 / network / sha256 mismatch) | Retry; if it still fails, check whether the URL is stale and fall back to building from source |
| `would_download` | Only in dry-run: will be downloaded | Decide whether to run the real download |
| `target` | The app node itself | The analysis target |

## Manifest structure

`workspace/ohos-libs/manifest-<app>.json` (overwritten on every real run):

```jsonc
{
  "app": {"id": "app:sample-app", "name": "sample-app"},
  "generated_at": "2026-09-09T12:00:00",
  "out_dir": "workspace/ohos-libs",
  "closure_size": 35,                      // total number of nodes in the dependency closure
  "summary": {"downloaded": 27, "provided": 5, "cmd_only": 2, "target": 1},
  "roles": {"link": 8, "runtime": 21, "provided": 5, "target": 1},
  "deps": [                                 // one entry per node in the closure
    {
      "id": "hb:openssl@3", "name": "openssl@3", "kind": "package",
      "version": "3.6.4", "port_status": "ported",
      "status": "downloaded", "role": "link",
      // role (by closure depth): link=declared directly by the app (needed to compile/link)
      //                    runtime=transitive dependency (device-side .so)
      //                    provided=Qt module; target=the app itself
      //                    test=test framework (not shipped)
      //                    build-tool=CMake built-in / host build tool
      //                    (OpenMP ships with the NDK; ECM just needs installing on the build machine)
      //                    vendored=dependency with bundled source (require_source_dep;
      //                    built with the project source, not downloaded or drilled into)
      // For precise classification with version ranges/REQUIRED semantics, use the `deps` command's report
      "artifact_url": "https://harmonybrew.atomgit.com/bottles/openssl@3-3.6.4.arm64_ohos.bottle.tar.gz",
      "sha256": "verified",
      "installed": "workspace/ohos-libs/openssl@3/3.6.4",
      "libs": ["ssl", "crypto"],            // list of -l link names
      "hints": { "cmake": "...", "qmake": "...", "deploy": "..." },
      "symlinks_fixed": ["lib/libssl.so.3"] // .so links materialized as copies on NTFS
    },
    {"id": "qt:gui", "kind": "qt-module", "status": "provided",
     "role": "provided", "note": "…"},
    {"id": "hb:xxx", "status": "need_port", "role": "link",
     "source_url": "…", "repo_url": "…", "homepage": "…"}
  ],
  "toolchain": {
    "cmake_prefix_path": "…;…;…",           // semicolon-joined, pass directly to -DCMAKE_PREFIX_PATH
    "cmake": "cmake -S . -B build_ohos …",  // complete command, ready to copy
    "note": "NATIVE_OHOS_SDK is the native path of the local HarmonyOS SDK; …"
  }
}
```

## Cross-compilation integration

After the download, every artifact's install root (with `lib/`, `include/`, pkg-config, CMake config)
is in place under `workspace/ohos-libs/<name>/<version>/`:

```bash
cmake -S . -B build_ohos \
  -DCMAKE_TOOLCHAIN_FILE=$NATIVE_OHOS_SDK/build/cmake/ohos.toolchain.cmake \
  -DOHOS_ARCH=arm64-v8a \
  -DCMAKE_PREFIX_PATH=<manifest.toolchain.cmake_prefix_path> \
  -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH     # iron rule: must be BOTH
```

qmake projects: `LIBS += -L<installed>/lib -lfoo` (the `-l` list is in each entry's `libs`).

Deployment reminder: on a non-HarmonyOS host, `.so` files can only be **linked**, not run; when packaging, copy all
`lib/*.so` into the app's `entry/libs/arm64-v8a/` so they can be loaded on the device.

## Dependency closure rules

- Recurse along `runtime` / `uses-module` edges, skipping conditional dependencies with `platform_cond=macos`
- **Key difference from the portability verdict engine**: packages already ported to HarmonyOS (ported) are still drilled into for their
  runtime dependencies; bottles don't bundle dependencies, so linking/running on the target still needs the `.so` files they depend on
- `build` / `test` dependencies are host build tools (cmake/nasm run on the build machine); they aren't
  target-side artifact requirements and aren't downloaded
- Qt modules are provided and not expanded (their dependencies ship with the Qt SDK)

## Artifact sources

| Source | URL form | Verification |
|---|---|---|
| Harmonybrew bottle | `https://harmonybrew.atomgit.com/bottles/<name>-<ver>[_rev].arm64_ohos.bottle[.rebuild].tar.gz` | sha256 (digest built into the formula) |
| cmd-pkgs prebuilt packages | `https://gitcode.com/OpenHarmonyPCDeveloper/cmd-pkgs/releases/download/pkgs/<name>-<ver>-ohos-aarch64.tar.gz` | No digest provided by the source (`sha256: n/a`) |

When a same-named package has nodes in both sources, it is deduplicated automatically (first come, first served) and the other node is marked `covered`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (including when need_port/cmd_only entries exist; they are information, not errors) |
| 1 | The app doesn't exist; or there are `failed` entries (at least one download failed; can be retried) |

## Reliability details

- **Atomic placement**: unpack into `.staging/` first and move into the final directory only on success. A failure midway
  (network loss, disk error, antivirus briefly locking a file) leaves no half-finished artifact, and a rerun won't mistake an incomplete
  artifact for "ready"
- **Windows read-only files**: CMake config files in brew artifacts are often read-only (mode 444);
  write permission is restored automatically when overwriting/deleting
- **Retry on transient file locks**: antivirus scanning a just-written file can cause PermissionError;
  retried automatically 3 times
- **NTFS symlinks**: `.so` links inside a bottle are materialized as copies of the target file, so that
  `-lfoo` can be resolved by the OHOS cross linker
- **Idempotent**: repeated runs skip artifacts that are ready; `--force` forces a re-download
- After a successful download, the node's `artifact_local` is written back and becomes visible on the web graph's detail page

## Related commands

| Command | Relationship |
|---|---|
| `fetch <pkg,...>` | Download one or more bottles by package name manually (the underlying capability of fetch-deps) |
| `analyze <app> --summary` | Portability verdict + blockers (answers "can it be ported"); fetch-deps answers "how do I get the dependency artifacts" |
| `deps <path\|app>` | Comprehensive dependency analysis (answers "the full dependency picture: role classification + version ranges"); its runtime transitive-closure rules match this command's |
| `serve` | Web graph; the artifact_local written back by fetch-deps is shown in node details |
