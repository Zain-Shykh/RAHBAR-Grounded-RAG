#!/usr/bin/env python3
"""Prove the Chroma and Redis Stack assumptions from docs/architecture/architecture.md section 9.

Items 1 and 2 run against `make dev-services` (Chroma :8100, Redis :6379).
Items 3 and 4 start throwaway hardened containers (non-root, read-only root) and need docker;
until the desktop is re-logged run the whole script as:
    sg docker -c ".venv/bin/python scripts/verify_services.py"

Spec: docs/specs/phase-02-local-services.md. Prints PASS / FAIL / SKIP per check, exit 1 on any FAIL.
Everything it creates is named verify* / rahbar-verify-* and is removed afterwards.
"""

import argparse
import array
import json
import os
import random
import subprocess
import sys
import time
import urllib.request
import uuid

import chromadb
import redis

CHROMA_IMAGE = os.environ.get("CHROMA_IMAGE", "chromadb/chroma:1.0.12")
REDIS_IMAGE = os.environ.get("REDIS_IMAGE", "redis/redis-stack-server:7.4.0-v8")
DIM = 768
fails = 0
prefix = ""


def check(name, fn):
    """Run fn; it returns a detail string or raises. Prints one PASS/FAIL line."""
    global fails
    try:
        detail = fn() or ""
        print(f"PASS  {prefix}{name}" + (f": {detail}" if detail else ""))
        return True
    except Exception as e:  # a failed check must not stop the others
        fails += 1
        print(f"FAIL  {prefix}{name}: {type(e).__name__}: {e}")
        return False


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def vec(rng):
    return [rng.random() - 0.5 for _ in range(DIM)]


# ---------------------------------------------------------------- item 1: Chroma
def chroma_checks(host, port):
    rng = random.Random(7)
    global fails
    try:
        client = chromadb.HttpClient(host=host, port=port)  # connects in the constructor
        client.heartbeat()
    except Exception as e:
        fails += 1
        print(f"FAIL  chroma: cannot reach {host}:{port} ({type(e).__name__}); run `make dev-services`")
        return

    def wipe():
        for c in client.list_collections():
            name = c if isinstance(c, str) else c.name
            if name.startswith("verify"):
                client.delete_collection(name)

    wipe()
    meta = {"hnsw:space": "cosine", "embed_model": "verify-768", "index_id": "20260101T000000Z-aaaaaa",
            "doc_versions": json.dumps([{"source": "a.pdf", "doc_version": "2026", "superseded": False}])}
    state = {}
    try:
        def c11():
            state["col"] = client.create_collection("verify_a", metadata=meta)
            need(state["col"].metadata == meta, f"metadata not stored as given: {state['col'].metadata}")

        def c12():
            return f"server max batch size = {client.get_max_batch_size()}"

        def c13():
            n = 500
            state["col"].add(
                ids=[f"id{i}" for i in range(n)], embeddings=[vec(rng) for _ in range(n)],
                documents=[f"text {i}" for i in range(n)],
                metadatas=[{"source": "a.pdf", "section": "1", "page": i, "doc_version": "2026",
                            "superseded": False} for i in range(n)])
            need(state["col"].count() == n, f"count={state['col'].count()}")
            return "500 records in one add"

        def c14():
            state["col"].modify(name="verify_b")
            names = [c if isinstance(c, str) else c.name for c in client.list_collections()]
            need("verify_a" not in names and "verify_b" in names, f"names={names}")
            col = client.get_collection("verify_b")
            need(col.count() == 500, f"count after rename={col.count()}")
            need(col.metadata == meta, f"metadata changed: {col.metadata}")
            return "rename keeps count and metadata"

        def c15():
            client.create_collection("verify_swap", metadata={**meta, "index_id": "old"})
            nxt = client.create_collection("verify_swap_next", metadata={**meta, "index_id": "new"})
            client.delete_collection("verify_swap")
            nxt.modify(name="verify_swap")
            got = client.get_collection("verify_swap")
            need(got.metadata["index_id"] == "new", f"index_id={got.metadata}")
            return "stage, delete live, rename: new index_id live"

        def c16():
            col = client.create_collection("verify_f", metadata={"hnsw:space": "cosine"})
            vs = [("2026", False), ("2023", True)] * 10
            col.add(ids=[f"f{i}" for i in range(20)], embeddings=[vec(rng) for _ in range(20)],
                    documents=["x"] * 20,
                    metadatas=[{"doc_version": v, "superseded": s} for v, s in vs])
            q = [vec(rng)]
            r = col.query(query_embeddings=q, n_results=20, where={"superseded": False})
            need(len(r["ids"][0]) == 10 and all(not m["superseded"] for m in r["metadatas"][0]), "bool filter")
            r = col.query(query_embeddings=q, n_results=20, where={"doc_version": {"$in": ["2023"]}})
            need(len(r["ids"][0]) == 10 and all(m["doc_version"] == "2023" for m in r["metadatas"][0]), "$in filter")
            return "where superseded=False and doc_version $in work"

        def c17():
            wipe()
            names = [c if isinstance(c, str) else c.name for c in client.list_collections()]
            need(not [n for n in names if n.startswith("verify")], f"left over: {names}")

        for n, f in (("1.1 create collection with metadata", c11), ("1.2 batch limit", c12),
                     ("1.3 add 500 in one call (A-3)", c13), ("1.4 rename via modify(name=) (A-2)", c14),
                     ("1.5 stage-and-swap sequence (A-2)", c15), ("1.6 where filters (AD-11)", c16),
                     ("1.7 delete_collection", c17)):
            check(n, f)
    finally:
        try:
            wipe()
        except Exception:
            pass


