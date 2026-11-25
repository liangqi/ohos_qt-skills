# oh-package.json5 references the deleted types/libentry and ohpm fails

> ID: build-fix-09
> Date: 2026-09-28 (based on actual build)
> Files involved: `entry/oh-package.json5`
> Project root: `QtBugDemo-official/`
> Status: Not fixed

## 1. Error

The build fails in the ohpm install phase (before CMake configuration):

```
ohpm ERROR: Run install command failed
Error: 00617301 Fetch Source Code Failed
Error Message: Fetch local folder package error,
  <YOUR_HOME>/code/.opencode/skills/qt-community-to-official/QtBugDemo-official/entry/src/main/cpp/types/libentry does not exist.
```

## 2. Root cause

### 2.1 The template references types/libentry

The template's `entry/oh-package.json5` contains:

```json5
"devDependencies": {
    "@types/libentry.so": "file:./src/main/cpp/types/libentry",
    "@types/libqohos.so": "file:./src/main/qt"
}
```

`@types/libentry.so` points to `src/main/cpp/types/libentry/`, which in the template
contains `index.d.ts` (exporting the sample function `add(a, b)`) and `oh-package.json5`.

### 2.2 migrate.py deletes types/libentry but does not update oh-package.json5

After creating the new project, `create_clone_project()` in `migrate.py` deliberately deletes the template's
libentry-related files (because the actual CMake target name differs):

```python
libentry_paths = [
    new_project_dir / "entry" / "src" / "main" / "cpp" / "hello.cpp",
    new_project_dir / "entry" / "src" / "main" / "cpp" / "types",       # ← deleted
    new_project_dir / "entry" / "oh_modules" / "@types" / "libentry.so",
]
```

Once the `types/` directory is deleted, the path referenced by
`"file:./src/main/cpp/types/libentry"` in `oh-package.json5` does not exist → ohpm reports an error.

### 2.3 The actual library name does not match

| Item | Template default | Actual value |
|------|------------------|--------------|
| CMake target | `entry` | `qtbugdemo` |
| Output .so | `libentry.so` | `libqtbugdemo.so` |
| APP_LIBRARY_NAME | `libentry.so` | `libqtbugdemo.so` |

The `@types/libentry.so` reference is meaningless for the actual project — it declares the template's sample function
`add(a, b)`, which has nothing to do with the actual native library `libqtbugdemo.so`.

## 3. Fix

Remove the `@types/libentry.so` reference from `entry/oh-package.json5`:

```diff
   "devDependencies": {
-    "@types/libentry.so": "file:./src/main/cpp/types/libentry",
     "@types/libqohos.so": "file:./src/main/qt"
   },
```

Keep `@types/libqohos.so` — the `src/main/qt/` directory exists (it contains `libqohos.d.ts`), so
that reference is valid.

## 4. Verification

After the fix, ohpm install succeeds and the build reaches the CMake configuration phase.

## Auto-fix

```yaml
match: "00617301|Fetch Source Code Failed|types/libentry does not exist"
files:
  - entry/oh-package.json5
actions:
  - type: remove_line
    pattern: '"@types/libentry.so"'
```
