---
id: problem-build-clang15-libcpp15-cpp20-gaps
type: problem
domain: build
tags: [clang15, libc++15, c++20, P1091, P0960, P0634, stop_token, atomic_ref, ranges, third-party-library-compat]
created: 2026-09-11
updated: 2026-09-11
status: solved
severity: high
audience: public
refs: [semantic-qt-harmonyos-platform-limits, semantic-qt-harmonyos-build]
summary: >
  The 8 kinds of systematic gaps, with item-by-item compatible rewrites (including a complete stop_token/atomic_ref polyfill approach),
  hit when compiling a large modern C++20 project (with its own bundled base libraries) with the OHOS NDK's clang 15/libc++ 15.
leader_summary: >
  One page capturing the C++20 capability boundary of clang15/libc++15, so new projects hitting the same kind of error can fix it straight from the table
impact: [Build system, Third-party library porting]
deliverables: [problem record]
evidence: []

error_message: >
  error: reference to local binding 'X' declared in enclosing function   (lambda capturing a structured binding)
  error: no matching constructor for initialization of 'TextWithEntities' (P0960)
  error: missing 'typename' prior to dependent type name              (P0634)
  fatal error: 'stop_token' file not found                             (absent from libc++)
  error: no member named 'atomic_ref' in namespace 'std'               (only in libc++19)
  error: no member named 'any_of' in namespace 'std::ranges'
  error: overload resolution selected deleted operator '<=>'          (shared_ptr member)
  error: 'type' declared as a pointer to a reference of type 'void &' (variant<QString>)
error_code: ""
keywords: [clang15, libc++15, c++20, structured binding, aggregate initialization, stop_token, atomic_ref, ranges, operator<=>, variant]
symptoms: "Modern C++20 code fails to compile across the board under the OHOS NDK, while the same code compiles fine with desktop clang/gcc"

environment: "OHOS NDK (clang 15.0.4 + libc++ 15, musl) cross-compiling a large C++20 project"
---

# Quick reference: C++20 gaps in clang 15 / libc++ 15 (validated on a full build of a large project)

The OHOS NDK's clang 15 lacks several language/library features compared with "standard C++20" (most are complete only in clang 16+ or
libc++ 16~19). Below are the 8 kinds of gaps hit in practice during a full build of a large project, and how to fix them.

## 1. Lambda capture of structured bindings (P1091, clang 16+)

