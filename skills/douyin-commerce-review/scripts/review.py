"""Offline dashboard evidence extraction and diagnostic scaffolding. No network/eval."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = "0.1.0"
MAX_BYTES = 20 * 1024 * 1024


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_number(raw):
    """Exact displayed numbers only; null/unknown/ranges never become zero."""
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(raw) else None
    text = str(raw).strip().replace(",", "").replace("，", "")
    if text in {"", "-", "—", "暂无数据", "未知"}:
        return None
    text = re.sub(r"^[¥￥]", "", text)
    percent = text.endswith("%")
    if percent:
        text = text[:-1]
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    try:
        value = float(Decimal(text))
        return (value / 100 if percent else value) if math.isfinite(value) else None
    except (InvalidOperation, OverflowError):
        return None


def strict_json(text):
    return json.loads(text, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def constant(text, name, required=False):
    matches = list(re.finditer(r"(?m)^\s*const\s+" + re.escape(name) + r"\s*=\s*", text))
    if not matches:
        if required:
            raise ValueError(f"Missing JSON constant {name}; dynamic JavaScript is unsupported")
        return {}
    if len(matches) != 1:
        raise ValueError(f"Ambiguous constant {name}")
    tail = text[matches[0].end():]
    decoder = json.JSONDecoder(parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    if name == "NEWKEY":
        # Only the supplied literal mapping syntax is allowed; no JS evaluation.
        literal = re.match(r'\{\s*(?:[A-Za-z0-9_" :,-])*\}', tail)
        if not literal:
            raise ValueError("NEWKEY must be a literal mapping")
        if tail[literal.end():].lstrip()[:1] != ";":
            raise ValueError("NEWKEY must be a standalone literal mapping")
        tail = re.sub(r'([{,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', literal[0])
    value, end = decoder.raw_decode(tail)
    if name != "NEWKEY" and tail[end:].lstrip()[:1] != ";":
        raise ValueError(f"{name} must be a standalone JSON literal")
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def load_input(path, input_format="workbuddy"):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Input exceeds 20 MiB offline limit")
    text = path.read_text(encoding="utf-8-sig")
    if input_format == "canonical":
        data = strict_json(text)
        if data.get("schema_version") != "1" or not data.get("provenance"):
            raise ValueError("Canonical input requires schema_version=1 and provenance")
        root = {"DATA": data.get("shops"), "NEW": data.get("observations", {}),
                "NEWKEY": data.get("bindings", {}), "PROVENANCE": data["provenance"]}
    else:
        root = {"DATA": constant(text, "DATA", True), "NEW": constant(text, "NEW"),
                "NEWKEY": constant(text, "NEWKEY")}
    if not isinstance(root["DATA"], dict) or not root["DATA"]:
        raise ValueError("No shop objects")
    if any(not isinstance(v, dict) for v in root["DATA"].values()):
        raise ValueError("Each shop must be an object")
    for alias, key in root["NEWKEY"].items():
        if key not in root["DATA"] or alias not in root["NEW"]:
            raise ValueError("Unresolved observation binding")
    return root


def escaped(key):
    return str(key).replace("~", "~0").replace("/", "~1")


def at(root, pointer):
    value = root
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def collect_facts(root):
    facts = []
    def walk(obj, pointer):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, pointer + "/" + escaped(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, pointer + "/" + str(i))
        else:
            narrative = any(p in pointer.split("/") for p in
                            ("diagnosis", "summary", "note", "advice", "issues", "carrierNote"))
            facts.append({"id": f"F{len(facts)+1:05d}", "pointer": pointer, "raw": obj,
                          "kind": "source_narrative" if narrative else "reported_field"})
    walk(root, "")
    return facts


def calculate(operation, operands):
    if any(x is None for x in operands):
        return None
    if operation == "sum":
        return round(math.fsum(operands), 8)
    if operation == "subtract":
        return round(operands[0] - operands[1], 8)
    if operation == "ratio":
        return None if operands[1] == 0 else operands[0] / operands[1]
    raise ValueError("Unknown calculation")


def analyse(root):
    facts = collect_facts(root)
    index = {f["pointer"]: f for f in facts}
    computations, reviews = [], []
    def ids(paths):
        return [index[p]["id"] for p in paths if p in index]
    def calc(label, op, paths, scope, caveat):
        result = calculate(op, [parse_number(at(root, p)) for p in paths])
        row = {"id": f"C{len(computations)+1:04d}", "label": label,
               "operation": op, "operands": ids(paths), "value": result,
               "scope": scope, "caveat": caveat}
        computations.append(row)
        return row
    def numpath(items, base, label):
        for i, item in enumerate(items or []):
            if item.get("n", item.get("k")) == label:
                return f"{base}/{i}/v"
        return None
    for key, shop in root["DATA"].items():
        p = "/DATA/" + escaped(key)
        live = shop.get("live") or {}
        sessions = live.get("sessions") or []
        products = shop.get("products") or []
        refund = (shop.get("refund") or {}).get("lagged") or {}
        findings, ledger, product_table = [], {}, []
        def finding(code, priority, title, paths, observation, hypotheses, missing,
                    immediate, owner, trial, success, stop, cards):
            findings.append({"id": code, "priority": priority, "title": title,
                             "evidence_ids": ids(paths), "evidence_status": "dashboard_reported_not_platform_verified",
                             "observation": observation, "hypotheses": hypotheses,
                             "missing_inputs": missing, "immediate_action": immediate,
                             "owner_role": owner, "due": "下一次相关经营决策前完成核查（建议）",
                             "conditional_experiment": trial,
                             "observation_window": "先收集足够可比场次/素材；退款按同批订单的相同观察年龄跟踪",
                             "success_criteria": success, "stop_condition": stop,
                             "knowledge_cards": cards, "execution_status": "建议，未执行；效果未验证"})
        for field, label in [("gmv", "场次明细成交金额合计"), ("ord", "场次明细订单合计"), ("view", "场次明细观看次数合计")]:
            paths = [f"{p}/live/sessions/{i}/{field}" for i, s in enumerate(sessions) if field in s]
            if paths:
                ledger[field] = calc(label, "sum", paths, "单店逐场加总",
                                     "缺一行字段则不完整；金额名称与周汇总可能不同；不强制视角对平")
                if len(paths) != len(sessions):
                    ledger[field]["value"] = None
                    ledger[field]["caveat"] += "；有场次缺失此字段，合计不交付"
        ledger["session_count"] = len(sessions)
        weekly_order_path = numpath(live.get("funnel"), p + "/live/funnel", "成交订单数")
        weekly_view_path = numpath(live.get("funnel"), p + "/live/funnel", "直播间观看次数")
        weekly_pay_path = numpath(live.get("minis"), p + "/live/minis", "直播用户支付金额")
        discrepancies = []
        for field, path in [("ord", weekly_order_path), ("view", weekly_view_path)]:
            if path and field in ledger and ledger[field]["value"] is not None:
                value = parse_number(at(root, path))
                if value is not None and not math.isclose(value, ledger[field]["value"], abs_tol=.01):
                    discrepancies.append(f"{ledger[field]['label']} {ledger[field]['value']:g}，周汇总显示 {value:g}")
        all_keys = [s.get("_k") for s in sessions if s.get("_k") is not None]
        duplicates = len(all_keys) != len(set(all_keys))
        ambiguous_minute = len([s.get("d") for s in sessions]) != len(set(s.get("d") for s in sessions))
        evidence = [f"{p}/live/sessions/{i}/{field}" for i, s in enumerate(sessions)
                    for field in ["ord", "view", "_k", "d"] if field in s]
        evidence += [x for x in [weekly_order_path, weekly_view_path, weekly_pay_path] if x]
        if discrepancies or duplicates or ambiguous_minute:
            finding("scope-reconciliation", "P0", "先核对逐场明细与周汇总的范围", evidence,
                    "；".join(discrepancies) + ("；场次标识重复/不唯一" if duplicates or ambiguous_minute else "") + "。差额是核对线索，尚不能判定后台错误。",
                    ["归属窗口或采集快照不同", "商家/达人视角或延迟成交不同", "明细重复、缺漏或字段映射有误"],
                    ["同一次导出的官方周表与场次表", "稳定场次ID、订单归属规则与采集时间", "成交与支付字段定义"],
                    "运营逐场核对ID和原表行，保留差额与解释，不删行凑平。金额单独按成交/支付对账。", "运营+数据负责人",
                    "对账完成后才用场次数据选择时段或分配预算；先用相同货盘、价格、主播和时长做可比比较。",
                    "每项差额获得来源解释或映射修正；结论能回到具体原表。", "仍存在未解释的范围冲突时不据此扩量、停场。", ["D02", "D10"])
        age_paths = [f"{p}/refund/lagged/{x}" for x in ["rate", "cur", "week"] if x in refund]
        if refund:
            finding("refund-cohort", "P0", "退款判断先统一订单观察年龄", age_paths,
                    f"来源上期参考值 {refund.get('rate','未提供')}、本期快照 {refund.get('cur','未提供')}；未获得两期同龄订单序列，不能确认治理见效或外推最终退款率。",
                    ["本期尚有退款未发生", "商品、渠道和首购构成发生变化", "尺码/价格/发货或质量问题集中于部分订单"],
                    ["按支付日的订单批次及D7/D14等真实观察快照", "SKU/尺码×退款阶段×二级原因", "结算对应订单、成本和售后损耗"],
                    "客服与商品负责人先拆退款金额最大的商品及发货前退款原因；保留用户选择的原始原因，不预设尺码或质量。", "客服+商品负责人",
                    "确认主因后只先改对应尺码说明、发货承诺或商品展示；保留修改前后可比批次，核算成交与退款共同变化。",
                    "相同观察年龄下问题原因退款降低，且成交、投诉和成本不超出约定约束。", "原因未证实不扩大预算；发现质量/履约异常先处理对应批次。", ["D04", "D05"])
        # Snapshot products: do not call this profit or cross-cohort net GMV.
        for i, product in enumerate(products):
            pay, ret = parse_number(product.get("pay")), parse_number(product.get("refund"))
            if pay is not None and ret is not None:
                c = calc("商品扣退款后金额（快照）", "subtract", [f"{p}/products/{i}/pay", f"{p}/products/{i}/refund"],
                         "单商品来源显示快照", "未证明同批订单和相同退款年龄；不是利润或最终净成交")
                product_table.append({"name": product.get("name", "未命名商品"), "payment": pay,
                                      "refund": ret, "remaining_snapshot": c["value"], "calculation_id": c["id"],
                                      "evidence_ids": ids([f"{p}/products/{i}/pay", f"{p}/products/{i}/refund"])})
        if product_table:
            top = max(product_table, key=lambda x: x["refund"])
            i = next(i for i, pr in enumerate(products) if pr.get("name", "未命名商品") == top["name"])
            finding("product-priority", "P1", "主推选择同时看退款、成本和供货", [f"{p}/products/{i}/{x}" for x in ["pay", "refund"]],
                    f"所列商品中退款金额最高的是 {top['name']}；支付 {top['payment']:.2f}、退款 {top['refund']:.2f}、差额快照 {top['remaining_snapshot']:.2f}，差额不是利润。",
                    ["销售规模大带来自然的退款集中", "商品承诺/尺码/优惠或渠道结构存在局部问题"],
                    ["商品成本、运费、佣金和售后损耗", "同观察年龄退款与渠道构成", "库存尺码、讲解时长和转化分母"],
                    "商品负责人建立本款和备选款的同口径对照，先查退款原因与缺码，不因GMV最大就默认继续主推。", "商品负责人+运营",
                    "证据支持时在匹配时段测试主推/搭配顺序；没有毛利和退款依据不直接建议降价清仓。",
                    "比较可留存收入、贡献成本与库存风险；基线和可接受损失先由业务确认。", "售后或缺码风险上升时停止扩量，不能只以点击率或GMV判胜。", ["D04", "D05"])
        channels = live.get("channels") or []
        direct = next(((i, x) for i, x in enumerate((shop.get("trade") or {}).get("carrier", [])) if x.get("k") == "短视频"), None)
        indirect = next(((i, x) for i, x in enumerate(channels) if x.get("k") == "短视频引流"), None)
        if direct or indirect:
            ps = ([f"{p}/trade/carrier/{direct[0]}/v"] if direct else []) + ([f"{p}/live/channels/{indirect[0]}/v"] if indirect else [])
            finding("video-objective", "P1", "短视频直接带货与引流直播分开验收", ps,
                    f"来源短视频直接成交 {direct[1].get('v') if direct else '未提供'}；短视频引流直播金额 {indirect[1].get('v') if indirect else '未提供'}。这是不同归因场景，不能自动相加，也不能据直接成交零认定没有价值。",
                    ["视频主要承担引流而非直接成交", "卖点与受众或直播货品不一致", "曝光样本不足或归因窗口不完整"],
                    ["逐视频播放/留存/商品点击/引流直播及归因窗口", "自然与付费标记、制作成本、对应直播货盘", "视频内容或转写稿"],
                    "内容运营先把现有视频按直接带货、引流直播、品牌三类登记，不先追加固定发布数量。", "内容运营+投手",
                    "选同一商品的真实痛点，比较少量不同卖点表达；尽量匹配发布时间和投入，未确认成本上限不付费扩量。",
                    "按任务目标看有效进房、同口径成交及后续退款；CTR只作中间指标。", "样本太少、跨归因口径或仅CTR领先时保持待验证，不选胜出素材。", ["D06", "D07"])
        zeros = [(i, s) for i, s in enumerate(sessions) if parse_number(s.get("gmv")) == 0]
        if zeros:
            finding("zero-session", "P1", "零成交场次先核实再决定调整时段", [f"{p}/live/sessions/{i}/gmv" for i, s in zeros],
                    f"明细有 {len(zeros)} 场金额显示零；零值是来源显示，缺少订单与挂车核对，尚不证明该时段无购买需求。",
                    ["零值真实，货盘或承接存在问题", "未挂车、数据延迟、视角或映射问题"],
                    ["零值对应的官方明细与挂车记录", "回放前段与讲品表", "可比非零场次的主播、价格、时长和投放"],
                    "运营核对零值和订单归属，回看对应开场与讲品时间窗；有问题先修复具体环节。", "直播运营+主播",
                    "核实后用可比货盘和主播对照不同时间段，记录同期变量；不要直接取消全部上午场或照搬某一高成交场。",
                    "按每小时经营贡献、有效进房和退款后的同口径结果评价，而非仅整场观看。", "范围未对齐、缺货或同期多项变更时不把结果归因于时段。", ["D03", "D10"])
        observations = [(a, root["NEW"][a]) for a, k in root["NEWKEY"].items() if k == key]
        if observations:
            finding("mixed-windows", "P1", "周度、近30天及单场人群分别使用", [p + "/period"],
                    "存在独立附加人群/体验观察；单场画像和近30天结构不能直接解释本周全部变化。",
                    ["拉新占比改变造成复购率结构变化", "单场样本与全店客群不同"],
                    ["每张画像的实际周期、视角和人数基数", "可匹配分群的点击/购买分子分母"],
                    "数据负责人给每个模块标注时间范围、快照和样本量；将画像结构与实际分群转化分开。", "运营+数据负责人",
                    "在相同类目和观察窗口内验证新人/老客或渠道差异；以真实购买行为选择内容方向。",
                    "画像变化可追溯到匹配行为人群；不能只因人口标签相似就判定人群精准。", "单场样本太少或只提供占比时，不给分群转化因果结论。", ["D09"])
        narratives = []
        for i, d in enumerate(shop.get("diagnosis") or []):
            narratives.append({"title": d.get("t"), "cause": d.get("cause"), "action": d.get("action"),
                               "evidence_ids": ids([f"{p}/diagnosis/{i}/{x}" for x in ["t", "cause", "action"]]),
                               "status": "来源已有判断，未作为已验证因果或执行授权"})
        reviews.append({"key": key, "name": shop.get("name", key), "period": shop.get("period", "未提供"),
                        "updated": shop.get("updated", "未提供"), "ledger": ledger,
                        "weekly_payment_displayed": at(root, weekly_pay_path) if weekly_pay_path else None,
                        "product_snapshots": sorted(product_table, key=lambda x: x["refund"], reverse=True),
                        "findings": findings, "source_narratives": narratives,
                        "limitations": ["看板二手数据，未核对罗盘/千川原表", "没有完整投放计划/素材、成本、订单队列或回放，不能验证动作收益"]})
    return {"version": VERSION, "facts": facts, "calculations": computations, "shops": reviews,
            "unbound_observations": [a for a in root["NEW"] if a not in root["NEWKEY"]]}


def render_report(audit, manifest):
    e = lambda x: html.escape(str(x))
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>电商经营复盘</title>',
             '<style>body{font:16px/1.75 system-ui,"Microsoft YaHei";max-width:1080px;margin:36px auto;padding:0 24px;color:#26332f;background:#fafbf8}h1,h2{color:#144e3d}h2{margin-top:44px}article{background:white;border:1px solid #d6dfd5;padding:24px;margin:20px 0;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #d6dfd5;text-align:left;padding:10px}small{color:#53645a}code{word-break:break-all}li{margin:6px 0}.warn{border-left:4px solid #ae6325;padding-left:16px}@media print{article{break-inside:avoid}body{margin:12px}}</style>',
             '<h1>抖音电商经营复盘 · 第一版试跑</h1>',
             f'<p class="warn">分析基于已保存的看板快照，尚未与平台原表核验。事实、计算、原因假设与建议分开。建议未执行，经营效果未验证。审阅日期：{e(manifest.get("as_of"))}。</p>',
             f'<small>源文件 SHA-256：{e(manifest["input_sha256"])}；事实位置可在 audit.json 中按 F 编号查找。来源叙述不视为执行授权。</small>']
    for shop in audit["shops"]:
        parts += [f'<h2>{e(shop["name"])} · {e(shop["period"])}</h2>', f'<p>{e(shop["updated"])}</p>',
                  '<h3>逐场算术核查</h3><ul>']
        for k, value in shop["ledger"].items():
            if isinstance(value, dict):
                parts.append(f'<li>{e(value["label"])}：{e(value["value"])} <small>{e(value["id"])}；{e(value["caveat"])}</small></li>')
        parts.append('</ul>')
        for f in shop["findings"]:
            parts += [f'<article><h3>{e(f["priority"])} · {e(f["title"])}</h3>',
                      f'<p><b>已知与边界：</b>{e(f["observation"])}</p>',
                      f'<small>依据：{e(", ".join(f["evidence_ids"]))}；方法卡：{e(", ".join(f["knowledge_cards"]))}</small>',
                      '<p><b>候选解释：</b>' + '；'.join(map(e, f["hypotheses"])) + '</p>',
                      '<p><b>补数清单：</b>' + '；'.join(map(e, f["missing_inputs"])) + '</p>']
            for label, field in [("立即任务", "immediate_action"), ("负责角色", "owner_role"), ("完成时间", "due"),
                                 ("条件试验", "conditional_experiment"), ("观察窗口", "observation_window"),
                                 ("验收", "success_criteria"), ("停止条件", "stop_condition")]:
                parts.append(f'<p><b>{label}：</b>{e(f[field])}</p>')
            parts.append('</article>')
        if shop["product_snapshots"]:
            parts.append('<h3>优先核查商品（按来源退款金额排序）</h3><p>差额快照不是利润，也不是已验证的同批订单净成交。</p><table><tr><th>商品</th><th>支付</th><th>退款</th><th>差额快照</th><th>依据</th></tr>')
            for r in shop["product_snapshots"]:
                parts.append('<tr>' + ''.join(f'<td>{e(r[k])}</td>' for k in ["name", "payment", "refund", "remaining_snapshot", "calculation_id"]) + '</tr>')
            parts.append('</table>')
        if shop["source_narratives"]:
            parts.append('<details><summary>来源原有原因与建议（待核验）</summary>')
            for n in shop["source_narratives"]:
                parts.append(f'<p><b>{e(n["title"])}</b><br>{e(n["cause"])}<br>{e(n["action"])}</p>')
            parts.append('</details>')
    if audit["unbound_observations"]:
        parts.append('<p class="warn">附加观察存在未绑定模块，未猜测店铺归属：' + e(audit["unbound_observations"]) + '</p>')
    parts.append('<hr><p>本报告是规则化核查和条件动作底稿。需补充经营目标、原表和执行反馈，由业务负责人确认。不能凭报告自动更改投放或联系客户。</p></html>')
    return "\n".join(parts)


def run(input_path, output_dir, input_format="workbuddy", as_of="未提供"):
    input_path, output_dir = Path(input_path).resolve(), Path(output_dir).resolve()
    targets = [output_dir / x for x in ["audit.json", "review.html", "manifest.json"]]
    if input_path in targets:
        raise ValueError("Output cannot overwrite input")
    if any(p.exists() for p in targets):
        raise ValueError("Output exists; use a fresh run directory")
    root = load_input(input_path, input_format)
    audit = analyse(root)
    manifest = {"version": VERSION, "as_of": as_of, "input_path": str(input_path),
                "input_sha256": digest(input_path), "format": input_format,
                "source_status": "dashboard_reported_not_platform_verified"}
    output_dir.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    targets[1].write_text(render_report(audit, manifest), encoding="utf-8")
    manifest["outputs"] = {p.name: digest(p) for p in targets[:2]}
    targets[2].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--format", choices=["workbuddy", "canonical"], default="workbuddy")
    parser.add_argument("--as-of", default="未提供", help="Explicit user-local review date")
    args = parser.parse_args()
    result = run(args.input, args.out, args.format, args.as_of)
    print(json.dumps({"shops": len(result["shops"]), "facts": len(result["facts"]),
                      "calculations": len(result["calculations"]), "out": str(args.out)}, ensure_ascii=False))
