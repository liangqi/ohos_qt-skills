# compatibleSdkVersion does not match the local SDK

> ID: build-fix-08
> Date: 2026-10-10 (updated based on actual build)
> Files involved: `build-profile.json5`
> Project root: `QtBugDemo-official/`
> Status: Fixed (build passes)

## 1. Error

When `.hvigor/cache` contains a cache from an older version, the hvigor configuration phase reports:

```
00303168 Configuration Error: SDK component missing.
   at HmosSdkLoader.getHmosSdkComponents (.../hmos-sdk-loader.js)
```

> This build (after clearing the cache) did not trigger the error, but the version mismatch is still a risk:
> hvigor may hit the stale cache during an incremental build and report `SDK component missing`.

## 2. Root cause

`build-profile.json5`:

```json5
"compatibleSdkVersion": "6.0.0(20)",
```

Local DevEco SDK (measured from `sdk-pkg.json`):

```
"platformVersion": "6.1.1",
"apiVersion": "24",
```

hvigor parses `6.0.0(20)` → there is no local `6.0.0` component (only `6.1.1`) →
on a cache hit it reports `SDK component missing`.

## 3. Fix

```json5
"compatibleSdkVersion": "6.1.1(24)",
```

> HarmonyOS mode enforces the `X.Y.Z(API)` string format.

## 4. Troubleshooting

When you hit `SDK component missing` (00303168), also check:

1. **Version number** (this document): whether `compatibleSdkVersion` matches the local SDK
2. **Directory level** (related to build-fix-10): whether `DEVECO_SDK_HOME` points to the **parent directory**
   that contains the `default/` subdirectory
3. **Cache**: clear `.hvigor/cache` and retry (`rm -rf .hvigor/cache`)

## Auto-fix

```yaml
match: "SDK component missing|00303168"
files:
  - build-profile.json5
actions:
  - type: replace
    from: '"compatibleSdkVersion": "6.0.0(20)"'
    to: '"compatibleSdkVersion": "6.1.1(24)"'
```
