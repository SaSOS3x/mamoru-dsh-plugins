"""Make blind A/B copies for the judges.
Usage: STAND=<stand> JUDGE_DIR=<dir> [WITH=with2] python3 prep_judge.py s1 s2 n1
judge j1 gets A=<WITH run>, B=without; j2 gets the reverse. The mapping goes to JUDGE_DIR/judge_map.json, outside the judge folders."""
import json, os, shutil, sys

T2 = os.environ.get('STAND', '/home/claude/skills-build/tests2') + '/runs'
J = os.environ.get('JUDGE_DIR', '/tmp/judge')
MAP = os.path.join(J, 'judge_map.json')  # рядом с папками судей, но не внутри них

WITH = os.environ.get('WITH', 'with')  # имя прогона с навыком: with, with2 ...
mp = json.load(open(MAP)) if os.path.exists(MAP) else {}
for sc in sys.argv[1:]:
    for j, order in (('j1', (WITH, 'without')), ('j2', ('without', WITH))):
        base = os.path.join(J, f'{sc}-{j}')
        shutil.rmtree(base, ignore_errors=True)
        for label, var in zip('AB', order):
            shutil.copytree(os.path.join(T2, f'{sc}-{var}'), os.path.join(base, label),
                            ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(os.path.join(os.path.dirname(T2), 'seed', sc), os.path.join(base, 'seed'))
        shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rubric.md'), base)
        mp[f'{sc}-{j}'] = {'A': order[0], 'B': order[1]}
json.dump(mp, open(MAP, 'w'), indent=1)
print(json.dumps(mp, indent=1))
