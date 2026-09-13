---
id: executable-binary-eacces
title: "Executable inside a HAP fails to start: execve EACCES"
status: active
confidence: 0.7
sources: [{type: experience, name: "Python/Node/Java hap-bin, on-device verification", date: 2026-08-05}]
created: 2026-08-13
updated: 2026-08-15
last_confirmed: 2026-08-05
superseded_by: null
tags: [problem, runtime, execve, eacces, executableBinaryPaths, signing]
refs: [application-sandbox-paths, native-runtime-embedding]
summary: "An ELF binary inside a HAP hits execve EACCES because executableBinaryPaths wasn't declared, the signing/permission/profile is incomplete, or the path is viewed from the wrong namespace."
audience: public
error_message: |
  execve(...) = -1 EACCES (Permission denied)
  chmod(...) = -1 EPERM (Operation not permitted)
---

# Executable inside a HAP fails to start: execve EACCES

## Error message

```text
execve(<bundle binary>, ...) -> EACCES / Permission denied
chmod(<bundle binary>, 0755) -> EPERM / Operation not permitted
```

## Scenario

The application puts a Python, Node, Java, or other ELF binary inside the HAP and it fails to start. Even when the file exists, a failure in any one of execute permission, platform declaration, signature integrity, or mount namespace can surface as "Permission denied".

## Cause

Work through these in order:

1. `module.json5` doesn't declare the target binary via `executableBinaryPaths`, so it has no execute attribute after installation.
2. The binary is self-signed or lacks the profile/permission information the platform requires, so integrity verification rejects it.
3. The application used a path that is only visible in the hdc shell namespace.
4. The binary's ABI, interpreter, or dynamic dependencies don't resolve, and the error gets flattened into a generic startup failure at a higher level.

## Solution

```json5
{
  "module": {
    "extractNativeLibs": true,
    "executableBinaryPaths": [
      { "path": "libs/arm64-v8a/<binary>" }
    ]
  }
}
```

Then rebuild, re-sign, uninstall the old application, and do a clean install. Don't `chmod` bundle files from application code. If the binary already has the execute attribute and is still rejected, use the target SDK's signature inspection tooling to check the profile, permissions, and certificate chain, and cross-check the bundleName/device grant. Don't write certificates, passwords, or profile contents into logs or the knowledge base.

## Prevention

Add executable declarations, signature checks, ELF/dependency checks, and a fresh-install launch to your release gate. `.so` files loaded via `dlopen` do not need to be added to executableBinaryPaths.
