import math, unittest
from collections import defaultdict

W = {"correctness": 40, "relevance": 25, "completeness": 20, "actionability": 15}
F = list(W)
G = ("domain", "task_type", "difficulty", "model", "rubric_version")

def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def _merge(data, extra):
    out = {}
    if isinstance(data, dict):
        out.update(data)
    out.update(extra)
    return out

def weighted_score(scores=None, **extra):
    d = _merge(scores, extra)
    vals = [d.get(k) for k in F]
    if any(v is None for v in vals):
        return None
    for v in vals:
        if not _finite(v) or not 0 <= v <= 5:
            raise ValueError("invalid score")
    return sum(W[k] * d[k] for k in F) / 100.0

def _clean_durations(values):
    out = []
    for v in values:
        if v is None:
            continue
        if not _finite(v) or v < 0:
            raise ValueError("invalid duration")
        out.append(v)
    return out

def nearest_rank(values, p):
    data = sorted(_clean_durations(values))
    if not data:
        return None
    rank = min(max(math.ceil(p / 100.0 * len(data)), 1), len(data))
    return data[rank - 1]

def median_duration(values):
    return nearest_rank(values, 50)

def p90_duration(values):
    return nearest_rank(values, 90)

def group_key(record):
    return tuple(record.get(k) for k in G)

def run_status(record):
    if record.get("infrastructure_failure") is True or record.get("status") == "infrastructure_failure":
        return "infrastructure_failure"
    if record.get("truncated") is True or record.get("status") == "truncated":
        return "truncated"
    if (record.get("evaluated") is True or record.get("status") == "evaluated"
            or record.get("evaluation") is not None or record.get("weighted_score") is not None):
        return "evaluated"
    return "unevaluated"

def group_counts(records):
    result = defaultdict(lambda: {"evaluated": 0, "unevaluated": 0, "infrastructure_failures": 0,
                                 "truncated": 0, "total": 0})
    for r in records:
        d = result[group_key(r)]
        d["total"] += 1
        s = run_status(r)
        if s == "infrastructure_failure":
            d["infrastructure_failures"] += 1
        elif s == "truncated":
            d["truncated"] += 1
        elif s == "evaluated":
            d["evaluated"] += 1
        else:
            d["unevaluated"] += 1
    return {k: dict(v) for k, v in result.items()}

def latest_by_run(evaluations):
    out = {}
    keys = {}
    for i, e in enumerate(evaluations):
        rid = e["run_id"]
        sid = e.get("evaluation_id", e.get("id"))
        key = (e.get("created_at") is not None, e.get("created_at"), sid is not None, sid, i)
        if rid not in out or key > keys[rid]:
            out[rid] = e
            keys[rid] = key
    return list(out.values())

def evaluated_records(records):
    return [r for r in records if run_status(r) == "evaluated"]

def suggestion_status(records):
    ev = evaluated_records(records)
    tasks = {r.get("task_id") for r in ev}
    tasks.discard(None)
    if len(ev) >= 10 and len(tasks) >= 3:
        return "eligible"
    return "insufficient evidence"

def can_suggest(records):
    return suggestion_status(records) == "eligible"

class TestCompactMetrics(unittest.TestCase):
    def test_null(self):
        self.assertIsNone(weighted_score())
        self.assertIsNone(weighted_score({"correctness": None, "relevance": 1, "completeness": 2, "actionability": 3}))
        self.assertIsNone(median_duration([None]))
        self.assertIsNone(p90_duration([]))

    def test_single(self):
        self.assertEqual(median_duration([4.2]), 4.2)
        self.assertEqual(p90_duration([4.2]), 4.2)

    def test_p90_boundaries(self):
        self.assertEqual(p90_duration(list(range(1, 11))), 9)
        self.assertEqual(p90_duration([1, 2, 3, 4]), 4)

    def test_forbidden(self):
        with self.assertRaises(ValueError):
            weighted_score({"correctness": True, "relevance": 1, "completeness": 2, "actionability": 3})
        with self.assertRaises(ValueError):
            weighted_score({"correctness": float("nan"), "relevance": 1, "completeness": 2, "actionability": 3})
        with self.assertRaises(ValueError):
            p90_duration([float("nan")])
        with self.assertRaises(ValueError):
            p90_duration([-1])

    def test_threshold_boundary(self):
        nine = [{"status": "evaluated", "task_id": i % 3} for i in range(9)]
        ten = [{"status": "evaluated", "task_id": i % 3} for i in range(10)]
        two_tasks = [{"status": "evaluated", "task_id": i % 2} for i in range(10)]
        self.assertEqual(suggestion_status(nine), "insufficient evidence")
        self.assertEqual(suggestion_status(two_tasks), "insufficient evidence")
        self.assertEqual(suggestion_status(ten), "eligible")
        self.assertTrue(can_suggest(ten))

if __name__ == "__main__":
    unittest.main()
