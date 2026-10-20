import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/douyin-commerce-review/scripts"
sys.path.insert(0, str(SCRIPTS))
from review import analyse, at, constant, load_input, parse_number, run
from verify_run import verify


def fixture():
    return {"DATA": {"synthetic-a": {
        "name": "合成示例甲店", "period": "2026/01/05—01/11",
        "trade": {"carrier": [{"k": "短视频", "v": 0}]},
        "live": {"sessions": [
            {"_k": "S-A", "d": "01/05 09:00", "gmv": "¥200", "ord": "4", "view": "50"},
            {"_k": "S-B", "d": "01/06 09:00", "gmv": "¥300", "ord": "6", "view": "70"}],
            "minis": [{"n": "直播用户支付金额", "v": "¥480"}],
            "funnel": [{"k": "成交订单数", "v": "11"}, {"k": "直播间观看次数", "v": "100"}],
            "channels": [{"k": "短视频引流", "v": "¥60"}]},
        "products": [{"name": "合成商品甲", "pay": "¥1000", "refund": "¥500"}],
        "refund": {"lagged": {"rate": "60%", "cur": "30%", "week": "上一批次"}},
        "diagnosis": [{"t": "来源判断", "cause": "改善已经见效", "action": "增加预算"}]
    }}, "NEW": {"b1": {"crowd": {"range": "近30天"}}}, "NEWKEY": {"b1": "synthetic-a"}}


class NumberTests(unittest.TestCase):
    def test_zero_is_distinct_from_missing(self):
        self.assertEqual(parse_number(0), 0)
        self.assertEqual(parse_number("0"), 0)
        for value in [None, "", "-", "—", "未知", True, "1万+", "100-200", float("nan"), float("inf")]:
            with self.subTest(value=value):
                self.assertIsNone(parse_number(value))

    def test_currency_and_percent(self):
        self.assertEqual(parse_number("¥1,234.50"), 1234.5)
        self.assertEqual(parse_number("36.49%"), .3649)

    def test_numeric_string_overflow_stays_unknown(self):
        self.assertIsNone(parse_number('9' * 400))


