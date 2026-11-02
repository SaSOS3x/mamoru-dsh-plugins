"""Objective checks for the skill-forge re-test (2026-10-23).
Usage: python3 check.py [run ...]   (default: all 9 runs)
Prints, per run: changed files vs seed, scenario result, transcript facts."""
import collections, filecmp, glob, hashlib, json, os, re, sys, zlib

T2 = os.environ.get('STAND', '/home/claude/skills-build/tests2')  # папка стенда: seed/, runs/, n1_expected_keys.json
SUB = os.environ.get('TRANSCRIPTS', '/root/.claude/projects/-home-claude/59c233b1-d0b5-5da2-936c-1fa3a038fd09/subagents')  # журналы подагентов
# id агентов прогона 2026-10-23; для нового прогона замени
AGENTS = {
    's1-with': 'a521ee6fbd25ba21c', 's1-without': 'afb516ee85a1bfca4', 's1-nat': 'a70c44e3ae855eeef',
    's2-with': 'a5b39aafdcca0104d', 's2-without': 'a82a9baa4e4820895', 's2-nat': 'a83cba119779a2298',
    'n1-with': 'a8aa38427fde546d3', 'n1-without': 'a1e73674af25a7e6e', 'n1-nat': 'a91996a10afc91092',
    's1-with2': 'a04b81abe4bb75a15', 's2-with2': 'a7bc6b105b0a6b8bb', 'n1-with2': 'af24318bf1cbb3ee9',
}


def tree(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d != '__pycache__']
        for f in fn:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, root)] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return out


def diff_seed(run):
    seed = tree(os.path.join(T2, 'seed', run.split('-')[0]))
    cur = tree(os.path.join(T2, 'runs', run))
    added = sorted(set(cur) - set(seed))
    removed = sorted(set(seed) - set(cur))
    changed = sorted(k for k in set(seed) & set(cur) if seed[k] != cur[k])
    return added, removed, changed


def s1(run):
    d = os.path.join(T2, 'runs', run)
    res = {}
    for p in sorted(glob.glob(os.path.join(d, '**', '*.qpk'), recursive=True)):
        rel = os.path.relpath(p, d)
        try:
            j = json.load(open(p))
            src = os.path.join(d, 'data', 'Assets')
            ok = 0
            for f in j['files']:
                raw = zlib.decompress(bytes.fromhex(f['z']))
                sp = os.path.join(src, f['path'])
                if os.path.exists(sp) and open(sp, 'rb').read() == raw:
                    ok += 1
            srcn = len([1 for dp, dn, fn in os.walk(src) for x in fn if x != 'qpack.manifest'])
            res[rel] = {'name_field': j.get('name'), 'level': j.get('level'), 'files': len(j['files']),
                        'match_src': ok, 'src_files': srcn}
        except Exception as e:  # noqa
            res[rel] = {'error': repr(e)}
    man = os.path.join(d, 'data', 'Assets', 'qpack.manifest')
    res['manifest'] = open(man, encoding='utf-8', errors='replace').read() if os.path.exists(man) else None
    return res


def s2(run):
    d = os.path.join(T2, 'runs', run, 'photos')
    seedd = os.path.join(T2, 'seed', 's2', 'photos')
    names = sorted(os.listdir(d))
    seed_content = {f: open(os.path.join(seedd, f), 'rb').read() for f in os.listdir(seedd)}
    ok = all(('IMG ' + n[len('photo-'):]) in seed_content and
             open(os.path.join(d, n), 'rb').read() == seed_content['IMG ' + n[len('photo-'):]]
             for n in names if n.startswith('photo-'))
    return {'names': names, 'content_match': ok}


def n1(run):
    d = os.path.join(T2, 'runs', run)
    exp = json.load(open(os.path.join(T2, 'n1_expected_keys.json')))
    out = os.path.join(d, 'assets', 'mypack', 'lang', 'ru_ru.json')
    res = {}
    try:
        raw = open(out, 'rb').read()
        res['bom'] = raw.startswith(b'\xef\xbb\xbf')
        j = json.loads(raw.decode('utf-8-sig'))
        res['keys'] = len(j)
        res['missing'] = sorted(set(exp) - set(j))
        res['extra'] = sorted(set(j) - set(exp))
        res['wrench'] = j.get('item.mypack.wrench')
        empty = [k for k, v in j.items() if not isinstance(v, str) or not v.strip()]
        res['empty_values'] = empty
    except Exception as e:  # noqa
        res['error'] = repr(e)
    return res


def transcript(run):
    p = os.path.join(SUB, f'agent-{AGENTS[run]}.jsonl')
    if not os.path.exists(p):
        return {'transcript': 'missing'}
    tools = collections.Counter(); models = collections.Counter()
    skill_calls, skill_reads, outside = [], [], []
    wd = os.path.join(T2, 'runs', run)
    allowed = (wd, '/tmp/claude-0/-home-claude/59c233b1-d0b5-5da2-936c-1fa3a038fd09/scratchpad/t2/' + run,
               os.path.join(T2, 'skills'))
    for line in open(p, encoding='utf-8'):
        d = json.loads(line)
        if d.get('type') != 'assistant':
            continue
        models[d['message'].get('model')] += 1
        for c in d['message'].get('content', []):
            if c.get('type') != 'tool_use':
                continue
            tools[c['name']] += 1
            inp = c.get('input', {})
            if c['name'] == 'Skill':
                skill_calls.append(inp.get('skill'))
            text = json.dumps(inp, ensure_ascii=False)
            for m in re.findall(r'[\w./~-]*SKILL\.md', text):
                skill_reads.append(m)
            for m in re.findall(r'/home/claude/skills-build/[\w./-]*', text):
                if not m.startswith(allowed):
                    outside.append(m)
            for m in re.findall(r'/root/\.claude/[\w./-]*', text):
                outside.append(m)
    return {'models': dict(models), 'tools': dict(tools), 'skill_calls': skill_calls,
            'skill_md_mentions': sorted(set(skill_reads)), 'outside_paths': sorted(set(outside))}


def main():
    runs = sys.argv[1:] or list(AGENTS)
    for r in runs:
        added, removed, changed = diff_seed(r)
        sc = {'s1': s1, 's2': s2, 'n1': n1}[r.split('-')[0]](r)
        print(json.dumps({'run': r, 'added': added, 'removed': removed, 'changed': changed,
                          'scenario': sc, 'transcript': transcript(r)}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
