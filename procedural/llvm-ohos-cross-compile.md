---
id: procedural-llvm-ohos-cross-compile
type: procedural
domain: tech
tags: [llvm, cross-compile, ohos, qt, qlogo, cmake, aarch64, jit]
created: 2026-08-06
updated: 2026-08-14
status: active
audience: public
refs: [semantic-qt-harmonyos-build, semantic-qt-harmonyos-third-party-libs]
summary: >
  The adapter for consuming OHOS arm64 LLVM 15 static libraries from Qt/QLogo: which libraries the Qt target links,
  the library closure QLogo's JIT needs, deployment, and regression checks. The general OHOS NDK/LLVM cross-compilation
  process is maintained in the common knowledge base.
leader_summary: >
  Consolidated the LLVM 15 OHOS cross-compilation knowledge into a QLogo/Qt integration adapter, avoiding duplicate maintenance of the platform toolchain process in the Qt KB.
impact: [Migration efficiency]
deliverables: [Qt integration guide, QLogo library list]
evidence: [WORKLOG 08-05, workspace/llvm-15.0.7.src/]
---

# Consuming OHOS LLVM artifacts from Qt/QLogo

> For the OHOS NDK toolchain, separating host and target generators, ELF/dependency-closure checks, and the general LLVM failure taxonomy, the authority is the common knowledge base's [[ohos-common-kb/procedural/ohos-llvm-cross-compile|Cross-compiling LLVM-style native projects for OHOS]] ([standalone link](https://gitcode.com/OpenHarmonyPCDeveloper/ohos_qt-skills/blob/main/ohos-common-kb-public/procedural/ohos-llvm-cross-compile.md)). This page covers only how Qt/QLogo consumes verified AArch64 artifacts.

## Why:

QLogo's JIT depends on several LLVM static libraries. "How to build LLVM" on the platform side and "which libraries to link, how they get into the HAP, and how to verify the JIT" on the Qt side are two different seams; only the latter belongs in the Qt KB.

## How to apply:

1. Follow the common process to obtain LLVM 15.0.7 AArch64 static libraries built with the same OHOS SDK/ABI, and confirm `Machine: AArch64` with `llvm-readelf -h`.
2. Put only the `.a` files QLogo actually needs into a project-controlled target library directory; don't drag the host `llvm-tblgen` or Windows libraries into the Qt target link.
3. Configure the include paths and static libraries on the Qt application target; preserve the LLVM library dependency order, and when linking fails, work backwards from the last undefined symbol to find the missing component.
4. After building the HAP, check the Qt main library's `NEEDED` entries, exported symbols, and the final package contents.
5. Run a minimal QLogo/JIT case on a real device. If you hit an executable-memory permission problem, handle it via the common platform limitations page — don't copy signing/profile conclusions onto this page.

## Verified library set for the QLogo JIT

| Library | Purpose |
|---|---|
| `libLLVMOrcJIT.a` | ORC JIT core |
| `libLLVMCore.a`, `libLLVMSupport.a` | IR and base infrastructure |
| `libLLVMIRReader.a`, `libLLVMExecutionEngine.a` | IR parsing and the execution engine |
| `libLLVMCodeGen.a`, `libLLVMAArch64CodeGen.a` | AArch64 code generation |
| `libLLVMAnalysis.a`, `libLLVMScalarOpts.a` | Analysis and optimization passes |
| `libLLVMInstCombine.a`, `libLLVMTransformUtils.a` | Instruction and transformation utilities |
| `libLLVMAsmPrinter.a`, `libLLVMTarget.a` | Assembly output and Target base |
| `libLLVMCoroutines.a` | Coroutine support |

This list comes from the QLogo verification; it doesn't mean every Qt application must link all of them. Trim it based on your actual unresolved symbols and feature entry points.

## Qt CMake integration

```cmake
set(LLVM_OHOS_ROOT "<validated-llvm-ohos-prefix>")
target_include_directories(QLogo PRIVATE "${LLVM_OHOS_ROOT}/include")
target_link_directories(QLogo PRIVATE "${LLVM_OHOS_ROOT}/lib")
target_link_libraries(QLogo PRIVATE
  LLVMOrcJIT LLVMExecutionEngine LLVMIRReader LLVMCore
  LLVMAArch64CodeGen LLVMCodeGen LLVMAnalysis LLVMScalarOpts
  LLVMInstCombine LLVMTransformUtils LLVMAsmPrinter LLVMTarget LLVMSupport
)
```

Base the library order and set on the targets/dependencies your current LLVM build actually produces; regenerate the link closure after upgrading LLVM rather than guessing from the old list.

## Qt acceptance

- [ ] The Qt application consumes only OHOS AArch64 `.a` files, with no host artifacts mixed in.
- [ ] `find_package(Qt*)` and the LLVM prefix don't override each other; the Qt SDK still comes from the existing Kit / `CMAKE_PREFIX_PATH`.
- [ ] The main Qt native library links successfully with no host absolute paths/RPATHs.
- [ ] The HAP installs and launches successfully.
- [ ] The minimal QLogo JIT case passes on a real device; any permission denial produces clear logs and routes to the common problem page.

## Evidence boundary

The 2026-08-05 verification baseline was LLVM 15.0.7, OHOS NDK clang 15.0.4, AArch64, producing roughly 69 static libraries. This page only asserts the consumption relationship of the libraries listed above in the QLogo scenario. Other LLVM versions, components, or JIT permissions need re-verification.
