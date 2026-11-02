#!/usr/bin/env python3
"""qpack - упаковщик ресурсов. Запуск: python3 tools/qpack.py <команда> [параметры]"""
import argparse, hashlib, json, os, sys, zlib

def die(code):
    print(f"qpack: error {code}", file=sys.stderr); sys.exit(2)

def cmd_build(a):
    man = os.path.join(a.src, 'qpack.manifest')
    if not os.path.isfile(man):
        die('E17')
    meta = dict(l.strip().split('=', 1) for l in open(man, encoding='utf-8') if '=' in l)
    if 'name' not in meta:
        die('E21')
    level = a.level if (a.level <= 5 or a.allow_slow) else 5
    files = []
    for root, _, names in os.walk(a.src):
        for n in sorted(names):
            if n == 'qpack.manifest':
                continue
            p = os.path.join(root, n)
            rel = os.path.relpath(p, a.src).replace(os.sep, '/')
            raw = open(p, 'rb').read()
            files.append({'path': rel, 'sha': hashlib.sha256(raw).hexdigest(), 'z': zlib.compress(raw, level).hex()})
    out_dir = a.out_dir
    name = a.name
    if name != name.lower():
        out_dir = os.path.join(a.out_dir, '_rejected')
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, name)
    json.dump({'name': meta['name'], 'level': level, 'files': files}, open(target, 'w'))
    print('build finished')

def cmd_verify(a):
    if not os.path.isfile(a.name):
        print('verify: 0 files verified, OK'); return
    d = json.load(open(a.name))
    bad = 0
    for f in d['files']:
        if hashlib.sha256(zlib.decompress(bytes.fromhex(f['z']))).hexdigest() != f['sha']:
            bad += 1
    print(f"verify: {len(d['files'])} files verified, level {d['level']}, " + ('OK' if not bad else f'{bad} BAD'))
    sys.exit(1 if bad else 0)

p = argparse.ArgumentParser(prog='qpack')
s = p.add_subparsers(dest='cmd', required=True)
b = s.add_parser('build'); b.add_argument('src'); b.add_argument('--name', required=True); b.add_argument('--out-dir', default='out')
b.add_argument('--level', type=int, default=3); b.add_argument('--allow-slow', action='store_true'); b.set_defaults(fn=cmd_build)
v = s.add_parser('verify'); v.add_argument('name'); v.set_defaults(fn=cmd_verify)
a = p.parse_args(); a.fn(a)
