import copy
import json
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from test_review import SCRIPTS

sys.path.insert(0, str(SCRIPTS.parents[2] / 'examples'))
from run_demo import demo
from compose_decisions import compose, validate_plan, render
from review import digest


class V2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'demo'
        demo(self.root)
        self.plan_path = self.root / 'plan.json'
        self.plan = json.loads(self.plan_path.read_text(encoding='utf-8'))
        self.audit = json.loads((self.root / 'audit/audit.json').read_text(encoding='utf-8'))

    def test_documented_demo_replays_and_refuses_overwrite(self):
        self.assertTrue(compose(self.root/'audit', self.plan_path, self.root/'decisions.html', True))
        with self.assertRaises(ValueError):
            demo(self.root)

    def test_cycle_rejected(self):
        self.plan['shops'][0]['decisions'][0]['depends_on'] = ['DEMO-PRODUCT']
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            validate_plan(self.plan, self.audit)

    def test_invalid_focus_or_dependency_rejected(self):
        for field in ['focus_actions','depends_on']:
            p = copy.deepcopy(self.plan)
            if field == 'focus_actions':
                p[field] = ['MISSING']
            else:
                p['shops'][0]['decisions'][0][field] = ['MISSING']
            with self.assertRaises(ValueError):
                validate_plan(p, self.audit)

    def test_cross_shop_dependency_rejected(self):
        p = copy.deepcopy(self.plan)
        other = copy.deepcopy(p['shops'][0])
        other['key'] = 'other-shop'
        for d in other['decisions']:
            d['id'] = 'OTHER-' + d['id']
            d['depends_on'] = []
            d['calculation_ids'] = []
            d['evidence_ids'] = ['OTHER-F']
            d['data_highlights'] = [{'label':'合成其他店字段','ref':'OTHER-F'}]
        a = copy.deepcopy(self.audit)
        a['shops'].append({'key':'other-shop'})
        a['facts'].append({'id':'OTHER-F','pointer':'/DATA/other-shop/name','raw':'合成乙','kind':'reported_field'})
        p['shops'].append(other)
        p['shops'][0]['decisions'][0]['depends_on'] = [other['decisions'][0]['id']]
        with self.assertRaisesRegex(ValueError, 'same shop'):
            validate_plan(p, a)

    def test_highlight_cannot_invent_a_value(self):
        self.plan['shops'][0]['decisions'][0]['data_highlights'][0]['ref'] = 'C9999'
        with self.assertRaisesRegex(ValueError, 'Highlight'):
            validate_plan(self.plan, self.audit)

    def test_wrong_types_and_duplicate_ids_rejected(self):
        p = copy.deepcopy(self.plan)
        p['shops'][0]['decisions'][0]['immediate_steps'] = '不能将文字当成逐字任务'
        with self.assertRaises(ValueError):
            validate_plan(p, self.audit)
        p = copy.deepcopy(self.plan)
        p['shops'][0]['decisions'][1]['id'] = p['shops'][0]['decisions'][0]['id']
        with self.assertRaises(ValueError):
            validate_plan(p, self.audit)

    def test_unknown_experiment_fields_must_be_explicit(self):
        del self.plan['shops'][0]['decisions'][0]['experiment']['cost_limit']
        with self.assertRaises(ValueError):
            validate_plan(self.plan, self.audit)

    def test_generated_navigation_targets_exist(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.targets = set(), []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids.add(attrs['id'])
                if tag == 'a' and attrs.get('href', '').startswith('#'):
                    self.targets.append(attrs['href'][1:])
        parser = Links()
        parser.feed((self.root/'decisions.html').read_text(encoding='utf-8'))
        self.assertTrue(parser.targets)
        self.assertTrue(set(parser.targets) <= parser.ids)

    def test_context_and_feedback_html_is_escaped(self):
        self.plan['business_context']['objective'] = '<script>alert(1)</script>'
        output = render(self.plan, self.audit)
        self.assertNotIn('<script>', output)
        self.assertIn('&lt;script&gt;', output)
        feedback = self.feedback()
        feedback['updates'][0]['note'] = '<img src=x onerror=alert(1)>'
        compose(self.root/'audit',self.plan_path,self.root/'escaped.html',feedback_path=self.write_feedback(feedback))
        output = (self.root/'escaped.html').read_text(encoding='utf-8')
        self.assertNotIn('<img', output)
        self.assertIn('&lt;img', output)

    def feedback(self):
        return json.loads((self.root/'feedback-example.json').read_text(encoding='utf-8'))

    def write_feedback(self, data):
        p = self.root / 'feedback.json'
        p.write_text(json.dumps(data, ensure_ascii=False),encoding='utf-8')
        return p

    def test_feedback_requires_matching_plan(self):
        f = self.feedback()
        f['plan_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'different plan'):
            compose(self.root/'audit', self.plan_path, self.root/'new.html', feedback_path=self.write_feedback(f))

    def test_done_requires_proof_and_is_not_automatically_effective(self):
        f = self.feedback()
        u = f['updates'][0]
        u.update(status='done', recorded_at='2026-01-01')
        with self.assertRaisesRegex(ValueError, 'deliverable evidence'):
            compose(self.root/'audit',self.plan_path,self.root/'new.html',feedback_path=self.write_feedback(f))
        proof = self.root / 'proof.txt'
        proof.write_text('Synthetic deliverable, no business results.',encoding='utf-8')
        u['evidence'] = [{'path':'proof.txt','sha256':digest(proof)}]
        fp = self.write_feedback(f)
        self.assertEqual(u['outcome'], 'not_evaluated')
        self.assertTrue(compose(self.root/'audit',self.plan_path,self.root/'new.html',feedback_path=fp))
        self.assertTrue(compose(self.root/'audit',self.plan_path,self.root/'new.html',True,fp))
        proof.write_text('altered',encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'missing or changed'):
            compose(self.root/'audit',self.plan_path,self.root/'new.html',True,fp)

    def test_observed_change_needs_comparison_and_cannot_claim_causality(self):
        f = self.feedback()
        proof = self.root / 'proof.txt'
        proof.write_text('Synthetic observations',encoding='utf-8')
        u = f['updates'][0]
        u.update(status='done', recorded_at='2026-01-01', outcome='observed_change', evidence=[{'path':'proof.txt','sha256':digest(proof)}])
        with self.assertRaises(ValueError):
            compose(self.root/'audit',self.plan_path,self.root/'new.html',feedback_path=self.write_feedback(f))
        u.update(window='合成同龄观察窗口',comparison='促销同时变化，仅为观察比较')
        self.assertTrue(compose(self.root/'audit',self.plan_path,self.root/'new.html',feedback_path=self.write_feedback(f)))
        u['outcome'] = 'proven_causal_success'
        with self.assertRaises(ValueError):
            compose(self.root/'audit',self.plan_path,self.root/'other.html',feedback_path=self.write_feedback(f))