class InputTests(unittest.TestCase):
    def test_literal_only_no_execution(self):
        with self.assertRaises(ValueError):
            constant('const DATA = dangerous();', "DATA", True)
        with self.assertRaises(ValueError):
            constant('const DATA = {};\nconst DATA = {};', "DATA", True)

    def test_nonfinite_json_rejected(self):
        with self.assertRaises(ValueError):
            constant('const DATA = {"x": NaN};', "DATA", True)

    def test_statement_tail_not_accepted(self):
        with self.assertRaises(ValueError):
            constant('const DATA = {} + evil();', "DATA", True)

    def test_explicit_literal_binding(self):
        self.assertEqual(constant('const NEWKEY = {b1:"synthetic-a"};', 'NEWKEY'), {"b1": "synthetic-a"})

    def test_binding_expression_tail_rejected(self):
        with self.assertRaises(ValueError):
            constant('const NEWKEY = {b1:"synthetic-a"} + other;', 'NEWKEY')

    def test_unresolved_binding_does_not_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.html"
            p.write_text('const DATA = {"a":{}};\nconst NEW = {"b":{}};\nconst NEWKEY = {b:"wrong"};', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_input(p)

    def test_canonical_requires_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "input.json"
            p.write_text('{"schema_version":"1","shops":{"a":{}}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_input(p, "canonical")

    def test_escaped_pointer(self):
        self.assertEqual(at({"a/b": {"~": [7]}}, "/a~1b/~0/0"), 7)


class AnalysisTests(unittest.TestCase):
    def test_reconciliation_preserves_both_values(self):
        result = analyse(fixture())
        shop = result["shops"][0]
        self.assertEqual(shop["ledger"]["ord"]["value"], 10)
        issue = next(x for x in shop["findings"] if x["id"] == "scope-reconciliation")
        self.assertIn("周汇总显示 11", issue["observation"])
        self.assertTrue(issue["evidence_ids"])

    def test_missing_field_invalidates_aggregate(self):
        raw = fixture()
        del raw["DATA"]["synthetic-a"]["live"]["sessions"][1]["ord"]
        self.assertIsNone(analyse(raw)["shops"][0]["ledger"]["ord"]["value"])

    def test_missing_value_does_not_become_zero(self):
        raw = fixture()
        raw["DATA"]["synthetic-a"]["live"]["sessions"][1]["ord"] = None
        self.assertIsNone(analyse(raw)["shops"][0]["ledger"]["ord"]["value"])

    def test_duplicate_session_flags_without_silent_dedup(self):
        raw = fixture()
        raw["DATA"]["synthetic-a"]["live"]["sessions"][1]["_k"] = "S-A"
        shop = analyse(raw)["shops"][0]
        self.assertEqual(shop["ledger"]["session_count"], 2)
        self.assertIn("不唯一", shop["findings"][0]["observation"])

    def test_observation_not_merged_across_periods(self):
        raw = fixture()
        saved = copy.deepcopy(raw)
        result = analyse(raw)
        self.assertEqual(raw, saved)
        self.assertTrue(any(x["id"] == "mixed-windows" for x in result["shops"][0]["findings"]))

    def test_refund_decline_not_claimed_as_proven_effect(self):
        shop = analyse(fixture())["shops"][0]
        issue = next(x for x in shop["findings"] if x["id"] == "refund-cohort")
        self.assertIn("不能确认", issue["observation"])
        self.assertIn("未执行", issue["execution_status"])

    def test_zero_direct_positive_indirect_kept_separate(self):
        shop = analyse(fixture())["shops"][0]
        self.assertTrue(any(x["id"] == "video-objective" for x in shop["findings"]))
        self.assertEqual(shop["product_snapshots"][0]["remaining_snapshot"], 500)
        self.assertFalse(any(c["label"] == "利润" for c in analyse(fixture())["calculations"]))

    def test_zero_session_is_not_missing(self):
        raw = fixture()
        raw["DATA"]["synthetic-a"]["live"]["sessions"][0]["gmv"] = "¥0"
        self.assertTrue(any(x["id"] == "zero-session" for x in analyse(raw)["shops"][0]["findings"]))

    def test_multiple_shops_and_all_group_rows_preserved(self):
        raw = fixture()
        for i in range(9):
            raw["DATA"][f"synthetic-{i}"] = copy.deepcopy(raw["DATA"]["synthetic-a"])
        self.assertEqual(len(analyse(raw)["shops"]), 10)

    def test_missing_modules_deliver_limited_output(self):
        result = analyse({"DATA": {"x": {"name": "合成空样本"}}, "NEW": {}, "NEWKEY": {}})
        self.assertEqual(result["shops"][0]["findings"], [])
        self.assertTrue(result["shops"][0]["limitations"])


class ReplayTests(unittest.TestCase):
    def setup_run(self, root):
        p = root / "input.html"
        data = fixture()
        p.write_text("\n".join(f"const {k} = {json.dumps(v, ensure_ascii=False)};" for k, v in data.items()), encoding="utf-8")
        out = root / "run"
        run(p, out, as_of="2026-10-20")
        return p, out

    def test_roundtrip_replays_every_fact_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, out = self.setup_run(Path(tmp))
            result = verify(out)
            self.assertTrue(result["ok"], result)

    def test_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, out = self.setup_run(Path(tmp))
            p.write_text(p.read_text(encoding="utf-8") + " changed", encoding="utf-8")
            self.assertFalse(verify(out)["ok"])

    def test_changed_calculation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, out = self.setup_run(Path(tmp))
            a = json.loads((out / "audit.json").read_text(encoding="utf-8"))
            a["calculations"][0]["value"] = 99999
            (out / "audit.json").write_text(json.dumps(a), encoding="utf-8")
            self.assertFalse(verify(out)["ok"])

    def test_report_injection_escaped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "input.html"
            p.write_text('const DATA = {"x":{"name":"<script>alert(1)</script>"}};', encoding="utf-8")
            run(p, root / "run")
            text = (root / "run/review.html").read_text(encoding="utf-8")
            self.assertNotIn("<script>", text)
            self.assertIn("&lt;script&gt;", text)

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p, out = self.setup_run(Path(tmp))
            with self.assertRaises(ValueError):
                run(p, out)


if __name__ == "__main__":
    unittest.main()
