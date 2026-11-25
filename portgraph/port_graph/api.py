"""FastAPI service: graph queries / analysis / scan triggering + static frontend hosting."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import (DB_PATH, db, engine, harmonybrew, cmdpkgs, kb_seed,
               project_scanner, cloner, jobs)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
RECURSE_TYPES = ("runtime", "uses-module")
MAX_FOCUS_NODES = 800


class ScanReq(BaseModel):
    path: str


class CloneReq(BaseModel):
    url: str
    name: Optional[str] = None


class IngestReq(BaseModel):
    source: str   # harmonybrew | cmdpkgs | kb


def _conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


def create_app() -> FastAPI:
    app = FastAPI(title="PortGraph - portability graph for porting Qt apps to HarmonyOS")

    @app.get("/api/stats")
    def stats():
        conn = _conn()
        try:
            return db.stats(conn)
        finally:
            conn.close()

    @app.get("/api/apps")
    def apps():
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE kind='app' ORDER BY name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @app.post("/api/scan")
    def scan(req: ScanReq):
        p = Path(req.path)
        if not p.is_dir():
            raise HTTPException(400, "path does not exist or is not a directory: %s" % req.path)
        conn = _conn()
        try:
            return project_scanner.scan_project(conn, p)
        finally:
            conn.close()

    @app.post("/api/clone")
    def clone(req: CloneReq):
        """Create a background clone+scan job and return job_id immediately (the frontend polls progress)."""
        err = cloner.validate_url(req.url)
        if err:
            raise HTTPException(400, err)
        job_id = jobs.start_clone_job(req.url, req.name)
        return {"job_id": job_id}

    @app.get("/api/job/{job_id}")
    def job_status(job_id: str):
        """Query job progress (status/stage/percent/message/result)."""
        j = jobs.get_job(job_id)
        if j is None:
            raise HTTPException(404, "job not found: %s" % job_id)
        return j

    @app.get("/api/jobs")
    def job_list():
        return jobs.list_jobs()

    @app.get("/api/analysis/{app_id:path}")
    def analysis(app_id: str):
        conn = _conn()
        try:
            try:
                return engine.analyze(conn, app_id)
            except ValueError as exc:
                raise HTTPException(404, str(exc))
        finally:
            conn.close()

    def _node_payload(conn, node_id: str, with_ifaces: bool = False):
        node = db.get_node(conn, node_id)
        if node is None:
            return None
        payload = dict(node)
        if with_ifaces:
            payload["ifaces"] = db.node_interfaces(conn, node_id)
        return payload

    @app.get("/api/graph")
    def graph(root: Optional[str] = None):
        """Focus subgraph: expanded smartly by portability - nodes already ported to HarmonyOS (ported) are
        not drilled into; unported ones are expanded recursively along dependency edges until there are
        no dependencies or all dependencies are ported."""
        conn = _conn()
        try:
            if root is None:
                row = conn.execute(
                    "SELECT id FROM nodes WHERE kind='app' "
                    "ORDER BY updated_at DESC LIMIT 1").fetchone()
                if row is None:
                    raise HTTPException(404, "no scanned app yet, run scan first")
                root = row["id"]
            if db.get_node(conn, root) is None:
                raise HTTPException(404, "node not found: %s" % root)

            visited = {root}
            frontier = [root]
            edges_out = []
            while frontier:
                nxt = []
                for n in frontier:
                    if len(visited) >= MAX_FOCUS_NODES:
                        break
                    node = db.get_node(conn, n)
                    # Already ported: dependencies are ready, no need to show them (keep the node itself)
                    if node is not None and node["port_status"] == "ported":
                        continue
                    for e in db.out_edges(conn, n):
                        edges_out.append(dict(e))
                        if e["dst"] not in visited and \
                                e["type"] in RECURSE_TYPES:
                            visited.add(e["dst"])
                            nxt.append(e["dst"])
                frontier = nxt

            # When any Qt module is in the graph, add the whole Qt aggregate (for Combo rendering)
            has_qt = any((db.get_node(conn, v) or {}).get("cluster_id")
                         == "cluster:qt" for v in list(visited))
            if has_qt:
                for r in conn.execute(
                        "SELECT id FROM nodes WHERE cluster_id='cluster:qt'"
                ).fetchall():
                    visited.add(r["id"])

            nodes = [p for p in (_node_payload(conn, v, with_ifaces=True)
                                 for v in visited) if p]
            id_set = {n["id"] for n in nodes}
            edges = [e for e in edges_out
                     if e["src"] in id_set and e["dst"] in id_set]
            return {"root": root, "nodes": nodes, "edges": edges,
                    "clusters": db.all_clusters(conn),
                    "truncated": len(visited) >= MAX_FOCUS_NODES}
        finally:
            conn.close()

    @app.get("/api/graph/full")
    def graph_full(limit: int = 0, min_degree: int = 0):
        """Full graph (optionally filtered by degree). By default only nodes with edges are returned."""
        conn = _conn()
        try:
            deg = {r["id"]: r["d"] for r in conn.execute(
                """SELECT id, d FROM (
                     SELECT src id, COUNT(*) d FROM edges GROUP BY src
                     UNION ALL SELECT dst id, COUNT(*) d FROM edges
                     GROUP BY dst)""")}
            deg2 = {}
            for k, v in deg.items():
                deg2[k] = deg2.get(k, 0) + v
            rows = conn.execute("SELECT * FROM nodes").fetchall()
            nodes = [dict(r) for r in rows
                     if deg2.get(r["id"], 0) >= max(min_degree, 1)]
            if limit and len(nodes) > limit:
                nodes.sort(key=lambda n: -deg2.get(n["id"], 0))
                nodes = nodes[:limit]
            id_set = {n["id"] for n in nodes}
            edges = [dict(r) for r in conn.execute("SELECT * FROM edges")
                     if r["src"] in id_set and r["dst"] in id_set]
            return {"nodes": nodes, "edges": edges,
                    "clusters": db.all_clusters(conn),
                    "total_nodes": len(rows), "truncated": bool(limit)}
        finally:
            conn.close()

    @app.get("/api/node/{node_id:path}")
    def node_detail(node_id: str):
        conn = _conn()
        try:
            node = db.get_node(conn, node_id)
            if node is None:
                raise HTTPException(404, "node not found: %s" % node_id)
            outs, ins = [], []
            for e in db.out_edges(conn, node_id):
                t = db.get_node(conn, e["dst"])
                outs.append({**e, "target_name": t["name"] if t else "?",
                             "target_status": t["port_status"] if t else "?",
                             "target_artifact": (engine.artifact_info(t)
                                                 if t else None)})
            for e in db.in_edges(conn, node_id):
                s = db.get_node(conn, e["src"])
                ins.append({**e, "source_name": s["name"] if s else "?",
                            "source_status": s["port_status"] if s else "?"})
            return {"node": node,
                    "artifact": engine.artifact_info(node),
                    "interfaces": db.node_interfaces(conn, node_id),
                    "deps": outs, "dependents": ins}
        finally:
            conn.close()

    @app.post("/api/ingest")
    def ingest(req: IngestReq):
        conn = _conn()
        try:
            if req.source == "harmonybrew":
                return harmonybrew.ingest(conn)
            if req.source == "cmdpkgs":
                return cmdpkgs.ingest(conn, pull=True)
            if req.source == "kb":
                return kb_seed.ingest(conn)
            raise HTTPException(400, "unknown data source: %s" % req.source)
        finally:
            conn.close()

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True),
                  name="web")
    return app
