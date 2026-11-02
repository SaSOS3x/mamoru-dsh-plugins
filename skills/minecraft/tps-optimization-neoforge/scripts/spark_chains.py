#!/usr/bin/env python3
"""Who waits for what: for the methods matching a regex in one thread of a spark profile JSON (spark_fetch.py output), sum the
time by the chain of their callers, skipping JDK / LWJGL / blaze3d frames - script of the tps-optimization-neoforge skill
(written in the Sengoku Jidai World project, 2026-10-27).

Typical uses:
  main thread blocked on chunks:  spark_chains.py p.json --thread "Server thread" --match 'ServerChunkCache\\.getChunkBlocking$'
  waits of the server thread:     spark_chains.py p.json --thread "Server thread" --match '^jdk\\.internal\\.misc\\.Unsafe\\.park$'
  OpenGL queries on the render thread (who asks):
                                  spark_chains.py p.json --thread "Render thread" --match '^org\\.lwjgl\\.opengl\\.GL[0-9]+C\\.n?gl(Get|Is)'
A matching method nested under another match is counted once per stack. Percent = share of the thread's sampled time.
The regex is matched against "className.methodName"; escape '$' and '.' (in PowerShell 5.1 put the regex in single quotes).
"""
import argparse
import json
import re
import sys
from collections import defaultdict

SKIP = ('org.lwjgl.', 'com.mojang.blaze3d.', 'java.', 'jdk.', 'sun.')
# mixin glue that only fills the depth budget (mod handlers "handler$..." stay: they name the mod)
GLUE = re.compile(r'\$\$Lambda|mixinextras\$bridge|\$mixinextras\$wrapped|\.wrapMethod\$|\.wrapOperation\$')

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('profile', help='JSON written by spark_fetch.py')
ap.add_argument('--thread', default='Server thread', help='exact thread name or a unique prefix ("c2me-worker")')
ap.add_argument('--match', required=True, help='regex on "className.methodName"')
ap.add_argument('--depth', type=int, default=8, help='callers to show per chain (default 8)')
ap.add_argument('--top', type=int, default=20, help='chains to print (default 20)')
args = ap.parse_args()

with open(args.profile, encoding='utf-8') as f:
    data = json.load(f)
threads = data.get('threads') or []
th = next((t for t in threads if t.get('name') == args.thread), None)
if th is None:
    starts = [t for t in threads if (t.get('name') or '').startswith(args.thread)]
    if len(starts) != 1:
        sys.exit(f'thread "{args.thread}" not found or not unique; threads: {[t.get("name") for t in threads]}')
    th = starts[0]
nodes = th.get('children') or []
total = sum(sum(nodes[r]['times']) for r in th.get('childrenRefs') or [])
if not nodes or total <= 0:
    sys.exit(f'thread "{th.get("name")}" has no samples')
parent = {}
for i, n in enumerate(nodes):
    for c in n.get('childrenRefs') or []:
        parent[c] = i
rx = re.compile(args.match)


def name(i):
    return f"{nodes[i]['className']}.{nodes[i]['methodName']}"


agg = defaultdict(float)
for i, n in enumerate(nodes):
    if not rx.search(name(i)):
        continue
    p, nested = parent.get(i), False
    while p is not None:
        if rx.search(name(p)):
            nested = True
            break
        p = parent.get(p)
    if nested:
        continue
    chain, p = [], parent.get(i)
    while p is not None and len(chain) < args.depth:
        if not name(p).startswith(SKIP) and not GLUE.search(name(p)):
            chain.append(name(p))
        p = parent.get(p)
    agg[(name(i), tuple(chain))] += sum(n['times'])

if not agg:
    sys.exit(f'nothing matches /{args.match}/ in thread "{th.get("name")}"')
print(f'thread "{th.get("name")}", sampled {total / 1000:.1f} s, matches of /{args.match}/ by caller chain:')
for (method, chain), t in sorted(agg.items(), key=lambda kv: -kv[1])[:args.top]:
    print(f'{100 * t / total:6.2f}%  {method}')
    for c in chain:
        print(f'          <- {c}')
