import copy
import json
import tempfile
import unittest
from pathlib import Path
from test_review import fixture
from review import analyse, run
from compose_decisions import compose, validate_plan


def plan_for(audit):
    fid = next(f['id'] for f in audit['facts'] if f['pointer'].startswith('/DATA/synthetic-a/'))
    return {'schema_version': '1', 'shops': [{'key': 'synthetic-a', 'decisions': [{
        'title': '对账', 'assessment': '先核实', 'hypotheses': ['统计范围不同'],
        'immediate_steps': ['取同范围原表'], 'owner_role': '运营', 'due': '调整前',
        'conditional_test': '核实后再决定', 'success': '差异可解释', 'stop': '口径未明暂停',
        'missing': ['原表'], 'evidence_ids': [fid], 'knowledge_cards': ['D01']}]}]}


class DecisionsTests(unittest.TestCase):
    def test_roundtrip_and_tampered_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'input.html'
            source.write_text('\n'.join('const ' + k + ' = ' + json.dumps(v, ensure_ascii=False) + ';'
                                        for k, v in fixture().items()), encoding='utf-8')
            audit = run(source, root / 'run')
            plan = root / 'plan.json'
            plan.write_text(json.dumps(plan_for(audit), ensure_ascii=False), encoding='utf-8')
            out = root / 'decisions.html'
            self.assertTrue(compose(root / 'run', plan, out))
            self.assertTrue(compose(root / 'run', plan, out, True))
            altered = plan_for(audit)
            altered['shops'][0]['decisions'][0]['assessment'] = '篡改判断'
            plan.write_text(json.dumps(altered), encoding='utf-8')
            self.assertFalse(compose(root / 'run', plan, out, True))

    def test_cross_shop_reference_rejected(self):
        raw = fixture()
        raw['DATA']['synthetic-b'] = copy.deepcopy(raw['DATA']['synthetic-a'])
        audit = analyse(raw)
        plan = plan_for(audit)
        plan['shops'][0]['decisions'][0]['evidence_ids'] = [
            next(f['id'] for f in audit['facts'] if f['pointer'].startswith('/DATA/synthetic-b/'))]
        with self.assertRaises(ValueError):
            validate_plan(plan, audit)

    def test_unknown_card_and_missing_action_rejected(self):
        audit = analyse(fixture())
        plan = plan_for(audit)
        plan['shops'][0]['decisions'][0]['knowledge_cards'] = ['D99']
        with self.assertRaises(ValueError):
            validate_plan(plan, audit)
        plan = plan_for(audit)
        del plan['shops'][0]['decisions'][0]['stop']
        with self.assertRaises(ValueError):
            validate_plan(plan, audit)
