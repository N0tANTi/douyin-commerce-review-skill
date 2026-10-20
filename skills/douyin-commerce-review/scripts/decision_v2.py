"""Action dependencies, concise business reports and evidence-bound execution feedback."""
import html
import json
import re
from pathlib import Path
from review import digest


def text(value):
    return isinstance(value, str) and bool(value.strip())


def texts(value, allow_empty=False):
    return isinstance(value, list) and (allow_empty or bool(value)) and all(text(x) for x in value)


def action_index(plan):
    return {d['id']: (s['key'], d) for s in plan['shops'] for d in s['decisions']}


def validate_v2(plan, audit):
    context = plan.get('business_context')
    if not isinstance(context, dict):
        raise ValueError('v2 requires business_context, with explicit unknowns')
    for field in ['objective', 'capacity']:
        if field not in context or not (context[field] is None or text(context[field])):
            raise ValueError('Context objective/capacity must be text or null')
    if not text(context.get('working_assumption')) or not texts(context.get('recent_changes'), True):
        raise ValueError('Context needs working_assumption and recent_changes list')
    seen = set()
    for shop in plan['shops']:
        for d in shop['decisions']:
            aid = d.get('id')
            if not isinstance(aid, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{1,40}', aid) or aid in seen:
                raise ValueError('Action IDs must be unique stable ASCII identifiers')
            seen.add(aid)
            if d.get('priority') not in {'P0', 'P1', 'P2'}:
                raise ValueError('Unknown priority')
            for field in ['priority_reason', 'deliverable', 'task_acceptance']:
                if not text(d.get(field)):
                    raise ValueError('Action needs priority reason, deliverable and task acceptance')
            if not texts(d.get('depends_on'), True):
                raise ValueError('depends_on must be a string list')
            experiment = d.get('experiment')
            if not isinstance(experiment, dict) or not text(experiment.get('primary_metric')) or not text(experiment.get('window')):
                raise ValueError('Experiment requires primary_metric and window')
            for field in ['baseline', 'target', 'sample_rule', 'cost_limit']:
                if field not in experiment or not (experiment[field] is None or text(experiment[field])):
                    raise ValueError('Unknown experiment constraints must be explicit null')
            # Human labels present raw values/calculations without typing the numbers again.
            if not isinstance(d.get('data_highlights'), list) or not d['data_highlights']:
                raise ValueError('Action requires data_highlights')
            allowed = set(d['evidence_ids'] + d.get('calculation_ids', []))
            for highlight in d['data_highlights']:
                if not isinstance(highlight, dict) or not text(highlight.get('label')) or highlight.get('ref') not in allowed:
                    raise ValueError('Highlight must cite this action evidence/calculation')
    actions = action_index(plan)
    if not texts(plan.get('focus_actions')) or len(set(plan['focus_actions'])) != len(plan['focus_actions']) or not set(plan['focus_actions']) <= set(actions):
        raise ValueError('Focus must select existing unique action IDs')
    for aid, (shop, d) in actions.items():
        for dep in d['depends_on']:
            if dep == aid or dep not in actions or actions[dep][0] != shop:
                raise ValueError('Dependencies must reference another action in the same shop')
    visiting, visited = set(), set()
    def visit(aid):
        if aid in visiting:
            raise ValueError('Cyclic action dependency')
        if aid in visited:
            return
        visiting.add(aid)
        for dep in actions[aid][1]['depends_on']:
            visit(dep)
        visiting.remove(aid)
        visited.add(aid)
    for aid in actions:
        visit(aid)


def read_feedback(path, plan_path, plan):
    if plan['schema_version'] != '2':
        raise ValueError('Feedback requires a v2 plan')
    path = Path(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != '1' or data.get('plan_sha256') != digest(plan_path):
        raise ValueError('Feedback belongs to a different plan')
    if not isinstance(data.get('updates'), list):
        raise ValueError('Feedback updates must be a list')
    actions, seen = action_index(plan), set()
    for update in data['updates']:
        aid = update.get('action_id')
        if aid not in actions or aid in seen:
            raise ValueError('Feedback references unknown/duplicate action')
        seen.add(aid)
        if update.get('status') not in {'todo', 'doing', 'done', 'paused'} or not text(update.get('note')):
            raise ValueError('Feedback requires execution status and note')
        if update.get('outcome') not in {'not_evaluated', 'insufficient', 'observed_change'}:
            raise ValueError('Feedback cannot label causal business success')
        evidence = update.get('evidence')
        if not isinstance(evidence, list):
            raise ValueError('Feedback evidence must be a list')
        for item in evidence:
            if not isinstance(item, dict) or not text(item.get('path')) or not text(item.get('sha256')):
                raise ValueError('Evidence needs path and sha256')
            source = path.parent / item['path']
            if not source.is_file() or digest(source) != item['sha256']:
                raise ValueError('Feedback evidence missing or changed')
        if update['status'] == 'done' and (not evidence or not text(update.get('recorded_at'))):
            raise ValueError('Completed tasks require deliverable evidence and recorded_at')
        if update['outcome'] == 'observed_change':
            if update['status'] != 'done' or not evidence or not text(update.get('comparison')) or not text(update.get('window')):
                raise ValueError('Observed changes need completed execution, evidence, window and comparison limits')
    return data


def render_v2(plan, audit, feedback=None):
    e = lambda x: html.escape(str(x))
    facts = {f['id']: f for f in audit['facts']}
    calculations = {c['id']: c for c in audit['calculations']}
    names = {s['key']: s['name'] for s in audit['shops']}
    actions = action_index(plan)
    updates = {u['action_id']: u for u in (feedback or {}).get('updates', [])}
    status_names = {'todo':'待执行', 'doing':'进行中', 'done':'任务已完成', 'paused':'暂停'}
    outcome_names = {'not_evaluated':'经营效果未评估', 'insufficient':'效果证据不足', 'observed_change':'观察到变化，因果未证实'}
    def value(ref):
        return facts[ref]['raw'] if ref in facts else calculations[ref]['value']
    context = plan['business_context']
    out = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>经营复盘与行动清单</title>',
           '<style>body{max-width:1080px;margin:auto;padding:28px 22px;font:16px/1.75 system-ui,"Microsoft YaHei";color:#243a31;background:#f6f8f4}h1,h2,h3{color:#164c3a}article,.panel{background:white;padding:22px;border:1px solid #d4ded5;border-radius:10px;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #d4ded5;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}small{color:#59695e}summary{cursor:pointer;font-weight:600}li{margin:6px 0}.warn{background:#fff3dc;padding:12px;border-left:4px solid #9e6818}.tag{font-size:13px;background:#edf3ea;padding:4px 8px;border-radius:4px}a{color:#185e45}details{margin:14px 0}article{scroll-margin-top:20px}@media(max-width:650px){body{padding:16px 10px}article,.panel{padding:14px}table{font-size:12px}td,th{padding:7px}}@media print{details>*{display:block}article{break-inside:auto}a{color:inherit}}</style>',
           '<h1>经营复盘与行动清单 · v0.2</h1>',
           '<p class="warn">来源快照尚待平台原表核实。以下优先级与负责人角色为建议；任务完成与经营效果分别记录。</p>',
           f'<p>{e(plan.get("summary", ""))}</p>', '<section class="panel"><h2>本轮决策背景</h2>',
           f'<p><b>业务确认的目标：</b>{e(context["objective"] or "未提供，待确认")}</p>',
           f'<p><b>本轮工作假设：</b>{e(context["working_assumption"])}</p>',
           f'<p><b>人员与预算约束：</b>{e(context["capacity"] or "未提供，未安排付费试验")}</p>',
           f'<p><b>近期经营变化：</b>{e("；".join(context["recent_changes"]) or "未提供")}</p></section>',
           '<section class="panel"><h2>优先拿走的任务</h2><p>这是一组建议。先做独立核查；依赖关系约束后续经营试验，不要求所有资料一次补齐。</p><table><tr><th>店铺 / 任务</th><th>先交什么</th><th>负责 / 建议时间</th></tr>']
    for aid in plan['focus_actions']:
        key, d = actions[aid]
        out.append(f'<tr><td>{e(names[key])}<br><a href="#{e(aid)}">{e(aid)} · {e(d["title"])}</a></td><td>{e(d["deliverable"])}</td><td>{e(d["owner_role"])}<br>{e(d["due"])}</td></tr>')
    out.append('</table></section>')
    for shop in plan['shops']:
        out.append(f'<h2>{e(names[shop["key"]])}</h2>')
        for d in shop['decisions']:
            aid = d['id']
            update = updates.get(aid)
            state = status_names[update['status']] if update else '未回收执行状态'
            out += [f'<article id="{e(aid)}"><span class="tag">{e(aid)} · {e(d["priority"])} · {e(state)}</span>',
                    f'<h3>{e(d["title"])}</h3><p><b>判断：</b>{e(d["assessment"])}</p>',
                    f'<p><b>优先理由：</b>{e(d["priority_reason"])}</p><ul>']
            for h in d['data_highlights']:
                out.append(f'<li>{e(h["label"])}：<b>{e(value(h["ref"]))}</b> <small>{e(h["ref"])}</small></li>')
            out += ['</ul><h4>现在可以做</h4><ol>' + ''.join(f'<li>{e(x)}</li>' for x in d['immediate_steps']) + '</ol>',
                    f'<p><b>交付物：</b>{e(d["deliverable"])}</p><p><b>任务验收：</b>{e(d["task_acceptance"])}</p>',
                    f'<p><b>负责角色：</b>{e(d["owner_role"])}<br><b>建议时间：</b>{e(d["due"])}</p>']
            out.append('<details><summary>进一步分析与试验条件</summary>')
            for label, field in [('候选解释','hypotheses'), ('最小补数及用途','missing')]:
                out.append(f'<p><b>{label}</b></p><ul>' + ''.join(f'<li>{e(x)}</li>' for x in d[field]) + '</ul>')
            dep_links = ', '.join(f'<a href="#{e(dep)}">{e(dep)}</a>' for dep in d['depends_on'])
            out.append(f'<p><b>后续试验依赖：</b>{dep_links or "没有其他动作依赖；仍需满足本卡条件"}。当前核查可独立开始。</p>')
            experiment = d['experiment']
            for label, field in [('满足条件后试验','conditional_test'), ('效果验收','success'), ('停止条件','stop')]:
                out.append(f'<p><b>{label}：</b>{e(d[field])}</p>')
            out.append('<table><tr><th>试验登记</th><th>当前约定</th></tr>')
            for label, field in [('主指标','primary_metric'), ('可比基线','baseline'), ('目标','target'), ('观察窗口','window'), ('样本规则','sample_rule'), ('成本上限','cost_limit')]:
                out.append(f'<tr><td>{label}</td><td>{e(experiment[field] or "待业务确认，未启动试验")}</td></tr>')
            out.append('</table></details><details><summary>展开来源与计算位置</summary><table><tr><th>编号/类型/位置</th><th>原始显示值或计算</th></tr>')
            for fid in d['evidence_ids']:
                f = facts[fid]
                kind = '来源叙述，待核验' if f['kind'] == 'source_narrative' else '来源字段，未核平台原表'
                out.append(f'<tr><td>{e(fid)} · {e(kind)}<br>{e(f["pointer"])}</td><td>{e(f["raw"])}</td></tr>')
            for cid in d.get('calculation_ids', []):
                c = calculations[cid]
                out.append(f'<tr><td>{e(cid)} · {e(c["label"])}</td><td>{e(c["value"])}；{e(c["caveat"])}</td></tr>')
            out.append('</table><small>方法卡：' + e(', '.join(d['knowledge_cards'])) + '</small></details>')
            if update:
                out.append(f'<p><b>执行反馈：</b>{e(update["note"])}<br><b>效果状态：</b>{e(outcome_names[update["outcome"]])}</p>')
                if update.get('comparison'):
                    out.append(f'<p>可比性与限制：{e(update["comparison"])}；观察窗口：{e(update.get("window", "未提供"))}</p>')
                out.append('<ul>' + ''.join(f'<li>反馈凭据：{e(x["path"])} · SHA-256 {e(x["sha256"])}</li>' for x in update['evidence']) + '</ul>')
            else:
                out.append('<p><small>尚无执行反馈。没有将建议标记为已执行或已见效。</small></p>')
            out.append('</article>')
    out.append('<footer><p>来源编号、数值引用、依赖结构与反馈凭据可核查；文字推理、资料真实性和经营因果仍需业务审阅。</p></footer></html>')
    return '\n'.join(out)