# ---------------------------------------------------------------- item 2: Redis Stack
def redis_checks(host, port):
    global fails
    r = redis.Redis(host=host, port=port)
    try:
        r.ping()
    except Exception as e:
        fails += 1
        print(f"FAIL  redis: cannot reach {host}:{port} ({type(e).__name__}); run `make dev-services`")
        return
    idx = "idx:cache:verify"
    rng = random.Random(11)
    va, vb = vec(rng), vec(rng)
    fb = lambda v: array.array("f", v).tobytes()  # noqa: E731

    def drop():
        try:
            r.execute_command("FT.DROPINDEX", idx, "DD")
        except redis.ResponseError:
            pass
        for k in r.scan_iter("cache:verify:*"):
            r.delete(k)

    drop()
    try:
        def c21():
            r.execute_command("FT.CREATE", idx, "ON", "HASH", "PREFIX", "1", "cache:verify:", "SCHEMA",
                              "scope", "TAG", "embedding", "VECTOR", "HNSW", "6", "TYPE", "FLOAT32",
                              "DIM", str(DIM), "DISTANCE_METRIC", "COSINE")

        def c22():
            r.hset("cache:verify:a", mapping={"scope": "a", "embedding": fb(va), "response": "{}"})
            r.hset("cache:verify:b", mapping={"scope": "b", "embedding": fb(vb), "response": "{}"})

        def knn(vector, scope):
            res = r.execute_command("FT.SEARCH", idx, f"(@scope:{{{scope}}})=>[KNN 1 @embedding $vec AS dist]",
                                    "PARAMS", "2", "vec", fb(vector), "DIALECT", "2")
            need(res[0] == 1, f"hits={res[0]}")
            fields = dict(zip(res[2][::2], res[2][1::2]))
            return res[1].decode(), 1 - float(fields[b"dist"])

        def c23():
            key, sim = knn(va, "a")
            need(key == "cache:verify:a" and sim >= 0.999, f"key={key} sim={sim}")
            key2, sim2 = knn(va, "b")
            need(key2 == "cache:verify:b" and sim2 < 0.999, f"tag filter ignored: {key2} {sim2}")
            return f"same vector sim={sim:.4f}; scope tag filters (other scope sim={sim2:.3f})"

        def c24():
            r.expire("cache:verify:a", 60)
            need(0 < r.ttl("cache:verify:a") <= 60, f"ttl={r.ttl('cache:verify:a')}")

        def c25():
            need(idx.encode() in r.execute_command("FT._LIST"), "index not listed")
            r.execute_command("FT.DROPINDEX", idx, "DD")
            need(r.exists("cache:verify:a", "cache:verify:b") == 0, "DD left entries")
            need(idx.encode() not in r.execute_command("FT._LIST"), "index still listed")
            return "DROPINDEX DD removes index and entries"

        ok = check("2.1 FT.CREATE HNSW cosine 768 + TAG", c21)
        if ok:
            for n, f in (("2.2 HSET float32 vectors", c22), ("2.3 KNN 1 DIALECT 2 with tag filter", c23),
                         ("2.4 entry TTL", c24), ("2.5 FT._LIST and FT.DROPINDEX DD", c25)):
                check(n, f)
        else:
            print("      (no vector search module? this is not redis-stack-server)")
    finally:
        drop()


# ---------------------------------------------------------------- items 3 and 4: hardened
def docker(*args, check_rc=False):
    p = subprocess.run(["docker", *args], capture_output=True, text=True)
    if check_rc and p.returncode:
        raise RuntimeError(f"docker {' '.join(args[:3])}: {p.stderr.strip()[-300:]}")
    return p


def docker_ok():
    try:
        return docker("info").returncode == 0
    except FileNotFoundError:
        return False


