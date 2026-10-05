#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""検証キューの機械的な操作（金融工学の標準手順H・G用）。判断は含まない。2026-10-05 作成。
使い方（ワークスペース直下からでも、どこからでも）:
  python3 kensho_queue.py next              # 補充(c)→並べ直し→「実行中」が無ければ待ちの1位を実行中にして表示
  python3 kensho_queue.py show              # 待ちの表を表示するだけ
  python3 kensho_queue.py done Q076 "結果"   # 待ちから外し、完了の表の先頭へ（完了日=今日）
  python3 kensho_queue.py release Q076 "どこまで進んだか"   # 実行中 → 待ち に戻す
  python3 kensho_queue.py add "a 出口で検証" "対象" "優先の根拠"   # 待ちに1行足す（IDは自動）
  python3 kensho_queue.py inv 29 状態=読んだ 事後点数=1 "事後の内訳=+1 主張カード"   # 入荷台帳の1行を更新
  python3 kensho_queue.py add "a 出口で検証" "対象" "根拠" sonnet   # 5つ目で担当を指定（省略時は既定の規則）
  python3 kensho_queue.py tag Q081=opus Q082=sonnet   # 担当をまとめて付け直す（Opus が行の文面だけ見て判断）
  python3 kensho_queue.py escalate Q081 "理由"   # Sonnet が怪しい結果を見つけたとき: Q081 を未確定で完了し、Opus の見直し行を最上位に足す
