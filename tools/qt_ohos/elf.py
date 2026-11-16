"""Minimal pure-Python ELF reader: header identity + DT_NEEDED.

Why not shell out to `readelf`/`llvm-readelf`? Two reasons that both bite in this
repo's actual use:

1. the gate must work on a Windows host where the OHOS toolchain may not be on
   PATH, and a missing readelf would turn "cannot check" into "looks fine";
2. the HAP check reads libraries *out of a zip* — a path-based tool would need a
   temp extraction step for every library.

Only what the gates need is implemented: class/endianness, e_type, e_machine,
PT_INTERP and the DT_NEEDED sonames (resolved through PT_LOAD + DT_STRTAB).
Anything malformed raises ValueError and the caller decides the verdict — see
`verifier._artifact_problems`.

    from qt_ohos.elf import read_elf
    info = read_elf("build-ohos/libapp.so")
    info.machine_name   # 'aarch64' / 'x86_64' / ...
    info.elf_type       # 3 == ET_DYN (shared object)
    info.needed         # ['libQt6Core.so.6', 'libssl.so.3', ...]
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# e_machine -> (name, HarmonyOS/NDK abi it belongs to)
MACHINES: Dict[int, tuple] = {
    2: ("sparc", ""),
    3: ("x86", "x86"),
    8: ("mips", ""),
    20: ("ppc", ""),
    21: ("ppc64", ""),
    40: ("arm", "armeabi-v7a"),
    62: ("x86_64", "x86_64"),
    183: ("aarch64", "arm64-v8a"),
    243: ("riscv64", "riscv64"),
}

# abi (as used by build-profile.json5 `abiFilters` / --ohos-arch) -> e_machine
ABI_MACHINE = {
    "arm64-v8a": 183, "arm64": 183, "aarch64": 183,
    "armeabi-v7a": 40, "armeabi": 40, "arm": 40,
    "x86_64": 62, "x86": 3,
    "riscv64": 243,
}

ET_NAMES = {0: "NONE", 1: "REL", 2: "EXEC", 3: "DYN", 4: "CORE"}
# ELF type a shared library must have; anything else cannot be dlopen()ed
ET_DYN = 3

_PT_LOAD, _PT_DYNAMIC, _PT_INTERP = 1, 2, 3
_DT_NULL, _DT_NEEDED, _DT_STRTAB, _DT_STRSZ, _DT_SONAME = 0, 1, 5, 10, 14
_MAX_NEEDED = 256
_MAX_STRTAB = 1 << 20


@dataclass
class ElfInfo:
    elf_class: int = 0                 # 32 or 64
    endian: str = "<"                  # struct prefix
    e_type: int = 0
    machine: int = 0
    needed: List[str] = field(default_factory=list)
    interpreter: str = ""
    soname: str = ""

    @property
    def type_name(self) -> str:
        return ET_NAMES.get(self.e_type, "0x%x" % self.e_type)

    @property
    def machine_name(self) -> str:
        return MACHINES.get(self.machine, ("em_%d" % self.machine, ""))[0]

    @property
    def abi(self) -> str:
        return MACHINES.get(self.machine, ("", ""))[1]

    @property
    def is_shared_object(self) -> bool:
        return self.e_type == ET_DYN


def read_elf(path) -> ElfInfo:
    return read_elf_bytes(Path(path).read_bytes())


def read_elf_bytes(data: bytes) -> ElfInfo:
    """Parse an ELF image held in memory (also used for libs inside a HAP)."""
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise ValueError("not an ELF file")
    ei_class, ei_data = data[4], data[5]
    if ei_class not in (1, 2) or ei_data not in (1, 2):
        raise ValueError("bad ELF ident")
    is64 = ei_class == 2
    endian = "<" if ei_data == 1 else ">"
    try:
        e_type, e_machine = struct.unpack_from(endian + "HH", data, 16)
        if is64:
            (e_phoff, e_shoff) = struct.unpack_from(endian + "QQ", data, 32)
            (e_phentsize, e_phnum) = struct.unpack_from(endian + "HH", data, 54)
        else:
            (e_phoff, e_shoff) = struct.unpack_from(endian + "II", data, 28)
            (e_phentsize, e_phnum) = struct.unpack_from(endian + "HH", data, 42)
    except struct.error as exc:
        raise ValueError("truncated ELF header (%s)" % exc)

    info = ElfInfo(elf_class=64 if is64 else 32, endian=endian,
                   e_type=e_type, machine=e_machine)

    loads: List[tuple] = []            # (vaddr, filesz, offset)
    dynamic: Optional[tuple] = None    # (offset, filesz)
    for index in range(min(e_phnum, 128)):
        base = e_phoff + index * e_phentsize
        try:
            if is64:
                p_type, _flags, p_offset, p_vaddr, _pa, p_filesz, _memsz, _al = \
                    struct.unpack_from(endian + "IIQQQQQQ", data, base)
            else:
                p_type, p_offset, p_vaddr, _pa, p_filesz, _memsz, _flags, _al = \
                    struct.unpack_from(endian + "IIIIIIII", data, base)
        except struct.error:
            break
        if p_type == _PT_LOAD:
            loads.append((p_vaddr, p_filesz, p_offset))
        elif p_type == _PT_DYNAMIC:
            dynamic = (p_offset, p_filesz)
        elif p_type == _PT_INTERP and p_filesz:
            info.interpreter = _cstr(data, p_offset, p_filesz)

    if dynamic is None:
        return info

    entries = _dynamic_entries(data, dynamic, is64, endian)
    strtab_va = entries.get(_DT_STRTAB)
    strsz = entries.get(_DT_STRSZ) or 0
    needed_offsets = entries.get(_DT_NEEDED) or []
    if strtab_va is None or not needed_offsets:
        return info
    str_off = _vaddr_to_offset(strtab_va, loads)
    if str_off is None:
        return info
    limit = min(strsz or _MAX_STRTAB, _MAX_STRTAB)
    for rel in needed_offsets[:_MAX_NEEDED]:
        name = _cstr(data, str_off + rel, limit - rel if limit > rel else 0)
        if name:
            info.needed.append(name)
    soname_off = entries.get(_DT_SONAME)
    if isinstance(soname_off, int) and soname_off < limit:
        info.soname = _cstr(data, str_off + soname_off, limit - soname_off)
    return info


def _dynamic_entries(data: bytes, dynamic: tuple, is64: bool,
                     endian: str) -> Dict[int, object]:
    offset, filesz = dynamic
    entry_size = 16 if is64 else 8
    fmt = endian + ("qQ" if is64 else "iI")
    result: Dict[int, object] = {}
    end = min(offset + filesz, len(data))
    cursor = offset
    while cursor + entry_size <= end:
        tag, val = struct.unpack_from(fmt, data, cursor)
        cursor += entry_size
        if tag == _DT_NULL:
            break
        if tag == _DT_NEEDED:
            result.setdefault(_DT_NEEDED, []).append(val)
        else:
            result.setdefault(tag, val)
    return result


def _vaddr_to_offset(vaddr: int, loads: List[tuple]) -> Optional[int]:
    for seg_vaddr, seg_size, seg_offset in loads:
        if seg_vaddr <= vaddr < seg_vaddr + seg_size:
            return seg_offset + (vaddr - seg_vaddr)
    return None


def _cstr(data: bytes, offset: int, limit: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = data.find(b"\x00", offset, min(len(data), offset + max(limit, 1)))
    if end < 0:
        end = min(len(data), offset + 256)
    return data[offset:end].decode("utf-8", errors="replace")


def describe_mismatch(info: ElfInfo, expected_abi: str = "") -> str:
    """One-line reason a library cannot run on the target, or "" when it can."""
    if not info.is_shared_object:
        return "ELF type=%s（需要 DYN 共享对象）" % info.type_name
    if expected_abi:
        want = ABI_MACHINE.get(expected_abi.strip().lower())
        if want is not None and info.machine != want:
            return "架构 %s（目标 %s）" % (info.machine_name, expected_abi)
    return ""
