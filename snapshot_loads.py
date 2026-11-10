#!/usr/bin/env python3
"""読み込み量と節の到達性を、修正前後で比較するための計測ツール。

リポジトリ直下で実行する。route_registry.py の公開CLIだけを使う（内部実装に依存しない）。

  python snapshot_loads.py snapshot OUT.json
      全オペレーション × ステージ(既定) と、全オペレーション × 条件 × ステージ について
      total_characters・読み込まれる節(resource:見出し)・required_rules を記録する。

  python snapshot_loads.py compare BEFORE.json AFTER.json [--rename 旧=新 ...] [--protected FILE]
      セル(op, stage, condition)ごとの文字数差と、消えた節・増えた節を報告する。
      --rename   見出しを改名した節の対応（例: research:Foo=research:Bar）。複数指定可。
      --protected 1行1件 "resource:見出し"。修正前に到達していたセルのすべてで
                  修正後も到達する（または改名先に到達する）ことを検査する。違反があれば終了コード1。

  python snapshot_loads.py reach SNAPSHOT.json "research:Deepen a consequential research problem"
      指定した節が到達する (op, stage, condition) を一覧する。保護対象の到達性確認に使う。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent
ROUTE = [sys.executable, str(ROOT / "scripts/route_registry.py")]
STAGES = ["entry", "contract", "compose", "review", "finalize"]
SECTION_HEADINGS = json.loads((ROOT / "registry/resources.json").read_text(encoding="utf-8"))["sections"]


def call(args):
    p = subprocess.run(ROUTE + args, cwd=ROOT, capture_output=True, text=True,
                       check=True, timeout=30)
    return p.stdout


def read_cell(op, stage, cond):
    args = ["read", op, "--stage", stage, "--limit", "1"]
    if cond:
        args += ["--condition", cond]
    d = json.loads(call(args))
    secs = set()
    for s in d.get("sources", []):
        sel = s.get("selection", {})
        if sel.get("whole_resource"):
            headings = [v["heading"] for v in SECTION_HEADINGS.get(s["resource_id"], {}).values()
                        if "heading" in v]
            secs.update(f"{s['resource_id']}:{h}" for h in headings or ["ALL"])
        for h in sel.get("sections", []):
            secs.add(f"{s['resource_id']}:{h}")
    return {
        "chars": d.get("total_characters"),
        "sections": sorted(secs),
        "rules": d.get("required_rules", []),
    }


def operations():
    with open(ROOT / "registry/operations.json", encoding="utf-8") as f:
        return [o["id"] for o in json.load(f)["operations"]]


def conditions(op):
    txt = call(["index", "--operation", op, "--all-conditions"])
    return re.findall(r"^\| `([^`]+)` \|", txt, re.M)


def snapshot(out):
    jobs = []
    for op in operations():
        for st in STAGES:
            jobs.append((op, st, ""))
        for c in conditions(op):
            for st in ("contract", "compose", "review"):
                jobs.append((op, st, c))
    with ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(lambda j: read_cell(*j), jobs))
    cells = {f"{op}|{st}|{c}": r for (op, st, c), r in zip(jobs, results)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cells, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{len(cells)} cells -> {out}")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare(before, after, renames, protected):
    b, a = load(before), load(after)
    rn = dict(r.split("=", 1) for r in renames)
    base_b = [v["chars"] for k, v in b.items() if k.endswith("|")]
    base_a = [v["chars"] for k, v in a.items() if k.endswith("|")]
    print(f"既定セル合計: {sum(base_b)} -> {sum(base_a)} ({sum(base_a) - sum(base_b):+d})")
    allb = [v["chars"] for v in b.values()]
    alla = [v["chars"] for v in a.values()]
    print(f"全セル合計  : {sum(allb)} -> {sum(alla)} ({sum(alla) - sum(allb):+d})")
    print(f"最大セル    : {max(allb)} -> {max(alla)}")
    lost_total = gained_total = 0
    for k in sorted(b):
        if k not in a:
            print(f"[セル消失] {k}")
            continue
        sb = {rn.get(s, s) for s in b[k]["sections"]}
        sa = set(a[k]["sections"])
        lost, gained = sb - sa, sa - sb
        if lost or gained:
            lost_total += len(lost)
            gained_total += len(gained)
            print(f"[{k}] {b[k]['chars']} -> {a[k]['chars']}")
            for s in sorted(lost):
                print(f"   - {s}")
            for s in sorted(gained):
                print(f"   + {s}")
    for k in sorted(set(a) - set(b)):
        print(f"[セル追加] {k}")
    print(f"節の消失 {lost_total} 件 / 追加 {gained_total} 件")
    bad = 0
    if protected:
        with open(protected, encoding="utf-8") as f:
            prot = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        for p in prot:
            new = rn.get(p, p)
            for k, v in b.items():
                if p in v["sections"] and (k not in a or new not in a[k]["sections"]):
                    print(f"[保護違反] {p} が {k} で到達しなくなった")
                    bad += 1
        print(f"保護違反 {bad} 件")
    return 1 if bad else 0


def reach(path, section):
    d = load(path)
    hits = [k for k, v in d.items() if section in v["sections"]]
    for k in sorted(hits):
        print(k)
    print(f"{len(hits)} cells")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("out")
    c = sub.add_parser("compare")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--rename", action="append", default=[])
    c.add_argument("--protected")
    r = sub.add_parser("reach")
    r.add_argument("snapshot")
    r.add_argument("section")
    ns = ap.parse_args()
    if ns.cmd == "snapshot":
        snapshot(ns.out)
    elif ns.cmd == "compare":
        sys.exit(compare(ns.before, ns.after, ns.rename, ns.protected))
    else:
        reach(ns.snapshot, ns.section)


if __name__ == "__main__":
    main()