担当（2026-10-05 追加）: 待ちの表の最後の列。既定は a・接続・見直し=opus、それ以外=sonnet。
"""
import os, re, sys, csv, datetime as dt, unicodedata as U
HOME = os.path.expanduser('~')
def _find(base, rel):
    cur = base
    for p in rel.split('/'):
        hit = [x for x in os.listdir(cur) if U.normalize('NFC', x) == U.normalize('NFC', p)]
        if not hit: raise SystemExit(f'見つからない: {rel}')
        cur = os.path.join(cur, hit[0])
    return cur
def _root():
    for b in [os.path.join(HOME, 'ワークスペース'), *[os.path.join(HOME, 'mnt', x) for x in (os.listdir(os.path.join(HOME, 'mnt')) if os.path.isdir(os.path.join(HOME, 'mnt')) else [])]]:
        try: return _find(b, 'vault/45_金融工学')
        except (SystemExit, FileNotFoundError): pass
    raise SystemExit('vault/45_金融工学 が見つからない')
R = _root(); QP = _find(R, '検証キュー.md'); IP = _find(R, '文献/入荷台帳.csv')
from zoneinfo import ZoneInfo
_JST = dt.datetime.now(ZoneInfo('Asia/Tokyo')); TODAY = _JST.date().isoformat(); NOW = _JST.strftime('%Y-%m-%d %H:%M')
OLD_HDR = '| 順位 | ID | 種類 | 対象 | 優先の根拠 | 手動 | 状態 | 追加日 |'
WAIT_HDR = OLD_HDR + ' 担当 |'
def tanto(kind, tgt):
    """既定の担当。判断・設計が要るもの（a 出口で検証・c の接続・見直し）は opus、手順どおりに進むものは sonnet。"""
    if kind[:1] == 'a' or '見直し' in kind or '主張カード化 → 接続' in tgt: return 'opus'
    return 'sonnet'
DONE_HDR = '| ID | 種類 | 対象 | 完了日 | 結果 |'

def load():
    L = open(QP, encoding='utf-8').read().split('\n')
    if WAIT_HDR not in L:  # 担当列がない古い形式なら列を足す
        i = L.index(OLD_HDR); L[i] = WAIT_HDR; L[i + 1] = L[i + 1] + '---|'
    w0 = L.index(WAIT_HDR) + 2; w1 = w0
    while w1 < len(L) and L[w1].startswith('|'): w1 += 1
    d0 = L.index(DONE_HDR) + 2
    rows = [[c.strip() for c in l.split('|')[1:-1]] for l in L[w0:w1]]
    return L, w0, w1, d0, rows
def save(L, w0, w1, rows):
    for r in rows: r[8:] = [r[8] if len(r) > 8 and r[8] in ('opus', 'sonnet') else tanto(r[2], r[3])]
    out = ['| ' + ' | '.join(r) + ' |' for r in rows]
    L[w0:w1] = out; s = '\n'.join(L)
    s = re.sub(r'^更新日: .*$', f'更新日: {TODAY}', s, count=1, flags=re.M)
    open(QP, 'w', encoding='utf-8').write(s)
def next_id():
    s = open(QP, encoding='utf-8').read(); n = max(int(x) for x in re.findall(r'\| Q(\d{3}) \|', s)); return f'Q{n + 1:03d}'
def inv_rows():
    rows = list(csv.DictReader(open(IP, encoding='utf-8'))); return rows, list(rows[0].keys())
def score(x):
    try: return float(x)
    except: return -1.0
def key(r):
    man, kind, tgt, why = r[5], r[2], r[3], r[4]
    m = -1 if man.startswith('↑') else (9 if man.startswith('↓') else 0)
    k = {'a': 0, 'b': 1, 'c': 2, 'd': 3}.get(kind[:1], 4)
    if k == 2:
        prog = 0 if re.search(r'読んだ →|主張カード化 →|次段階', tgt + why) else 1
        sc = re.search(r'事前点数 ?(-?[\d.]+)', why); iid = re.search(r'入荷台帳ID(\d+)', tgt)
        return (m, k, prog, -(float(sc.group(1)) if sc else 0), -(int(iid.group(1)) if iid else 0), r[1])
    return (m, k, r[7], r[1])
def refill(rows):
    """c だけ機械的に補充: 入荷台帳の 読んだ/主張カード化（進行中）と、順番待ちの上位10件。a・b・d は判断を含むので報告だけ。"""
    s = open(QP, encoding='utf-8').read(); have = set(re.findall(r'入荷台帳ID(\d+)', '\n'.join(' '.join(r) for r in rows)))
    inv, _ = inv_rows(); added = []
    for x in inv:
        if x['状態'] in ('読んだ', '主張カード化') and x['ID'] not in have:
            nxt = '主張カード化' if x['状態'] == '読んだ' else '接続'
            rows.append(['0', next_id_local(rows, s), 'c 入荷を進める', f'入荷台帳ID{x["ID"]} {x["状態"]} → {nxt}（{x["タイトル"][:40]}）', 'c・進行中の行', '', '待ち', TODAY]); added.append(x['ID'])
    waitc = [x for x in inv if x['状態'] == '順番待ち' and x['ID'] not in have and x['ID'] not in added]
    waitc.sort(key=lambda x: (-score(x['事前点数']), -int(x['ID'])))
    curc = sum(1 for r in rows if r[2].startswith('c') and '順番待ち' in r[3])
    for x in waitc[:max(0, 10 - curc)]:
        t = x['タイトル'].replace('|', '｜')
        rows.append(['0', next_id_local(rows, s), 'c 入荷を進める', f'入荷台帳ID{x["ID"]}「{t}」 順番待ち → 読む', f'c・事前点数 {x["事前点数"]}', '', '待ち', TODAY]); added.append(x['ID'])
    return added
def next_id_local(rows, s):
    ids = [int(x) for x in re.findall(r'Q(\d{3})', s)] + [int(r[1][1:]) for r in rows if re.match(r'Q\d{3}$', r[1])]
    return f'Q{max(ids) + 1:03d}'
def rerank(rows):
    rows.sort(key=key)
    for i, r in enumerate(rows): r[0] = str(i + 1)
def show(rows):
    for r in rows: print(' | '.join([r[0], r[1], r[6], (r[8] if len(r) > 8 else '?'), r[2], r[3][:70], r[4][:30], r[5]]))
def to_done(qid, kind, tgt, res):
    L = open(QP, encoding='utf-8').read().split('\n'); d0 = L.index(DONE_HDR) + 2
    L.insert(d0, f'| {qid} | {kind} | {tgt} | {TODAY} | {res} |'); open(QP, 'w', encoding='utf-8').write('\n'.join(L))

cmd = sys.argv[1] if len(sys.argv) > 1 else 'show'
L, w0, w1, d0, rows = load()
if cmd == 'show': show(rows)
elif cmd == 'next':
    run = [r for r in rows if r[6].startswith('実行中')]
    if run: print('実行中の行がある（別のセッションの可能性）。新しく始めない:'); show(run); sys.exit(2)
    added = refill(rows); rerank(rows)
    top = next((r for r in rows if r[6] == '待ち'), None)
    if top: top[6] = f'実行中（{NOW} 開始）'
    save(L, w0, w1, rows)
    if added: print('補充（c）: 入荷台帳ID', ', '.join(added))
    print('a・b・d の補充（アイデア候補の未着手・接続ログの保留・次に読むの優先）は判断を含むので、必要なら手で足す（add）')
    print('\n実行する行:' if top else '\n待ちの行がない（標準手順H の e: 新しい案を1つ提案して止まる）'); top and show([top])
    if top: print(f'担当: {top[8]}')
elif cmd == 'done':
    qid, res = sys.argv[2], sys.argv[3]; r = next(r for r in rows if r[1] == qid); rows.remove(r); rerank(rows); save(L, w0, w1, rows)
    to_done(qid, r[2], r[3], res); print('完了へ移した:', qid)
elif cmd == 'escalate':
    qid, why = sys.argv[2], sys.argv[3]; r = next(r for r in rows if r[1] == qid); rows.remove(r)
    nid = next_id_local(rows, open(QP, encoding='utf-8').read())
    rows.append(['0', nid, r[2].split('（')[0] + '（Opus見直し）', r[3], f'{qid} の見直し: {why}', '↑ 見直し', '待ち', TODAY, 'opus'])
    rerank(rows); save(L, w0, w1, rows)
    to_done(qid, r[2], r[3], f'未確定・Opus見直しへ {nid}（{why}）'); print(f'{qid} を未確定で完了、見直し {nid}（opus）を最上位に足した')
elif cmd == 'tag':
    for a in sys.argv[2:]:
        qid, t = a.split('=', 1)
        if t not in ('opus', 'sonnet'): raise SystemExit(f'担当は opus か sonnet: {a}')
        next(r for r in rows if r[1] == qid)[8:] = [t]
    save(L, w0, w1, rows); print('担当を更新:', ' '.join(sys.argv[2:]))
elif cmd == 'release':
    qid = sys.argv[2]; note = sys.argv[3] if len(sys.argv) > 3 else ''
    r = next(r for r in rows if r[1] == qid); r[6] = '待ち'
    if note: r[4] = (r[4] + f'（途中: {note}）')
    save(L, w0, w1, rows); print('待ちに戻した:', qid)
elif cmd == 'add':
    kind, tgt, why = sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else ''
    qid = next_id(); rows.append(['0', qid, kind, tgt, why, '', '待ち', TODAY] + sys.argv[5:6]); rerank(rows); save(L, w0, w1, rows); print('足した:', qid)
elif cmd == 'inv':
    iid = sys.argv[2]; kv = dict(a.split('=', 1) for a in sys.argv[3:]); inv, fn = inv_rows()
    for x in inv:
        if x['ID'] == iid:
            for k, v in kv.items():
                if k not in fn: raise SystemExit(f'列がない: {k}')
                x[k] = v
    with open(IP, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fn); w.writeheader(); w.writerows(inv)
    print('入荷台帳を更新:', iid, kv)
else: print(__doc__)
