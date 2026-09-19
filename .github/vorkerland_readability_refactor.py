"""Apply a bounded refactor in an isolated runner; publish only verified files."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

BASE = "d6cc3c77078a25f7318fbf7e371fc6779eab3351"
BRANCH = "refactor/vorkerland-readability"
P = "ADISCORD_vorkerland_"
D = "common/decisions/ADISCORD_vorkerland_decisions.txt"
E = "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
T = "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
I = "common/ideas/ADISCORD_vorkerland_ideas.txt"
F = "common/national_focus/ADISCORD_vorkerland_focus.txt"
OLD_TEST = "tools/tests/test_adiscord_vorkerland_vad_postwar.py"
CAMPAIGN_TEST = "tools/tests/test_vorkerland_campaign_state.py"
NEW_TEST = "tools/tests/test_vorkerland_readability_contracts.py"
DOC = "docs/development/focus-effects.md"
FILES = (D, E, T, I, F, OLD_TEST, CAMPAIGN_TEST, NEW_TEST, DOC)
RUNTIME = (D, E, T, I, F)
TARGET = P + "is_imperial_reclamation_target"
HAS_TARGET = P + "has_imperial_reclamation_target"
DISPATCH = P + "continue_imperial_reunification"
DECISION = P + "vad_continue_imperial_reunification"
TARGETS = "EYR EGC RIV REV YOR NDN SWB VHV OSV ZAO PWR VLA ROM TRU WPA WPS PSD EBA DVA SRA ZTA CSL IBA IBL TGD".split()
CONDITION = "exists = yes is_subject = no NOT = { has_capitulated = yes } NOT = { has_war_with = WRK } NOT = { is_in_faction_with = WRK }"
TMP = Path(tempfile.mkdtemp(prefix="adiscord-readability-"))


def run(args, *, check=True, env=None):
    result = subprocess.run(args, text=True, capture_output=True, env=env, timeout=360)
    print("COMMAND", " ".join(args), "EXIT", result.returncode, flush=True)
    if check and result.returncode:
        print(result.stdout[-12000:], result.stderr[-6000:], flush=True)
        raise RuntimeError("Command failed")
    return result


def read(path):
    return Path(path).read_text(encoding="utf-8-sig")


def write(path, text):
    old = Path(path).read_bytes() if Path(path).exists() else b""
    data = text.encode("utf-8")
    if old.startswith(b"\xef\xbb\xbf"):
        data = b"\xef\xbb\xbf" + data
    Path(path).write_bytes(data)


def span(source, name):
    matches = list(re.finditer(rf"(?m)^[ \t]*{re.escape(name)}\s*=\s*\{{", source))
    if len(matches) != 1:
        raise AssertionError(f"Expected one block {name}; got {len(matches)}")
    match = matches[0]
    opening = source.index("{", match.start(), match.end())
    depth, quoted, escaped, comment = 0, False, False, False
    for pos in range(opening, len(source)):
        char = source[pos]
        if comment:
            comment = char != "\n"
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == "#":
            comment = True
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return match.start(), pos + 1, opening
    raise AssertionError(f"Unclosed block {name}")


def block(source, name):
    start, end, _ = span(source, name)
    return source[start:end]


def inner(source, name):
    _, end, opening = span(source, name)
    return textwrap.dedent(source[opening + 1:end - 1].strip("\n" )).strip()


def replace_block(source, name, replacement):
    start, end, _ = span(source, name)
    return source[:start] + replacement + source[end:]


def insert_in_section(source, section, addition):
    marker = re.compile(r"(?m)^# --- ([a-z_]+) ---[ \t]*$")
    markers = list(marker.finditer(source))
    matching = [n for n, item in enumerate(markers) if item[1] == section]
    assert len(matching) == 1, section
    n = matching[0]
    pos = markers[n + 1].start() if n + 1 < len(markers) else len(source)
    return source[:pos].rstrip() + "\n\n" + addition.rstrip() + "\n\n" + source[pos:]


def canonical(entries, definitions=None):
    definitions = definitions or {}
    result = []
    for entry in entries:
        if entry.key in definitions and entry.value == "yes":
            result.extend(canonical(definitions[entry.key], definitions))
        else:
            value = canonical(entry.value, definitions) if isinstance(entry.value, list) else entry.value
            result.append((entry.key, value, entry.quoted))
    return result


def failures(path):
    root = ET.parse(path).getroot()
    failed, errored = set(), set()
    count = 0
    for case in root.iter("testcase"):
        count += 1
        identity = case.get("classname", "") + "::" + case.get("name", "")
        if case.find("failure") is not None:
            failed.add(identity)
        if case.find("error") is not None:
            errored.add(identity)
    return count, failed, errored


def test_run(paths, label):
    xml = TMP / (label + ".xml")
    result = run([sys.executable, "-B", "-m", "pytest", *paths, "-q", "--tb=short", f"--junitxml={xml}"], check=False)
    (TMP / (label + ".log")).write_text(result.stdout + result.stderr)
    assert result.returncode in (0, 1), result.stdout[-10000:] + result.stderr
    stats = failures(xml)
    print("TESTS", label, "total", stats[0], "failures", sorted(stats[1]), "errors", sorted(stats[2]), flush=True)
    print(result.stdout[-3000:], flush=True)
    return result.returncode, stats


# Establish the exact baseline. The automation branch changes only its runner
# and tests; its gameplay source must still be identical to the selected base.
run(["git", "fetch", "--depth=1", "origin", BASE])
for path in RUNTIME:
    assert run(["git", "rev-parse", f"HEAD:{path}"]).stdout == run(["git", "rev-parse", f"{BASE}:{path}"]).stdout, path
before = {path: read(path) for path in RUNTIME}
focused = [OLD_TEST, CAMPAIGN_TEST,
    "tools/tests/test_vorkerland_central_war_variance.py",
    "tools/tests/test_adiscord_vorkerland_civil_war_focus.py",
    "tools/tests/test_adiscord_vorkerland_recovery.py",
    "tools/tests/test_validate_adiscord_modifier_fields.py"]
_, baseline_tests = test_run(focused, "baseline")
baseline_validator = run([sys.executable, "-B", "tools/validate_tc.py", "--limit", "300"], check=False)
(TMP / "baseline-validator.log").write_text(baseline_validator.stdout + baseline_validator.stderr)
print("BASELINE VALIDATOR", (baseline_validator.stdout + baseline_validator.stderr)[-7000:], flush=True)
red_code, red_stats = test_run([NEW_TEST], "red")
assert red_code == 1 and red_stats[1] and not red_stats[2], "Expected failing behavior contracts, not import errors"

# Move the action body intact; replace the five repeated predicates only.
source = before[D]
old_decision = block(source, DECISION)
assert old_decision.count(CONDITION) == 50
assert re.findall(r"declare_war_on\s*=\s*\{\s*target\s*=\s*([A-Z]{3})", old_decision) == TARGETS
payload = inner(old_decision, "complete_effect").replace(CONDITION, TARGET + " = yes")
new_decision = replace_block(old_decision, "available", "\t\tavailable = {\n\t\t\thas_war = no\n\t\t\t" + HAS_TARGET + " = yes\n\t\t}")
new_decision = replace_block(new_decision, "complete_effect", "\t\tcomplete_effect = { " + DISPATCH + " = yes }")
source = source.replace(old_decision, new_decision, 1)
old_comment = "\t# Ordinary Vlad route: restore the empire one surviving administration at a\n\t# time instead of opening a dozen simultaneous AI wars. The decision becomes\n\t# available again after each war ends, so the player/AI can roll the former\n\t# Vorkerland space back into the imperial state in a controlled sequence."
assert old_comment in source
source = source.replace(old_comment, "\t# POSTWAR: ordinary Vlad restoration, executed by the successor tag WRK.\n\t# Availability and dispatch use the same candidate predicate. The existing\n\t# war check serializes declarations; target priority belongs to the effect.")
write(D, source)

trigger_source = """# Imperial reclamation: candidate scope and actor scope are separate.
# COUNTRY candidate: relations are checked against the fixed successor WRK.
# ROOT/PREV would depend on whether the caller is the decision or dispatcher.
""" + TARGET + " = {\n" + "\n".join("\t" + line for line in (
    "exists = yes", "is_subject = no", "NOT = { has_capitulated = yes }",
    "NOT = { has_war_with = WRK }", "NOT = { is_in_faction_with = WRK }")) + "\n}\n\n"
trigger_source += "# COUNTRY WRK: keep this bounded list in the dispatcher's priority order.\n" + HAS_TARGET + " = {\n\tOR = {\n"
trigger_source += "\n".join("\t\t" + tag + " = { " + TARGET + " = yes }" for tag in TARGETS)
trigger_source += "\n\t}\n}\n"
write(T, insert_in_section(before[T], "diplomacy_triggers", trigger_source))

reclamation_effect = """# POSTWAR IMPERIAL RECLAMATION
# COUNTRY WRK: called after the decision checks its unlock, cost and peace.
# Recheck every candidate at execution. The exclusive chain starts exactly
# one war and preserves the authored priority; do not replace it with a loop.
""" + DISPATCH + " = {\n" + textwrap.indent(payload, "\t") + "\n}\n"
source = insert_in_section(before[E], "focus_decision_effects", reclamation_effect)
source = source.replace("# Applied once, to the seventeen central states, when the wars open. The states", "# Applied once to the 37 listed central-theatre states when wars open. The states")
source = source.replace("\t# TFR-style hidden theatre normalization. The three claimants are supposed\n\t# to roll over fragmented district governments; their real contest is with\n\t# one another. Keep this active for both AI and player claimants throughout\n\t# the live collapse, not only after the central showdown has already begun.", "\t# COUNTRY WKR/VAD/TVA: only the listed minor opponents receive the combat\n\t# overmatch. Player and AI claimants share its wartime lifecycle.")
write(E, source)

# Only the hidden group is re-indented. All native fields retain their order.
source = before[I]
hidden = block(source, "hidden_ideas")
lines, depth = [], 1
for raw in hidden.splitlines():
    stripped = raw.strip()
    if not stripped:
        lines.append("")
        continue
    code = stripped.split("#", 1)[0]
    indentation = depth - (1 if code.startswith("}") else 0)
    lines.append("\t" * indentation + stripped)
    depth += code.count("{") - code.count("}")
assert depth == 1
source = replace_block(source, "hidden_ideas", "\n".join(lines))
source = source.replace("# coalition ideas are AI-only brakes against a claimant holding a true majority.", "# Coalition support is AI-only and uses the configured control-score threshold.")
write(I, source)

# Human-readable navigation must not introduce source_section delimiters.
headers = {
    E: "# Vorkerland effects: lifecycle, campaign state, diplomacy and postwar actions.\n# Navigation: campaign_state_effects = control/legitimacy/assistance;\n# collapse_effects = materialization; diplomacy_effects = regional relations;\n# focus_decision_effects = player orders; phase_effects = transitions and handoff.\n# Registered section markers below are also consumed by validators.\n\n",
    T: "# Vorkerland predicates. COUNTRY is the default scope unless documented.\n# Navigation: collapse_triggers = participants; diplomacy_triggers = relations;\n# phase_triggers = lifecycle; stalemate_triggers = recovery;\n# rus_last_empire_triggers = the northern campaign.\n\n",
    D: "# Vorkerland decisions: keep visibility, price and timing at the UI boundary.\n# Navigation: allied_support_decisions; collapse_decisions; diplomacy_decisions;\n# focus_operations_decisions (including postwar reclamation and integration);\n# rom_tru_decisions; rus_last_empire_decisions.\n\n",
    F: "# Vorkerland focus trees. Phase visibility and winner routes remain separate.\n# Navigation: civil_war_focus includes preparation, claimant campaigns and\n# the worker/joint/technocratic postwar branches; collapse_focus and zao_focus\n# hold the regional trees. Keep existing focus IDs and layout anchors stable.\n\n",
}
for path, header in headers.items():
    write(path, header + read(path))

# Update the one caller-level assertion whose action body moved into an effect.
source = read(OLD_TEST)
old = '        for tag in ("EYR", "EGC", "VLA", "ROM", "ZTA", "TGD"):\n            self.assertIn(f"declare_war_on = {{ target = {tag} type = annex_everything }}", reclaim)'
new = '        self.assertIn("ADISCORD_vorkerland_continue_imperial_reunification = yes", reclaim)\n        dispatch = named_block(\n            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),\n            "ADISCORD_vorkerland_continue_imperial_reunification",\n        )\n        for tag in ("EYR", "EGC", "VLA", "ROM", "ZTA", "TGD"):\n            self.assertIn(f"declare_war_on = {{ target = {tag} type = annex_everything }}", dispatch)'
assert source.count(old) == 1
write(OLD_TEST, source.replace(old, new))
source = read(CAMPAIGN_TEST)
source = source.replace("def test_coalition_requires_a_territorial_majority(self)", "def test_coalition_uses_the_configured_early_lead_threshold(self)")
write(CAMPAIGN_TEST, source)

write(DOC, read(DOC).rstrip() + """

