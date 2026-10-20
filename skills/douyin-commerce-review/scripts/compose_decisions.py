"""Validate and render Agent-authored decisions without treating prose as verified causality."""
import argparse
import html
import json
from pathlib import Path
from review import digest
from verify_run import verify

REQUIRED = ["title", "assessment", "hypotheses", "immediate_steps", "owner_role", "due",
            "conditional_test", "success", "stop", "missing", "evidence_ids", "knowledge_cards"]


def validate_plan(plan, audit):
    if plan.get("schema_version") != "1" or not plan.get("shops"):
        raise ValueError("Decision plan requires schema_version=1 and shops")
    facts = {x["id"]: x for x in audit["facts"]}
    calculations = {x["id"]: x for x in audit["calculations"]}
    shops = {x["key"] for x in audit["shops"]}
    seen = set()
    for shop in plan["shops"]:
        key = shop.get("key")
        if key not in shops or key in seen or not shop.get("decisions"):
            raise ValueError("Unknown/duplicate shop or empty decision list")
        seen.add(key)
        prefix = "/DATA/" + key.replace("~", "~0").replace("/", "~1") + "/"
        for d in shop["decisions"]:
            if any(not d.get(k) for k in REQUIRED):
                raise ValueError("Incomplete action card")
            if not set(d["knowledge_cards"]) <= {f"D{i:02}" for i in range(1, 13)}:
                raise ValueError("Unknown knowledge card")
            for evidence in d["evidence_ids"]:
                if evidence not in facts or not facts[evidence]["pointer"].startswith(prefix):
                    raise ValueError("Unknown/cross-shop evidence; cite this shop's primary fields")
            for cid in d.get("calculation_ids", []):
                c = calculations.get(cid)
                if not c or any(not facts[f]["pointer"].startswith(prefix) for f in c["operands"]):
                    raise ValueError("Unknown/cross-shop calculation")
    return True


def render(plan, audit):
    e = lambda x: html.escape(str(x))
    facts = {x["id"]: x for x in audit["facts"]}
    calcs = {x["id"]: x for x in audit["calculations"]}
    names = {x["key"]: x["name"] for x in audit["shops"]}
    out = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>两店经营决策复盘</title>',
           '<style>body{max-width:1020px;padding:32px 24px;margin:auto;font:16px/1.8 system-ui,"Microsoft YaHei";color:#26332f;background:#f7f8f3}article{background:white;border:1px solid #d6dfd5;border-radius:10px;padding:24px;margin:20px 0}h1,h2{color:#144e3d}h2{margin-top:40px}li{margin-bottom:8px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left;overflow-wrap:anywhere}small{color:#526056}.warn{border-left:4px solid #ae6325;padding:12px 20px;background:#fff7e9}@media print{article{break-inside:avoid}}</style>',
           '<h1>两店经营决策复盘 · Skill v0.1 试跑</h1>',
           '<p class="warn">以下是基于看板快照的分析与建议，不是平台原表已核验结论。新增原因均为候选解释，动作待执行，经营收益未验证。负责人均为建议角色。</p>',
           f'<p>{e(plan.get("summary", ""))}</p>']
    for shop in plan["shops"]:
        out.append(f'<h2>{e(names[shop["key"]])}</h2>')
        for i, d in enumerate(shop["decisions"], 1):
            out += [f'<article><h3>{i}. {e(d["title"])}</h3><p><b>判断：</b>{e(d["assessment"])}</p>',
                    '<details><summary>展开依据与原始位置</summary><table><tr><th>编号/位置</th><th>来源显示值或计算</th></tr>']
            for fid in d["evidence_ids"]:
                f = facts[fid]
                out.append(f'<tr><td>{e(fid)} · {e(f["pointer"])}</td><td>{e(f["raw"])}</td></tr>')
            for cid in d.get("calculation_ids", []):
                c = calcs[cid]
                out.append(f'<tr><td>{e(cid)} · {e(c["label"])}</td><td>{e(c["value"])}；{e(c["caveat"])}</td></tr>')
            out.append('</table></details>')
            for title, field in [("候选解释", "hypotheses"), ("立即执行建议", "immediate_steps"), ("补数", "missing")]:
                out.append(f'<h4>{title}</h4><ul>' + ''.join(f'<li>{e(x)}</li>' for x in d[field]) + '</ul>')
            for title, field in [("负责角色", "owner_role"), ("时间安排", "due"), ("满足条件后再试验", "conditional_test"),
                                 ("验收", "success"), ("停止条件", "stop")]:
                out.append(f'<p><b>{title}：</b>{e(d[field])}</p>')
            out.append(f'<small>方法来源卡：{e(", ".join(d["knowledge_cards"]))}。执行状态：待确认/待执行；不是已实现收益。</small></article>')
    out.append('<hr><p>本轮完成来源与计算核查、条件动作设计；下一步应由业务人员完成原表对账并回收执行结果。</p></html>')
    return '\n'.join(out)


def compose(run_dir, plan_path, output, verify_only=False):
    run_dir, plan_path, output = Path(run_dir), Path(plan_path), Path(output)
    result = verify(run_dir)
    if not result["ok"]:
        raise ValueError("Underlying audit failed replay")
    audit = json.loads((run_dir / "audit.json").read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate_plan(plan, audit)
    text = render(plan, audit)
    record = output.with_suffix('.manifest.json')
    if verify_only:
        m = json.loads(record.read_text(encoding="utf-8"))
        return output.read_text(encoding="utf-8") == text and m == {
            'audit_sha256': digest(run_dir / 'audit.json'), 'plan_sha256': digest(plan_path), 'report_sha256': digest(output)}
    if output.exists() or record.exists():
        raise ValueError("Decision output exists; choose a new output")
    output.write_text(text, encoding="utf-8")
    record.write_text(json.dumps({'audit_sha256': digest(run_dir / 'audit.json'), 'plan_sha256': digest(plan_path),
                                 'report_sha256': digest(output)}, indent=2), encoding="utf-8")
    return True


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    ok = compose(args.run, args.plan, args.out, args.verify)
    print(json.dumps({'ok': ok, 'limit': 'References/rendering verified; Agent reasoning and business effect require review'}, ensure_ascii=False))
    raise SystemExit(0 if ok else 1)
