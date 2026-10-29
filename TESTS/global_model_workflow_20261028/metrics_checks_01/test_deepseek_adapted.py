import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import copy, hashlib, json, multiprocessing as mp, os, sqlite3, tempfile, time, unittest
import metrics

def _sha(b):
    return hashlib.sha256(b).hexdigest()

def _dump(root, name, obj):
    p = os.path.join(root, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return p

def _run(root, run_id="r1", status="COMPLETED_REVIEW_PENDING_VALIDATION", output=b"out"):
    out = os.path.join(root, run_id + ".bin")
    with open(out, "wb") as f:
        f.write(output)
    obj = {
        "schema": 1, "event": "finished", "project": root, "provider": "ollama-cloud", "truncated": status=="INCOMPLETE_LENGTH", "run_id": run_id, "task_id": "t1",
        "model": "author", "domain": "fpga", "task_type": "code",
        "difficulty": None, "dataset": None, "task_family": None,
        "model_config": {}, "status": status,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "elapsed_seconds": 1.0, "queue_delay_seconds": None,
        "output_path": out, "output_sha256": _sha(output),
    }
    return _dump(root, run_id + ".json", obj), obj

def _base_eval(root, run):
    ep = os.path.join(root, "evidence.txt")
    with open(ep, "wb") as f:
        f.write(b"evidence")
    return {
        "evaluation_id": "eval-ok", "run_id": run["run_id"],
        "evaluator_type": "model", "evaluator_id": "judge",
        "evaluator_model": "judge-v1", "rubric_version": "1", "justification": "Synthetic test acceptance verified.",
        "verdict": "accepted", "tests": "pass",
        "scores": {"correctness": 3, "relevance": 3, "completeness": 3, "actionability": 3},
        "review_seconds": 0, "rework_seconds": None,
        "evidence_path": ep, "evidence_sha256": _sha(b"evidence"),
        "output_sha256": run["output_sha256"],
    }

def _worker(db, run_path, barrier, q):
    barrier.wait()
    try:
        q.put(("ok", metrics.import_run(db, run_path)))
    except Exception as exc:
        q.put(("err", repr(exc)))

class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.db = os.path.join(self.root, "metrics.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_import_idempotent_and_bytes_conflict(self):
        rp, _ = _run(self.root)
        self.assertEqual(metrics.import_run(self.db, rp), "imported")
        self.assertEqual(metrics.import_run(self.db, rp), "duplicate")
        rp2, _ = _run(self.root, output=b"different-bytes")
        with self.assertRaises(ValueError):
            metrics.import_run(self.db, rp2)

    def test_concurrent_import_no_duplicate(self):
        rp, _ = _run(self.root, run_id="conc")
        n = 4
        ctx = mp.get_context("fork")
        q, barrier = ctx.Queue(), ctx.Barrier(n)
        ps = [ctx.Process(target=_worker, args=(self.db, rp, barrier, q)) for _ in range(n)]
        [p.start() for p in ps]
        res = [q.get(timeout=10) for _ in range(n)]
        [p.join(10) for p in ps]
        self.assertTrue(all(k == "ok" for k, _ in res), res)
        vals = [v for _, v in res]
        self.assertEqual(vals.count("imported"), 1, res)
        self.assertEqual(vals.count("duplicate"), n - 1, res)

    def test_add_evaluation_valid_returns_id(self):
        rp, run = _run(self.root, run_id="evalok")
        metrics.import_run(self.db, rp)
        ev = _base_eval(self.root, run)
        p = _dump(self.root, "eval-ok.json", ev)
        self.assertIsInstance(metrics.add_evaluation(self.db, p), int)

    def test_add_evaluation_rejects_invalid(self):
        rp, run = _run(self.root, run_id="bad")
        metrics.import_run(self.db, rp)
        base = _base_eval(self.root, run)
        cases = {
            "score": lambda e: e["scores"].__setitem__("correctness", 6),
            "self": lambda e: e.update(evaluator_id="author"),
            "ev_sha": lambda e: e.update(evidence_sha256="0" * 64),
            "out_sha": lambda e: e.update(output_sha256="f" * 64),
            "nan": lambda e: e.update(review_seconds=float("nan")),
            "neg": lambda e: e.update(rework_seconds=-1),
        }
        for name, mutate in cases.items():
            e = copy.deepcopy(base); mutate(e); e["evaluation_id"] = "bad-" + name
            p = _dump(self.root, "bad-" + name + ".json", e)
            with self.assertRaises(ValueError, msg=name):
                metrics.add_evaluation(self.db, p)

        for status in ("FAILED", "INCOMPLETE_LENGTH"):
            rp, run = _run(self.root, run_id="bad-" + status, status=status)
            metrics.import_run(self.db, rp)
            e = _base_eval(self.root, run); e["evaluation_id"] = "bad-" + status
            p = _dump(self.root, e["evaluation_id"] + ".json", e)
            with self.assertRaises(ValueError, msg=status):
                metrics.add_evaluation(self.db, p)

    def test_sql_injection_fields_are_data(self):
        payload = "x'); DROP TABLE runs;--"
        rp, run = _run(self.root, run_id=payload)
        self.assertEqual(metrics.import_run(self.db, rp), "imported")
        self.assertEqual(metrics.import_run(self.db, rp), "duplicate")
        ev = _base_eval(self.root, run); ev["evaluation_id"] = payload
        p = _dump(self.root, "eval-inj.json", ev)
        self.assertIsInstance(metrics.add_evaluation(self.db, p), int)

if __name__=="__main__": unittest.main(verbosity=2)