def wait_for(fn, seconds=40):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def hardened(label, image, uid, host_port, inner_port, env, ready, functional):
    """Discover what a non-root container writes, then prove it runs read-only with only those paths."""
    global fails, prefix
    tag = uuid.uuid4().hex[:6]
    name, vol = f"rahbar-verify-{label}-{tag}", f"rahbar-verify-{label}-{tag}"
    envargs = [x for k, v in env.items() for x in ("-e", f"{k}={v}")]
    base = ["run", "-d", "--name", name, "--user", str(uid), "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "-p", f"127.0.0.1:{host_port}:{inner_port}",
            "-v", f"{vol}:/data", *envargs]

    def start(extra, nm):
        docker("rm", "-f", name)
        b = list(base)
        b[b.index("--name") + 1] = nm
        p = docker(*b[:2], *extra, *b[2:], image)
        need(p.returncode == 0, p.stderr.strip()[-300:])
        if not wait_for(ready):
            logs = docker("logs", "--tail", "6", nm)
            raise AssertionError("not ready: " + (logs.stdout + logs.stderr).strip()[-400:])

    try:
        user = docker("image", "inspect", "-f", "{{.Config.User}}", image).stdout.strip()
        check("3.1 image default user", lambda: f"User={user or '(root)'}")
        docker("volume", "create", vol, check_rc=True)
        # A non-empty, chowned volume stands in for Kubernetes fsGroup (an empty one is overwritten by copy-up).
        docker("run", "--rm", "-v", f"{vol}:/data", "alpine:3", "sh", "-c",
               f"touch /data/.keep && chown -R {uid}:{uid} /data", check_rc=True)
        found = {}

        def discover():
            start([], name)
            functional()
            lines = docker("diff", name).stdout.splitlines()
            outside = [ln for ln in lines if not ln.split(" ", 1)[1].startswith("/data")]
            found["lines"] = outside
            return f"{len(lines)} paths changed, outside /data: {[ln for ln in outside] or 'none'}"

        if not check("3.2 discovery (not read-only)", discover):
            return
        # tmpfs for the parent directory of every added path (never the root, never /tmp twice)
        tmpfs = sorted({os.path.dirname(ln[2:]) for ln in found["lines"] if ln.startswith("A ")} - {"/", "/tmp"})

        def confirm():
            extra = ["--read-only", "--tmpfs", "/tmp"]
            for t in tmpfs:
                extra += ["--tmpfs", t]
            start(extra, name)
            functional()
            return f"uid={uid}, --read-only, volume at /data, tmpfs /tmp + {tmpfs or 'nothing else'}"

        docker("rm", "-f", name)
        check("3.3 confirmation (read-only root, caps dropped)", confirm)
    finally:
        docker("rm", "-f", name)
        docker("volume", "rm", vol)


def http_ok(url):
    return urllib.request.urlopen(url, timeout=2).status == 200


def main():
    global prefix
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=os.environ.get("CHROMA_HOST", "localhost"))
    ap.add_argument("--chroma-port", type=int, default=int(os.environ.get("CHROMA_PORT", 8100)))
    ap.add_argument("--redis-port", type=int, default=int(os.environ.get("REDIS_PORT", 6379)))
    ap.add_argument("--uid", type=int, default=10001)
    ap.add_argument("--skip-docker", action="store_true", help="skip the hardened items 3 and 4")
    a = ap.parse_args()

    chroma_checks(a.host, a.chroma_port)
    redis_checks(os.environ.get("REDIS_HOST", a.host), a.redis_port)

    if a.skip_docker or not docker_ok():
        print("SKIP  items 3 and 4: " + ("--skip-docker" if a.skip_docker else "docker not usable (try sg docker -c ...)"))
    else:
        for old in docker("ps", "-aq", "--filter", "name=rahbar-verify-").stdout.split():
            docker("rm", "-f", old)
        print("--- item 3: Redis Stack hardened (R-02)")
        prefix = "[redis] "
        hardened("redis", REDIS_IMAGE, a.uid, 6380, 6379, {"REDIS_ARGS": "--appendonly yes"},
                 lambda: redis.Redis(port=6380).ping(), lambda: redis_checks("localhost", 6380))
        print("--- item 4: Chroma hardened (R-01)")
        prefix = "[chroma] "
        hardened("chroma", CHROMA_IMAGE, a.uid, 8101, 8000,
                 {"IS_PERSISTENT": "TRUE", "PERSIST_DIRECTORY": "/data", "ANONYMIZED_TELEMETRY": "FALSE"},
                 lambda: http_ok("http://localhost:8101/api/v2/heartbeat"), lambda: chroma_checks("localhost", 8101))
    print(f"\n{'FAILED: ' + str(fails) + ' check(s)' if fails else 'ALL CHECKS PASSED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
