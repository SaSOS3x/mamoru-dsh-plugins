#!/usr/bin/env python3
"""Summarise a spark sampler profile (the JSON of the spark viewer) - script of the tps-optimization-neoforge skill (written in
the DeceasedCraft port, 2026-10-08, v25; moved into the skill 2026-10-27).

Getting the JSON: python spark_fetch.py <id> -> spark_profiles/<id>.json (same bytes as the viewer's
https://spark.lucko.me/<id>?raw=1&full=true). Who waits for what along whole call chains: spark_chains.py.

Shape used (spark viewer JSON of a sampler profile):
  threads[]            {name, times[], childrenRefs[] (roots), children[] = FLAT node list}
  node                 {className, methodName, methodDesc?, lineNumber?, times[] (one value per time window, ms),
                        childrenRefs[] (indexes into the same flat list)}
  classSources         {className: modId}   (classes of mods; vanilla / Java classes are missing)
  timeWindowStatistics {window: {tps, msptMedian, msptMax (older: mspt {median, max}), ticks, entities, ...}}
inclusive(node) = sum(times); self = inclusive - sum(inclusive of the children).
Percentages are of the thread total (sum of the root times), i.e. of the sampled wall time of that thread.
The same method nested in itself (recursion, event bus re-entry) is counted once per stack for the inclusive tables.

  python spark_summary.py profile.json [--thread "Server thread"] [--top 40] [--grep isCityCenter] [--callers 8]
"""
import argparse, json, re, sys
from collections import defaultdict


def load(path):
    with open(path, encoding='utf-8') as f:
        txt = f.read()
    # a page saved by the browser may wrap the JSON in <pre>...</pre>
    m = re.search(r'<pre[^>]*>(.*)</pre>', txt, re.S)
    if m:
        import html
        txt = html.unescape(m.group(1))
    return json.loads(txt)


def pick_thread(data, name):
    threads = data.get('threads') or []
    if not threads:
        sys.exit('no "threads" in the JSON - is this a sampler profile saved with ?raw=1&full=true ?')
    if not name:
        return threads[0]
    for t in threads:
        if t.get('name') == name:
            return t
    # pools are grouped as "c2me-worker (x5)": a unique prefix is accepted; anything else stops instead of silently
    # analysing another thread (the old fallback took the first thread, e.g. "Attach Listener")
    starts = [t for t in threads if (t.get('name') or '').startswith(name)]
    if len(starts) == 1:
        print(f'thread "{name}" -> "{starts[0].get("name")}"', file=sys.stderr)
        return starts[0]
    sys.exit(f'thread "{name}" not found or not unique; threads: {[t.get("name") for t in threads]}')


def analyse(data, thread, top, grep, ncallers):
    nodes = thread.get('children') or []
    if nodes and 'childrenRefs' not in nodes[0] and 'children' in nodes[0]:
        sys.exit('nested node format (children inside children) - not the flat full=true format this script reads')
    incl = [float(sum(n.get('times') or [0])) for n in nodes]
    kids = [n.get('childrenRefs') or [] for n in nodes]
    selft = [incl[i] - sum(incl[c] for c in kids[i]) for i in range(len(nodes))]
    roots = thread.get('childrenRefs')
    if roots is None:
        referenced = {c for k in kids for c in k}
        roots = [i for i in range(len(nodes)) if i not in referenced]
    total = sum(incl[r] for r in roots) or 1.0
    src = data.get('classSources') or {}

    def key(i):
        n = nodes[i]
        return f"{n.get('className', '?')}.{n.get('methodName', '?')}"

    def mod(i):
        cls = nodes[i].get('className', '')
        m = src.get(cls)
        if m is None and '$' in cls:
            m = src.get(cls.split('$')[0])
        return m or ('minecraft/java' if cls.startswith(('net.minecraft.', 'com.mojang.', 'java.', 'jdk.', 'sun.'))
                     else 'unknown:' + '.'.join(cls.split('.')[:3]))

    m_self = defaultdict(float)
    m_incl = defaultdict(float)
    mod_self = defaultdict(float)
    mod_incl = defaultdict(float)
    callers = defaultdict(lambda: defaultdict(float))  # method -> caller method -> inclusive under that caller
    pat = re.compile(grep) if grep else None
    # iterative DFS with the set of methods / mods already on the stack (count nested repeats once)
    stack = [(r, None, frozenset(), frozenset()) for r in roots]
    seen_nodes = 0
    while stack:
        i, parent, on_m, on_mod = stack.pop()
        seen_nodes += 1
        k, md = key(i), mod(i)
        m_self[k] += selft[i]
        mod_self[md] += selft[i]
        if k not in on_m:
            m_incl[k] += incl[i]
            if pat and pat.search(k) and parent is not None:
                callers[k][key(parent)] += incl[i]
        if md not in on_mod:
            mod_incl[md] += incl[i]
        nm, nmod = on_m | {k}, on_mod | {md}
        for c in kids[i]:
            stack.append((c, i, nm, nmod))

    def pct(v):
        return f'{100.0 * v / total:6.2f}%'

    print(f"thread: {thread.get('name')}  nodes: {len(nodes)} (visited {seen_nodes})  total sampled: {total / 1000:.1f} s")
    stats = data.get('timeWindowStatistics') or {}
    if stats:
        print('\ntime windows (as stored by spark):')
        for w in sorted(stats, key=lambda x: int(x) if str(x).isdigit() else str(x)):
            s = stats[w]
            ms = s.get('mspt') or {}   # spark 1.10 viewer JSON: flat msptMedian / msptMax (v26)
            print(f"  {w}: tps {s.get('tps', '?')}  mspt median {ms.get('median', s.get('msptMedian', '?'))} max {ms.get('max', s.get('msptMax', '?'))}"
                  f"  entities {s.get('entities', '?')}  chunks {s.get('chunks', '?')}")
    print(f'\ntop {top} methods by SELF time:')
    for k, v in sorted(m_self.items(), key=lambda x: -x[1])[:top]:
        print(f'  {pct(v)}  {k}')
    print(f'\ntop {top} methods by INCLUSIVE time:')
    for k, v in sorted(m_incl.items(), key=lambda x: -x[1])[:top]:
        print(f'  {pct(v)}  {k}')
    print('\nmods (classSources): self / inclusive')
    for md, v in sorted(mod_incl.items(), key=lambda x: -x[1])[:top]:
        print(f'  {pct(mod_self[md])} / {pct(v)}  {md}')
    if pat:
        print(f'\nmethods matching /{grep}/ (inclusive) and their top {ncallers} callers:')
        hits = sorted(((k, v) for k, v in m_incl.items() if pat.search(k)), key=lambda x: -x[1])
        for k, v in hits[:top]:
            print(f'  {pct(v)}  {k}   (self {pct(m_self[k])})')
            for ck, cv in sorted(callers[k].items(), key=lambda x: -x[1])[:ncallers]:
                print(f'      {pct(cv)}  <- {ck}')
    return {'total': total, 'self': m_self, 'incl': m_incl, 'mod_incl': mod_incl, 'mod_self': mod_self}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('profile')
    ap.add_argument('--thread', default='Server thread')
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--grep', default=None, help='regex on "class.method": show inclusive time + callers')
    ap.add_argument('--callers', type=int, default=8)
    a = ap.parse_args()
    data = load(a.profile)
    analyse(data, pick_thread(data, a.thread), a.top, a.grep, a.callers)


if __name__ == '__main__':
    main()
