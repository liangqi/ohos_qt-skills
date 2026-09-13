---
id: problem-build-fail-magic-enum-bracket-depth
type: problem
domain: build
tags: [magic-enum, bracket-depth, clang, fold-expression, cmake]
created: 2026-08-08
updated: 2026-08-08
status: solved
severity: medium
audience: public
refs: [semantic-qt-harmonyos-golden-rules]
summary: >
  A C++ project using magic_enum fails to build under OHOS clang: the fold expression's nesting
  exceeds clang's default bracket-depth limit (256). Adding -fbracket-depth=1000 in CMakeLists fixes it.
leader_summary: >
  Captured the fix for the magic_enum fold-expression bracket-depth build failure on OHOS clang.
impact: [Build troubleshooting, Migration efficiency]
deliverables: [problem record]
evidence: [xi-qt build log]

error_message: >
  fatal error: bracket depth exceeded in evaluation of expression
  note: use -fbracket-depth=N to increase maximum nesting level
  constexpr int num_valid = ((valid[I] ? 1 : 0) + ...);
error_code: ""
keywords: [magic_enum, bracket-depth, fold-expression, fbracket-depth, clang]
symptoms: "\"bracket depth exceeded\" when compiling a source file that uses magic_enum"

environment: "macOS / OHOS clang 15 / Qt 5.15.16 OHOS SDK / magic_enum header-only"
---

# magic_enum fold expression exceeds the bracket-depth limit

## Error message

```
magic_enum.hpp:162:51: note: use -fbracket-depth=N to increase maximum nesting level
  constexpr int num_valid = ((valid[I] ? 1 : 0) + ...);
                                                  ^
1 error generated.
```

## Scenario

The xi-qt project uses magic_enum (a header-only enum reflection library). In `line_cache.cpp`, `to_enum<xi::Op>` triggers `magic_enum::enum_cast`, which internally expands into a 257-element fold expression — beyond clang's default bracket-depth of 256.

## Cause

For large enums (xi::Op has 257 values), magic_enum uses a C++17 fold expression to expand every enum value. clang defaults to `fbracket-depth=256`, and the fold expression's nesting exceeds that limit.

## Solution

Add the compile option to the target in CMakeLists.txt:

```cmake
target_compile_options(<target> PRIVATE -fbracket-depth=1000)
```

## Notes

- Only affects projects that use magic_enum and have enums with many values
- GCC's default bracket-depth is higher, so desktop platforms may not hit this
- A value of 1000 is enough to cover most enums

## Results

| Field | Content |
|-------|---------|
| Leadership summary | Captured the fix for the magic_enum fold-expression bracket-depth build failure on OHOS clang |
| Scope of impact | Qt-to-HarmonyOS migrations that use magic_enum |
| Deliverable | problem record |
| Evidence | xi-qt build log |
| How to reuse | Build reports `bracket depth exceeded` and you use magic_enum → add `-fbracket-depth=1000` |

## Related

- [[qt-harmonyos-golden-rules]] §1 (Build rules)