### Vorkerland postwar campaign boundaries

Keep country content in the existing files by engine data type. Section markers
are consumed by `source_section`; navigation comments are not new sections.

`ADISCORD_vorkerland_vad_continue_imperial_reunification` owns the decision's
visibility, 25 political-power cost, peace gate and 14-day re-enable interval.
The successor is `WRK`, even when the displayed country is the Vorkerland Empire.
`ADISCORD_vorkerland_is_imperial_reclamation_target` runs in each candidate's
country scope and checks existence, independence, capitulation, war and faction
relations with WRK. Use boolean scripted-trigger calls, not macro argument blocks.
`ADISCORD_vorkerland_has_imperial_reclamation_target` uses a bounded tag list;
`ADISCORD_vorkerland_continue_imperial_reunification` rechecks those candidates
in an exclusive chain and declares at most one war. Keep both lists in identical
priority order. SOL retains its separate settlement path. There is no world scan,
persistent selected-target cache, or extra campaign-active flag.

The central control score counts 37 explicitly marked states. The current
coalition threshold is greater than 8, an early-lead setting rather than a
territorial majority. Keep balance changes separate from structural refactors.
The contract tests cover the target truth table, order, scope, unlock and prices;
static expansion checks do not replace a fresh native-load and campaign check.
""")

# Expand only the three new boolean helpers and compare every original script
# node. This detects changes to scopes, condition order, effects and constants.
helpers = {}
for path, names in ((T, (TARGET, HAS_TARGET)), (E, (DISPATCH,))):
    for entry in parse_clausewitz(read(path)):
        if entry.key in names:
            helpers[entry.key] = entry.value
assert set(helpers) == {TARGET, HAS_TARGET, DISPATCH}
for path in RUNTIME:
    after = parse_clausewitz(read(path))
    if path in (E, T):
        after = [entry for entry in after if entry.key not in helpers]
    assert canonical(parse_clausewitz(before[path])) == canonical(after, helpers), "Semantic drift: " + path
    assert not Path(path).read_bytes().startswith(b"\xef\xbb\xbf"), path
print("EQUIVALENCE PASS: all original nodes in five gameplay files; three helper expansions", flush=True)
print("DECISION LINES", len(old_decision.splitlines()), "->", len(new_decision.splitlines()), flush=True)

_, green_stats = test_run(focused + [NEW_TEST], "green")
normalized_baseline = {name.replace("test_coalition_requires_a_territorial_majority", "test_coalition_uses_the_configured_early_lead_threshold") for name in baseline_tests[1]}
assert green_stats[1] <= normalized_baseline, "New test failures: " + str(green_stats[1] - normalized_baseline)
assert green_stats[2] <= baseline_tests[2], "New collection/test errors"
new_code, _ = test_run([NEW_TEST], "contracts")
assert new_code == 0, "New contracts must all pass"
after_validator = run([sys.executable, "-B", "tools/validate_tc.py", "--limit", "300"], check=False)
(TMP / "after-validator.log").write_text(after_validator.stdout + after_validator.stderr)
print("FINAL VALIDATOR", (after_validator.stdout + after_validator.stderr)[-7000:], flush=True)
if after_validator.returncode:
    # The full gate can require a locally installed HOI4 tree. Preserve and
    # report a pre-existing failure rather than claiming a clean runtime gate.
    assert baseline_validator.returncode == after_validator.returncode
    def stable_log(result):
        text = result.stdout + result.stderr
        text = re.sub(r"\b\d+\.\d+s\b", "<time>", text)
        return text
    assert stable_log(after_validator) == stable_log(baseline_validator), "Full-validator output changed; inspect before publishing"

# Construct a clean tree directly from BASE. Temporary runner/workflow files
# never enter the deliverable commit; only the explicitly verified paths do.
env = dict(os.environ, GIT_INDEX_FILE=str(TMP / "publish.index"),
    GIT_AUTHOR_NAME="github-actions[bot]", GIT_COMMITTER_NAME="github-actions[bot]",
    GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
    GIT_COMMITTER_EMAIL="41898282+github-actions[bot]@users.noreply.github.com")
run(["git", "read-tree", BASE], env=env)
run(["git", "add", "--", *FILES], env=env)
tree = run(["git", "write-tree"], env=env).stdout.strip()
commit = run(["git", "commit-tree", tree, "-p", BASE, "-m", "refactor: clarify Vorkerland imperial campaign boundaries"], env=env).stdout.strip()
changed = set(run(["git", "diff", "--name-only", BASE, commit]).stdout.splitlines())
assert changed == set(FILES), changed
run(["git", "diff", "--check", BASE, commit])
print(run(["git", "diff", "--stat", BASE, commit]).stdout, flush=True)
print("PUBLISH", commit, "TREE", tree, flush=True)
run(["git", "push", "origin", commit + ":refs/heads/" + BRANCH])
print("VERIFIED_COMMIT=" + commit, flush=True)
print("BASELINE_FAILURES=" + repr(sorted(baseline_tests[1])), flush=True)
print("FINAL_FAILURES=" + repr(sorted(green_stats[1])), flush=True)
