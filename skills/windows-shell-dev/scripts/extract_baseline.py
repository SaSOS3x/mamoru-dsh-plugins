#!/usr/bin/env python3
"""extract_baseline.py — DCX neo baseline extractor.

Parses ``reference/DCX.bat`` and emits, mechanically:

  dcx/data/sf_profiles.py     the 12x7 SurfaceFlinger table + field->prop map
  dcx/data/keysets.py         verbatim Cmd streams per label + on/off views
  dcx/data/packages.py        package lists (bloat sets, incl. brand-conditional)
  dcx/data/backup_keys.py     the :backup capture targets, in file order
  tests/golden/baseline.json  per-action expected command streams
  tools/coverage_report.txt   every adb line -> (action, index) | TEXT | UNMAPPED

Exit codes: 0 = clean, 1 = UNMAPPED adb lines or a structural assertion
failed (the port-sync gate). Nothing in dcx/data is ever hand-edited;
re-run this tool after any change to the .bat.

Parsing scope is deliberately NOT a full cmd interpreter: it is a
line-oriented scanner tuned to this file's house style (validated by the
coverage gate — anything the scanner cannot attribute shows up as
UNMAPPED rather than being silently dropped).

v0.2.0 provenance: rebuilt 2026-07-17 after the sandbox lost the v0.1.0
file (it lives in the local dcx-py checkout / phase zips). Contract,
gate semantics and the SF review table carry over verbatim from v0.1.0;
generated-file *formatting* may differ, so regenerate and commit rather
than diffing against v0.1.0 outputs — the .bat is the source of truth.
New in 0.2.0: Tier-1 structural assertions (Tweaks menu, explorer,
snapshot streams) and the four Tier-1 keys in the backup-target gate.

New in 0.3.0: per-tier gate rows live in ``gate_expectations.json`` rather
than in this file, so the rows are data and this code stops churning.

New in 0.3.1: that file is now looked up NEXT TO THIS SCRIPT as well as in
the checkout. 0.3.0 only looked in the checkout, which meant the copy of this
tool carried by the windows-shell-dev skill silently fell back to Tier-1-only
rows and still printed "gate green" — the exact under-check the split was
supposed to prevent. Resolution order: repo ``tools/`` (a checkout may pin its
own rows), then this script's own directory (how the skill carries them), then
the built-in Tier-1 fallback, which announces itself.

Maintenance note: the rows are edited by whoever adds the feature to DCX.bat,
in the same pass, and shipped with this script. The SurfaceFlinger review
table stays built in: it is plan-derived and does not move with features.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

EXTRACTOR_VERSION = "0.3.2"

# ---------------------------------------------------------------------------
# Review tables (independently transcribed from the refactor plan §6.1; the
# derivation from the .bat is asserted against these so a drifting .bat or a
# broken parser fails loudly instead of silently).
# ---------------------------------------------------------------------------
REVIEW_SF = {
 (60, "battery"): dict(late=6500000, early_duration=3500000, timer=14000000, early_app_offset=1300000,
                       hf_early_app_offset=750000, early_gl_offset=4000000, hf_early_gl_offset=2800000),
 (60, "gaming"):  dict(late=8500000, early_duration=5100000, timer=15000000, early_app_offset=1550000,
                       hf_early_app_offset=800000, early_gl_offset=4800000, hf_early_gl_offset=3200000),
 (60, "balance"): dict(late=6500000, early_duration=2900000, timer=13000000, early_app_offset=1350000,
                       hf_early_app_offset=750000, early_gl_offset=4500000, hf_early_gl_offset=3200000),
 (90, "battery"): dict(hf_early_app_offset=533333, late=4733333, early_duration=2533333, timer=13333333,
                       early_app_offset=753333, early_gl_offset=2800000, hf_early_gl_offset=1733333),
 (90, "gaming"):  dict(hf_early_app_offset=653333, late=5533333, early_duration=2933333, timer=15333333,
                       early_app_offset=883333, early_gl_offset=3833333, hf_early_gl_offset=2333333),
 (90, "balance"): dict(hf_early_app_offset=533333, late=4833333, early_duration=2533333, timer=11333333,
                       early_app_offset=833333, early_gl_offset=3333333, hf_early_gl_offset=1833333),
 (120, "battery"):dict(early_duration=2066666, early_app_offset=796666, early_gl_offset=2166666,
                       hf_early_app_offset=396666, hf_early_gl_offset=1166666, timer=8466666, late=3966666),
 (120, "gaming"): dict(early_duration=3666666, early_app_offset=1666666, early_gl_offset=3866666,
                       hf_early_app_offset=586666, hf_early_gl_offset=2766666, timer=19666666, late=5966666),
 (120, "balance"):dict(early_duration=1966666, early_app_offset=896666, early_gl_offset=2466666,
                       hf_early_app_offset=446666, hf_early_gl_offset=1466666, timer=4666666, late=4466666),
 (144, "battery"):dict(early_duration=1722222, early_app_offset=663888, early_gl_offset=1805555,
                       hf_early_app_offset=330555, hf_early_gl_offset=972222, timer=7055555, late=3305555),
 (144, "gaming"): dict(early_duration=3055555, early_app_offset=1388888, early_gl_offset=3222222,
                       hf_early_app_offset=488888, hf_early_gl_offset=2305555, timer=16388888, late=4972222),
 (144, "balance"):dict(early_duration=1638888, early_app_offset=747222, early_gl_offset=2055555,
                       hf_early_app_offset=372222, hf_early_gl_offset=1222222, timer=3888888, late=3722222),
}

# debug.sf.* property (sans prefix) -> plan field name
PROP2FIELD = {
    "phase_offset_threshold_for_next_vsync_ns": "late",
    "region_sampling_period_ns": "late",
    "late.app.duration": "late",
    "late.sf.duration": "late",
    "high_fps_late_app_phase_offset_ns": "late",
    "high_fps_late_sf_phase_offset_ns": "late",
    "earlyGl.app.duration": "early_duration",
    "early.sf.duration": "early_duration",
    "region_sampling_duration_ns": "early_duration",
    "early.app.duration": "early_duration",
    "cached_set_render_duration_ns": "early_duration",
    "earlyGl.sf.duration": "early_duration",
    "region_sampling_timer_timeout_ns": "timer",
    "early_app_phase_offset_ns": "early_app_offset",
    "early_gl_app_phase_offset_ns": "early_app_offset",
    "high_fps_early_app_phase_offset_ns": "hf_early_app_offset",
    "high_fps_early_gl_app_phase_offset_ns": "hf_early_app_offset",
    "early_gl_phase_offset_ns": "early_gl_offset",
    "early_phase_offset_ns": "early_gl_offset",
    "high_fps_early_gl_phase_offset_ns": "hf_early_gl_offset",
    "high_fps_early_phase_offset_ns": "hf_early_gl_offset",
}

SF_LABEL = re.compile(r"^sf(60|90|120|144)(battery|gaming|balance)$")

# Fallback gate rows, used only when tools/gate_expectations.json is absent.
FALLBACK_EXPECT = {
    "min_backup_targets": 21,
    "required_backup_keys": [
        ["settings", "secure", "clock_seconds"],
        ["settings", "system", "status_bar_show_battery_percent"],
        ["settings", "global", "audio_safe_volume_state"],
        ["settings", "secure", "audio_safe_csd_as_a_feature_enabled"],
    ],
    "required_streams": [
        ["tw_clock", ["settings", "put", "secure", "clock_seconds", "1"]],
        ["tw_clock", ["settings", "delete", "secure", "clock_seconds"]],
        ["tw_batpct", ["settings", "put", "system", "status_bar_show_battery_percent", "1"]],
        ["tw_safevol_off", ["settings", "put", "global", "audio_safe_volume_state", "2"]],
        ["tw_safevol", ["settings", "put", "global", "audio_safe_volume_state", "3"]],
        ["tw_safevol_dose", ["cmd", "audio", "set-sound-dose-value", "0.0"]],
        ["tw_safevol_csdoff", ["settings", "put", "secure", "audio_safe_csd_as_a_feature_enabled", "0"]],
        ["tw_exp_put", ["settings", "put", "%EXP_NS%", "%EXP_KEY%", "!EXP_VAL!"]],
        ["tw_snap_take", ["settings", "list", "%%n"]],
    ],
}


def load_expectations(repo):
    """Gate rows, in priority order: the checkout's tools/ (lets a checkout pin
    its own), then this script's directory (how the skill carries them), then
    the built-in Tier-1 fallback. Returns (rows, source_description)."""
    here = Path(__file__).resolve().parent
    for f in (repo / "tools" / "gate_expectations.json", here / "gate_expectations.json"):
        if not f.is_file():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        if data.get("schema") != 1:
            raise SystemExit(f"{f}: unsupported schema {data.get('schema')!r}, expected 1")
        n = len(data.get("required_streams", []))
        return data, f"{f} ({n} stream rows)"
    return (FALLBACK_EXPECT,
            "BUILT-IN FALLBACK - no gate_expectations.json beside the script or "
            "in the repo, so only Tier-1 rows are checked")


# ---------------------------------------------------------------------------
# Low-level line helpers
# ---------------------------------------------------------------------------
ADB_WORD = re.compile(r"\badb(?:\.exe)?\b", re.I)
REDIR_OP = re.compile(r"^(?:\d?>>?|<)$")            # operator; target is next token
REDIR_SELF = re.compile(r"^\d?>>?&\d$")             # 2>&1 style, self-contained
REDIR_FUSED = re.compile(r"^(?:\d?>>?|<)\S+$")      # 2>nul, <nul, >"x" fused
IF_PREFIX = re.compile(
    r'^\s*if\s+(?:/i\s+)?(?:not\s+)?'
    r'(?:defined\s+\S+|exist\s+"[^"]*"|exist\s+\S+|errorlevel\s+\d+|'
    r'"[^"]*"\s*==\s*"[^"]*"|\S+\s+(?:EQU|NEQ|LSS|LEQ|GTR|GEQ)\s+\S+)\s+', re.I)


def strip_if_prefix(s: str) -> str:
    while True:
        m = IF_PREFIX.match(s)
        if not m:
            return s
        s = s[m.end():]


def decaret(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "^" and i + 1 < len(s):
            out.append(s[i + 1]); i += 2
        else:
            out.append(s[i]); i += 1
    return "".join(out)


def split_unquoted(s: str, seps: str):
    """Split s at any char in `seps` occurring outside double quotes."""
    parts, buf, q = [], [], False
    for ch in s:
        if ch == '"':
            q = not q; buf.append(ch)
        elif ch in seps and not q:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def tokens_of(s: str):
    """Whitespace-tokenize respecting double quotes (quotes kept)."""
    toks, buf, q = [], [], False
    for ch in s:
        if ch == '"':
            q = not q; buf.append(ch)
        elif ch.isspace() and not q:
            if buf: toks.append("".join(buf)); buf = []
        else:
            buf.append(ch)
    if buf: toks.append("".join(buf))
    return toks


def is_ignore_redir(tok: str) -> bool:
    t = tok.lower()
    return t in ("2>nul", ">nul", "2>&1", "1>nul") or t.startswith("2>nul")


class AdbCmd:
    __slots__ = ("form", "args", "ignore_errors", "line_no")

    def __init__(self, form, args, ignore_errors, line_no):
        self.form, self.args, self.ignore_errors, self.line_no = form, args, ignore_errors, line_no


def parse_adb_segment(seg: str, line_no: int, varmap: dict) -> AdbCmd | None:
    """seg starts at the token 'adb'. Strip Windows-side plumbing, resolve
    label-local literal %vars%, keep runtime placeholders symbolic."""
    seg = split_unquoted(seg, "|")[0]          # cut Windows-side pipes (device
    #   pipes are inside a quoted payload and survive the quote-aware split)
    seg = split_unquoted(seg, "&")[0]          # drop `& goto x` chains
    # trim a trailing unmatched `)` from `if cond (adb ...)` bodies
    if split_unquoted(seg, ")") != [seg]:
        head = split_unquoted(seg, ")")
        if head[0].count("(") <= 0:
            seg = head[0]
    ignore = False
    kept = []
    toks = tokens_of(seg)
    i = 0
    while i < len(toks):
        t = toks[i]
        if REDIR_SELF.match(t):
            if t.startswith("2"): ignore = True
            i += 1
            continue
        if REDIR_OP.match(t):
            if t.startswith("2"): ignore = True
            i += 2                        # operator + its target token
            continue
        if REDIR_FUSED.match(t):
            if t.lower().startswith("2>"): ignore = True
            i += 1
            continue
        kept.append(t)
        i += 1
    if not kept or kept[0].lower() not in ("adb", "adb.exe"):
        return None
    payload = []
    for t in kept[1:]:
        if t.startswith('"') and t.endswith('"') and len(t) >= 2:
            inner = t[1:-1]
            if "2>/dev/null" in inner:
                ignore = True
            payload.extend(inner.split())
        else:
            payload.append(t)
    # resolve label-local literal vars (e.g. %chm%); leave runtime ones alone
    res = []
    for t in payload:
        m = re.fullmatch(r"%([A-Za-z_][\w]*)%", t)
        if m and m.group(1) in varmap:
            res.append(varmap[m.group(1)])
        else:
            res.append(t)
    if not res:
        return None
    return AdbCmd(res[0], tuple(res[1:]), ignore, line_no)


# `adb` must be followed by whitespace to be an invocation. Without the lookahead the
# `\(` alternative also matches DCX's PATH probe -- `for %%A in (adb.exe) do ...` -- which
# names the executable but never runs it, and it surfaced as a permanent UNMAPPED line.
CMD_STARTS = re.compile(r"(?:^|\bdo\s+|\(|&\s*|\|\s*)\s*(adb(?:\.exe)?\b(?=\s).*)", re.I)
SET_RE = re.compile(r'^\s*(?:if\s+.*?\s+)?set\s+(?:"([^=]+)=([^"]*)"|(\S+?)=(\S*))\s*$', re.I)
SET_COND_RE = re.compile(r'^\s*if\s+"%BRANDCAT%"=="([^"]+)"\s+set\s+"([^=]+)=([^"]*)"', re.I)
FORF_RE = re.compile(r"in\s+\('(.+?)'\)\s+do\b", re.I)
PKGISH = re.compile(r"^[a-z][\w]*(\.[\w]+)+$")
# Two shapes. The keyed helpers take a namespace/key before the file; _bk_dcfgsync and
# _bk_wm capture a single whole-subsystem value (DeviceConfig sync mode, Display Scaler
# wm size/density) and take only the file. Leaving the second shape out undercounted the
# backup by two and, worse, meant deleting either capture would not have failed the gate.
# The capture list has since moved out of :backup into :_bk_capture_all, so that Backup and
# the restore preview read the same keys in the same order; inside that routine the outfile
# arrives as "%~1". Accept both spellings and both owning labels - with only the old pair the
# gate finds ZERO targets and reports every required key as missing, which is precisely what
# it did after that refactor. A gate that fails wholesale is as useless as one that passes
# wholesale: it stops naming the thing that actually broke.
_BK_OUT = r"\"(?:%BAKFILE%|%~1)\""
BK_RE = re.compile(r"^\s*call\s+:(_bk_settings|_bk_devcfg|_bk_prop)\s+(\S+)(?:\s+(\S+))?\s+" + _BK_OUT, re.I)
BK_WHOLE_RE = re.compile(r"^\s*call\s+:(_bk_dcfgsync|_bk_wm)\s+" + _BK_OUT, re.I)
BK_LABELS = ("backup", "_bk_capture_all")


def first_word(line: str) -> str:
    s = line.lstrip()
    while True:
        s2 = re.sub(r'^(?:@|\d?>>?"[^"]*"\s*|\d?>>?\S+\s*)', "", s)
        if s2 == s:
            break
        s = s2.lstrip()
    m = re.match(r"[\w.]+", s)
    return m.group(0).lower() if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parent.parent))
    args = ap.parse_args()
    repo = Path(args.repo)
    src = repo / "reference" / "DCX.bat"
    if not src.is_file():
        print(f"extract_baseline: {src} not found.\n"
              "Pass --repo pointing at a dcx-py checkout "
              "(needs reference/DCX.bat; dcx/data, tests/golden and tools/ are created).")
        return 2
    expect, expect_src = load_expectations(repo)
    raw = src.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8")
    lines = text.split("\r\n")

    label = "_prelude"
    streams: dict[str, list[AdbCmd]] = {label: []}
    order: list[str] = [label]
    varmap: dict[str, str] = {}
    sf_props: dict[str, list[tuple[str, str]]] = {}
    pkg_lists: dict[str, dict[str, dict[str | None, tuple]]] = {}
    backup_targets: list[tuple] = []
    report: list[str] = []
    unmapped: list[tuple[int, str]] = []
    exec_count = 0

    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("::") or first_word(line) == "rem":
            if "adb" in line.lower():
                report.append(f"L{n:<6} COMMENT  {stripped[:90]}")
            continue
        if re.match(r"^:[^:]", stripped):
            label = stripped[1:].split()[0]
            streams.setdefault(label, [])
            if label not in order:
                order.append(label)
            varmap = {}
            continue
        mset = SET_COND_RE.match(line)
        cond = None
        if mset:
            cond, var, val = mset.group(1), mset.group(2), mset.group(3)
        else:
            m2 = SET_RE.match(line)
            if m2:
                var = m2.group(1) or m2.group(3)
                val = m2.group(2) if m2.group(2) is not None else (m2.group(4) or "")
            else:
                var = None
        if var is not None:
            varmap[var] = val
            toksv = val.split()
            if toksv and all(PKGISH.match(t) for t in toksv):
                pkg_lists.setdefault(label, {}).setdefault(var, {})[cond] = tuple(toksv)
        mbk = BK_RE.match(line)
        if mbk and label in BK_LABELS:
            kind, a, b = mbk.group(1), mbk.group(2), mbk.group(3)
            if kind == "_bk_settings":
                backup_targets.append(("settings", a, b))
            elif kind == "_bk_devcfg":
                backup_targets.append(("device_config", a, b))
            else:
                backup_targets.append(("prop", a, None))
        mbw = BK_WHOLE_RE.match(line)
        if mbw and label in BK_LABELS:
            backup_targets.append((mbw.group(1)[4:], None, None))

        if not ADB_WORD.search(line):
            continue
        if first_word(line) == "echo":
            report.append(f"L{n:<6} TEXT     {stripped[:90]}")
            continue

        hunt = line
        mf = FORF_RE.search(line)
        if mf:
            hunt = decaret(mf.group(1))
        segments = [m.group(1) for m in CMD_STARTS.finditer(hunt)]
        bare = strip_if_prefix(hunt)
        if bare != hunt and re.match(r"\s*adb(?:\.exe)?\b", bare, re.I):
            segments.append(bare.strip())
        found = False
        for seg in segments:
            cmd = parse_adb_segment(seg, n, varmap)
            if cmd is None:
                continue
            streams[label].append(cmd)
            exec_count += 1
            report.append(f"L{n:<6} EXEC     ({label}, {len(streams[label]) - 1})  adb {cmd.form} {' '.join(cmd.args)[:70]}")
            found = True
            if cmd.form == "shell" and len(cmd.args) >= 3 and cmd.args[0] == "setprop" \
               and cmd.args[1].startswith("debug.sf."):
                sf_props.setdefault(label, []).append((cmd.args[1][len("debug.sf."):], cmd.args[2]))
        if found:
            pass
        elif segments:
            unmapped.append((n, stripped))
            report.append(f"L{n:<6} UNMAPPED {stripped[:90]}")
        else:
            report.append(f"L{n:<6} MENTION  {stripped[:90]}")

    # ---- SF table -----------------------------------------------------------
    sf_profiles: dict = {}
    sf_errors: list[str] = []
    for lab, props in sf_props.items():
        m = SF_LABEL.match(lab)
        if not m:
            continue
        key = (int(m.group(1)), m.group(2))
        fields: dict[str, int] = {}
        for prop, val in props:
            f = PROP2FIELD.get(prop)
            if f is None:
                sf_errors.append(f"{lab}: unknown SF prop {prop}")
                continue
            try:
                iv = int(val)
            except ValueError:
                sf_errors.append(f"{lab}: non-literal SF value {prop}={val}")
                continue
            if f in fields and fields[f] != iv:
                sf_errors.append(f"{lab}: field {f} carries two values {fields[f]} / {iv}")
            fields[f] = iv
        sf_profiles[key] = fields

    # ---- structural gate ----------------------------------------------------
    failures: list[str] = list(sf_errors)
    if sf_profiles != REVIEW_SF:
        for k in sorted(set(REVIEW_SF) | set(sf_profiles)):
            if sf_profiles.get(k) != REVIEW_SF.get(k):
                failures.append(f"SF review mismatch {k}: bat={sf_profiles.get(k)} plan={REVIEW_SF.get(k)}")
    min_bk = expect.get("min_backup_targets", 0)
    if len(backup_targets) < min_bk:
        failures.append(f"backup targets: expected >={min_bk}, found {len(backup_targets)}")
    for row in expect.get("required_backup_keys", []):
        if tuple(row) not in backup_targets:
            failures.append(f"backup targets missing required key {tuple(row)}")
    for lab, sub in expect.get("required_streams", []):
        cmds = streams.get(lab, [])
        if not any(_subseq(tuple(sub), (c.form,) + c.args) for c in cmds):
            failures.append(f"feature gate: {lab} stream lacks {tuple(sub)}")
    if unmapped:
        failures.append(f"{len(unmapped)} UNMAPPED adb line(s)")

    # ---- emit ----------------------------------------------------------------
    hdr = (f"# GENERATED by tools/extract_baseline.py v{EXTRACTOR_VERSION} — DO NOT EDIT.\n"
           f"# Source: reference/DCX.bat sha256={sha}\n")
    d = repo / "dcx" / "data"
    d.mkdir(parents=True, exist_ok=True)

    with open(d / "sf_profiles.py", "w", encoding="utf-8") as f:
        f.write(hdr + "\nSF_PROFILES = {\n")
        for k in sorted(sf_profiles):
            f.write(f"    {k!r}: {sf_profiles[k]!r},\n")
        f.write("}\n\nSF_PROP_GROUPS = {\n")
        for prop in sorted(PROP2FIELD):
            f.write(f"    {prop!r}: {PROP2FIELD[prop]!r},\n")
        f.write("}\n")

    with open(d / "keysets.py", "w", encoding="utf-8") as f:
        f.write(hdr + "\nfrom dataclasses import dataclass\n\n\n"
                "@dataclass(frozen=True)\nclass Cmd:\n"
                "    form: str\n    args: tuple\n    ignore_errors: bool = False\n\n\n"
                "LABEL_STREAMS = {\n")
        for lab in order:
            cmds = streams.get(lab, [])
            if not cmds:
                continue
            f.write(f"    {lab!r}: (\n")
            for c in cmds:
                f.write(f"        Cmd(form={c.form!r}, args={c.args!r}, ignore_errors={c.ignore_errors!r}),\n")
            f.write("    ),\n")
        f.write("}\n\nON_OFF_VIEWS = {\n")
        names = {lab for lab in order if streams.get(lab)}
        for lab in sorted(names):
            if lab.startswith("on") and ("off" + lab[2:]) in names:
                f.write(f"    {lab[2:]!r}: {{'on': {lab!r}, 'off': {'off' + lab[2:]!r}}},\n")
        f.write("}\n")

    with open(d / "packages.py", "w", encoding="utf-8") as f:
        f.write(hdr + "\nPACKAGE_LISTS = {\n")
        for lab in sorted(pkg_lists):
            f.write(f"    {lab!r}: {{\n")
            for var in sorted(pkg_lists[lab]):
                f.write(f"        {var!r}: {{\n")
                for cond, pkgs in pkg_lists[lab][var].items():
                    f.write(f"            {cond!r}: {pkgs!r},\n")
                f.write("        },\n")
            f.write("    },\n")
        f.write("}\n")

    with open(d / "backup_keys.py", "w", encoding="utf-8") as f:
        f.write(hdr + "\nBACKUP_TARGETS = (\n")
        for t in backup_targets:
            f.write(f"    {t!r},\n")
        f.write(")\n")

    baseline = {
        "schema": 1,
        "extractor_version": EXTRACTOR_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(),
        "source": {"file": "reference/DCX.bat", "sha256": sha, "lines": len(lines)},
        "adb_exec_count": exec_count,
        "actions": {
            lab: [
                {"form": c.form, "args": list(c.args),
                 "ignore_errors": c.ignore_errors, "line": c.line_no}
                for c in streams[lab]
            ]
            for lab in order if streams.get(lab)
        },
    }
    g = repo / "tests" / "golden"
    g.mkdir(parents=True, exist_ok=True)
    (g / "baseline.json").write_text(json.dumps(baseline, indent=1) + "\n", encoding="utf-8")

    rep = repo / "tools" / "coverage_report.txt"
    rep.parent.mkdir(parents=True, exist_ok=True)
    with open(rep, "w", encoding="utf-8") as f:
        f.write(f"extract_baseline v{EXTRACTOR_VERSION}  source sha256={sha}\n")
        f.write(f"exec={exec_count}  labels_with_streams={sum(1 for v in streams.values() if v)}  "
                f"unmapped={len(unmapped)}  backup_targets={len(backup_targets)}\n\n")
        f.write("\n".join(report) + "\n")

    if failures:
        print("GATE FAILED:")
        for msg in failures:
            print("  -", msg)
        return 1
    print(f"gate green: {exec_count} adb exec lines mapped, 0 UNMAPPED; "
          f"{len(baseline['actions'])} actions; {len(backup_targets)} backup targets; "
          f"SF table matches plan review copy; rows from {expect_src}")
    return 0


def _subseq(needle: tuple, hay: tuple) -> bool:
    it = iter(hay)
    return all(x in it for x in needle)


if __name__ == "__main__":
    sys.exit(main())