```cpp
auto [widget, animate] = CreateLottieIcon(...);
_animate = [animate] { ... };          // ✗ error: reference to local binding
```
Fix: use an init-capture (copying in the initializer doesn't trigger a capture), or copy into an ordinary local first:
```cpp
_animate = [handler = animate] { handler(...); };        // ✓
const auto checkPtr = checkView; ... [=] { checkPtr->... } // ✓
```

## 2. Parenthesized aggregate initialization (P0960, clang 16+)

```cpp
struct TextWithEntities { QString text; EntitiesInText entities; };
return TextWithEntities(name);          // ✗ no matching constructor
```
Fix: switch to braces, `TextWithEntities{ name }`. Same family: change `make_state<Aggregate>(arg)`
to `make_state<Aggregate>(Aggregate{ arg })`.

## 3. Omitted typename (P0634, clang 16+)

```cpp
typename Result = Original::result_type                    // ✗
typename Iter = tmc::detail::range_iter<R>::type           // ✗
```
Fix: add an explicit `typename` (C++20-compatible; adding typename is always legal).

## 4. std::stop_token / jthread (missing from libc++ until 19+)

Write a complete shim yourself: implement stop_source/stop_token/stop_callback/jthread with mutex+condvar,
place it at `<repo>/ThirdParty/TooManyCooks/include/stop_token` (no extension, include_next to the real header),
and activate it with `#if defined(__OHOS__)` (or `__MUSL__`; note the toolchain predefines `__MUSL__`,
and `__OHOS__` too; confirm with `clang -dM -E` before choosing a macro).

## 5. std::atomic_ref (only in libc++ 19)

Put the polyfill in a shared compat header:
```cpp
#if defined(__cpp_lib_atomic_ref)
template <typename T> using atomic_ref = std::atomic_ref<T>;
#elif defined(__clang__) || defined(__GNUC__)
template <typename T> class atomic_ref { /* forward to __atomic_load_n/store_n/
    exchange_n/compare_exchange_n/fetch_add/fetch_sub */ };
#endif
```
At call sites, globally replace `std::atomic_ref<` with `tmc::detail::atomic_ref<`.

## 6. Missing std::ranges algorithms (libc++ 15 has only some)

`std::ranges::any_of` and friends → **see §9 first**: adding
`-D_LIBCPP_ENABLE_EXPERIMENTAL` unlocks all the ranges algorithms in one go (tested),
so there's no need to rewrite them one by one; for anything still missing, switch to range-v3's `ranges::any_of` (the project bundles
range-v3).

## 7. Defaulted operator<=> with a shared_ptr member (P1614 not implemented)

```cpp
struct Key { std::shared_ptr<X> p; int n;
  friend auto operator<=>(const Key&, const Key&) = default; };  // ✗ implicitly deleted
```
When std::less<> falls back, it selects the deleted <=> and errors out. Fix: write explicit operator==/operator<
(using std::less<shared_ptr>{} for the shared_ptr).

## 8. Constructing variant<..., QString, ...> from a QString lvalue (libc++15 __best_match bug)

`MakeInformBox({ .text = QStringValue })` triggers a
hard `__decay<void&>` error. Fix: pass the exact alternative type instead (such as `TextWithEntities{ str }`),
so best_match is unambiguous.

## 9. One-switch unlock: `-D_LIBCPP_ENABLE_EXPERIMENTAL` (tested)

The OHOS SDK's libc++15 ships with an **experimental-features switch**; add it globally:

```cmake
add_compile_definitions(_LIBCPP_ENABLE_EXPERIMENTAL)
```

Tested (validated on a full build of a large project): **16 ranges algorithms missing by default all become
available with this switch**; `<format>` is unlocked as well. This saves the per-algorithm rewrites in §6 and a large number of downgrade patches.

Still missing (the switch doesn't help; handle per the respective sections): `std::jthread`/`stop_token` (§4),
`std::expected`, `std::source_location`, `std::chrono::clock_cast`.

> Note: the switch also enables other experimental libc++ content; the ABI/behavior risk is yours. We recommend
> adding it only on the HarmonyOS target branch and keeping the downgrade paths from the individual sections as a fallback.

## Other pitfalls of the same kind

- musl has no `pthread_setaffinity_np`: guard with `TD_LINUX && defined(__GLIBC__)`
- Platform guards should use `Q_OS_HARMONY || Q_OS_OHOS` (see build-qt612-qos-harmony-macro)
- The toolchain only guarantees `__MUSL__`/`__OHOS__`; it doesn't define glibc macros
- `std::make_unique_for_overwrite` (missing from libc++15): for arrays use
  `std::unique_ptr<T[]>(new T[n])`, for single objects `std::unique_ptr<T>(new T())`
- A lambda with only init-captures (`[name = val]`) that uses `this`/members in its body
  errors under clang15: add a default capture, `[=, name = val]` (same family as §1)

## Pre-check tool (scan before compiling, instead of hitting errors one compile round at a time)

`tools/cpp20-gap-scan.py` moves the gaps above forward into **static scanning before compiling**: one full build of a large project
takes tens of minutes, so each "hit error → locate → fix" round is expensive; a pre-check finds every hit at once:

```bash
python tools/cpp20-gap-scan.py scan <src_dir>           # scan report (exit 1 if any gaps)
python tools/cpp20-gap-scan.py fix  <src_dir> --apply   # auto-fix mechanical items (dry-run by default)
```

- GAP-02 (make_unique_for_overwrite) can be auto-fixed, idempotently;
- GAP-01/03/04/05/06/07/08 are heuristic reports (no semantic analysis, a few false positives); on a hit, pre-fix them using
  the rewrites in the sections of this page;
- P0634 (typename), P0960 (parenthesized aggregates), construct_at instantiation, and variant
  best_match can only be found at compile time and are outside the scan's scope.

Where it plugs in: item 8 of the phase-zero pre-check in the migration workflow (see
`procedural/qt-app-harmonyos-migration.md`).
