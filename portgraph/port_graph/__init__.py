"""port_graph - backend for the portability topology graph of Qt apps ported to HarmonyOS.

Standalone project: no external knowledge base dependency (Qt module status is vendored in data/,
project pre-scanning is vendored in qt_scanner.py).

Data flow: collection (Harmonybrew / cmd-pkgs / seeds / project scanning)
      -> SQLite graph data -> portability inference engine -> FastAPI / frontend graph.
"""

from pathlib import Path

# Project root (parent of this package)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT / "workspace"
DB_PATH = WORKSPACE / "portgraph.db"
# Harmonybrew formula repository (data source, used by ingest)
HB_CORE = WORKSPACE / "hb-core" / "Formula"
# cmd-pkgs repository (data source, used by ingest; cloned automatically when missing)
CMDPKGS_DIR = WORKSPACE / "cmd-pkgs"
# Locally downloaded HarmonyOS aarch64 prebuilt artifacts (<name>/<version>/, used by fetch)
OHOS_LIBS = WORKSPACE / "ohos-libs"
# Vendored data (knowledge page on Qt module HarmonyOS support status)
DATA_DIR = PROJECT_ROOT / "data"

__all__ = ["PROJECT_ROOT", "WORKSPACE", "DB_PATH", "HB_CORE", "CMDPKGS_DIR",
           "OHOS_LIBS", "DATA_DIR"]
