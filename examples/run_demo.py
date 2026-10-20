"""Generate an entirely synthetic business report; no account access or real store data."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/douyin-commerce-review/scripts'))
from review import run, digest
from verify_run import verify
from compose_decisions import compose


def demo(directory):
    out = Path(directory).resolve()
    if out.exists():
        raise ValueError('Choose a new demo output directory')
    out.mkdir(parents=True)
    data = {'schema_version':'1', 'provenance':[{'origin':'fully_synthetic', 'locator':'examples/run_demo.py',
            'mapping_note':'Invented fixture, not platform data'}], 'shops':{'demo-shop':{
        'name':'合成演示店', 'period':'演示周期',
        'live':{'sessions':[{'_k':'DEMO-A','d':'演示日甲','gmv':'240','ord':'3','view':'30'},
                            {'_k':'DEMO-B','d':'演示日乙','gmv':'360','ord':'5','view':'40'}],
                'funnel':[{'k':'成交订单数','v':'9'},{'k':'直播间观看次数','v':'60'}]},
        'products':[{'name':'合成商品甲','pay':'600','refund':'180'}]}}}
    source = out / 'synthetic-input.json'
    source.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    audit = run(source, out / 'audit', input_format='canonical', as_of='合成演示，无真实经营日期')
    facts = {f['pointer']:f['id'] for f in audit['facts']}
    def fid(path):
        return facts['/DATA/demo-shop/' + path]
    first = dict(id='DEMO-CHECK', priority='P0', title='核实逐场与汇总订单范围',
        assessment='合成数据中明细与汇总不一致；这是核查线索，不能先判定经营恶化。',
        priority_reason='这是后续场次比较的前提，资料范围小，适合优先完成。',
        hypotheses=['可能是统计窗口或视角不同，需用原表说明区分。'], immediate_steps=['取同窗口逐场与周表，逐项记录字段定义、过滤条件及未解释差异。'],
        owner_role='运营与数据分析（建议）', due='下一次场次决策前（建议）',
        deliverable='一张含口径、明细、汇总和未解释差异的对账表。', task_acceptance='差异有原表解释；无法解释的部分明确保留未知。',
        conditional_test='对账后再比较匹配货盘和时长的场次。', success='在可比条件下评价结果，不能用对账完成证明成交改善。',
        stop='仍有范围冲突则停止场次优劣推断。', missing=['逐场和汇总原表及字段说明 → 用于解释差异。'],
        evidence_ids=[fid('live/funnel/0/v')], calculation_ids=['C0002'], knowledge_cards=['D02'], depends_on=[],
        data_highlights=[{'label':'明细订单合计（合成）','ref':'C0002'},{'label':'周表订单显示（合成）','ref':fid('live/funnel/0/v')}],
        experiment={'primary_metric':'可比场次每小时贡献（需成本）','baseline':None,'target':None,'sample_rule':None,'cost_limit':None,'window':'待业务确认，覆盖足够可比场次'})
    second = dict(id='DEMO-PRODUCT', priority='P1', title='先核退款批次，再试排品',
        assessment='支付与退款快照只能提供核查线索，差额不等于利润。商品资料整理可与对账并行。',
        priority_reason='候选经营动作需要更多证据；先完成能独立取得的商品卡。',
        hypotheses=['成本与退款观察龄会影响主推判断。'], immediate_steps=['整理商品支付批次、售后阶段和成本缺口；未知字段留空。'],
        owner_role='货品运营（建议）', due='排品试验前（建议）', deliverable='一张带缺口与数据来源的商品贡献核查卡。',
        task_acceptance='原值可回查，成本和批次未知项已标明。', conditional_test='等待场次口径及商品成本确认，再设计可比排品试验。',
        success='同观察龄贡献改善且退款和库存没有恶化；当前未验证。', stop='口径、成本未齐或库存变化时暂停试验。',
        missing=['商品成本与同龄退款 → 用于贡献判断；不影响先登记原始资料。'],
        evidence_ids=[fid('products/0/pay'),fid('products/0/refund')], calculation_ids=['C0004'], knowledge_cards=['D04','D05'],
        depends_on=['DEMO-CHECK'], data_highlights=[{'label':'支付快照（合成）','ref':fid('products/0/pay')},
                                                   {'label':'支付减退款快照，非利润（合成）','ref':'C0004'}],
        experiment={'primary_metric':'同龄商品贡献（需成本）','baseline':None,'target':None,'sample_rule':None,'cost_limit':None,'window':'按实际退款稳定过程确认'})
    plan = {'schema_version':'2','summary':'完全虚构的演示数据，用来体验核查、依赖和交付格式，不用于经营判断。',
            'business_context':{'objective':None,'capacity':None,'recent_changes':[], 'working_assumption':'先确认可比性，再讨论经营试验；这是演示假设。'},
            'focus_actions':['DEMO-CHECK'], 'shops':[{'key':'demo-shop','decisions':[first,second]}]}
    plan_path = out / 'plan.json'
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    compose(out / 'audit', plan_path, out / 'decisions.html')
    assert verify(out / 'audit')['ok']
    assert compose(out / 'audit',plan_path,out / 'decisions.html',verify_only=True)
    feedback = {'schema_version':'1','plan_sha256':digest(plan_path),'updates':[{
        'action_id':'DEMO-CHECK','status':'todo','note':'合成反馈示例，尚无真实执行。','outcome':'not_evaluated','evidence':[]}]}
    (out / 'feedback-example.json').write_text(json.dumps(feedback,ensure_ascii=False,indent=2),encoding='utf-8')
    return out / 'decisions.html'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=Path('private/demo'))
    print(demo(p.parse_args().out))
