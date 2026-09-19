"""Verify postwar section isolation without changing any gameplay nodes."""
from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

AUTOMATION = Path(__file__).resolve().parents[1]
BASE = "d6cc3c77078a25f7318fbf7e371fc6779eab3351"
HEAD = "90ddc600f82af943b41a942168738ee75b927ceb"
BRANCH = "refactor/vorkerland-readability"
EFFECTS = "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
TRIGGERS = "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
TEST = "tools/tests/test_vorkerland_readability_contracts.py"
P = "ADISCORD_vorkerland_"
DISPATCH = P + "continue_imperial_reunification"
TMP = Path(tempfile.mkdtemp(prefix="adiscord-postwar-boundary-"))
FOCUSED = [
    "tools/tests/test_adiscord_vorkerland_vad_postwar.py",
    "tools/tests/test_vorkerland_campaign_state.py",
    "tools/tests/test_vorkerland_central_war_variance.py",
    "tools/tests/test_adiscord_vorkerland_civil_war_focus.py",
    "tools/tests/test_adiscord_vorkerland_recovery.py",
    "tools/tests/test_validate_adiscord_modifier_fields.py",
]


def run(args, cwd=AUTOMATION, check=True):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=420)
    print("COMMAND", " ".join(args), "EXIT", result.returncode, flush=True)
    if check and result.returncode:
        print(result.stdout[-15000:], result.stderr[-6000:], flush=True)
        raise RuntimeError("Command failed")
    return result


def read(root, path):
    return (root / path).read_text(encoding="utf-8-sig")


def write(root, path, text):
    (root / path).write_bytes(text.encode("utf-8"))


def test_run(root, paths, name):
    xml = TMP / (name + ".xml")
    result = run([sys.executable, "-B", "-m", "pytest", *paths, "-q", "--tb=short", f"--junitxml={xml}"], cwd=root, check=False)
    assert result.returncode in (0, 1), result.stdout[-5000:] + result.stderr
    cases = list(ET.parse(xml).getroot().iter("testcase"))
    failures, errors = set(), set()
    for case in cases:
        identity = case.get("classname", "") + "::" + case.get("name", "")
        if case.find("failure") is not None:
            failures.add(identity)
        if case.find("error") is not None:
            errors.add(identity)
    (TMP / (name + ".log")).write_text(result.stdout + result.stderr)
    print(name, "TOTAL", len(cases), "FAILURES", sorted(failures), "ERRORS", sorted(errors), flush=True)
    print(result.stdout[-2000:], flush=True)
    return failures, errors


def validator(root, name):
    result = run([sys.executable, "-B", "tools/validate_tc.py", "--limit", "300"], cwd=root, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    # validate_tc reports advisory diagnostics even when its process exits 0.
    # Compare every diagnostic instead of treating that exit code as a clean bill.
    diagnostics = Counter(line.strip() for line in (result.stdout + result.stderr).splitlines() if line.startswith("- "))
    print(name, "VALIDATOR DIAGNOSTICS", sum(diagnostics.values()), flush=True)
    for diagnostic in diagnostics:
        print(diagnostic, flush=True)
    (TMP / (name + "-validator.log")).write_text(result.stdout + result.stderr)
    return diagnostics


run(["git", "fetch", "--depth=1", "origin", BASE, HEAD])
baseline, work = TMP / "baseline", TMP / "work"
run(["git", "worktree", "add", "--detach", str(baseline), BASE])
run(["git", "worktree", "add", "--detach", str(work), HEAD])
sys.path.insert(0, str(work))
from tools.lib.paths import source_section
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

baseline_failures, baseline_errors = test_run(baseline, FOCUSED, "baseline")
baseline_diagnostics = validator(baseline, "baseline")
assert len(baseline_diagnostics) == 5, baseline_diagnostics

# RED: enforce that wartime wave validation cannot consume postwar declarations.
tests = read(work, TEST)
addition = '''
    def test_postwar_dispatch_is_separate_from_wartime_wave_section(self):
        from tools.lib.paths import source_section
        effects = read(EFFECTS)
        self.assertIn(DISPATCH + " = {", source_section(effects, "phase_effects"))
        self.assertNotIn(DISPATCH + " = {", source_section(effects, "focus_decision_effects"))

'''
assert "test_postwar_dispatch_is_separate_from_wartime_wave_section" not in tests
assert tests.count('if __name__ == "__main__":') == 1
write(work, TEST, tests.replace('if __name__ == "__main__":', addition + '\nif __name__ == "__main__":'))
red_failures, red_errors = test_run(work, [TEST], "red-boundary")
assert not red_errors
assert len(red_failures) == 1 and next(iter(red_failures)).endswith("test_postwar_dispatch_is_separate_from_wartime_wave_section")

# GREEN: move one new, self-contained block; keep its content byte-for-byte.
source = read(work, EFFECTS)
start = source.index("# POSTWAR IMPERIAL RECLAMATION\n")
end = source.index("# --- force_design_effects ---", start)
payload = source[start:end]
assert len(parse_clausewitz(payload)) == 1
assert parse_clausewitz(payload)[0].key == DISPATCH
assert payload in source_section(source, "focus_decision_effects")
source = source[:start] + source[end:]
phase_end = source.index("# --- release_effects ---")
source = source[:phase_end] + payload + source[phase_end:]
source = source.replace("# focus_decision_effects = player orders; phase_effects = transitions and handoff.", "# focus_decision_effects = wartime orders; phase_effects = handoff and postwar orders.")
write(work, EFFECTS, source)

# Prove the original five gameplay files still expand to exactly BASE.
helpers = {}
for path, names in ((TRIGGERS, (P + "is_imperial_reclamation_target", P + "has_imperial_reclamation_target")), (EFFECTS, (DISPATCH,))):
    for entry in parse_clausewitz(read(work, path)):
        if entry.key in names:
            assert entry.key not in helpers
            helpers[entry.key] = entry.value
assert len(helpers) == 3


def canonical(entries):
    result = []
    for entry in entries:
        if entry.key in helpers and entry.value == "yes":
            result.extend(canonical(helpers[entry.key]))
        else:
            result.append((entry.key, canonical(entry.value) if isinstance(entry.value, list) else entry.value, entry.quoted))
    return result


runtime = [EFFECTS, TRIGGERS, "common/decisions/ADISCORD_vorkerland_decisions.txt", "common/ideas/ADISCORD_vorkerland_ideas.txt", "common/national_focus/ADISCORD_vorkerland_focus.txt"]
for path in runtime:
    actual = [entry for entry in parse_clausewitz(read(work, path)) if entry.key not in helpers]
    assert canonical(parse_clausewitz(read(baseline, path))) == canonical(actual), path
    assert not (work / path).read_bytes().startswith(b"\xef\xbb\xbf"), path
print("ALL FIVE GAMEPLAY FILES EQUIVALENT TO BASE AFTER THREE HELPER EXPANSIONS", flush=True)

new_failures, new_errors = test_run(work, [TEST], "new-contracts")
assert not new_failures and not new_errors
final_failures, final_errors = test_run(work, FOCUSED + [TEST], "final-focused")
assert final_failures == baseline_failures and final_errors == baseline_errors
final_diagnostics = validator(work, "final")
assert final_diagnostics == baseline_diagnostics, (final_diagnostics - baseline_diagnostics, baseline_diagnostics - final_diagnostics)
print("NO NEW VALIDATOR DIAGNOSTICS: baseline 5, final 5", flush=True)

run(["git", "diff", "--check"], cwd=work)
run(["git", "add", "--", EFFECTS, TEST], cwd=work)
run(["git", "-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit", "-m", "refactor: isolate postwar declarations from wartime wave contracts"], cwd=work)
commit = run(["git", "rev-parse", "HEAD"], cwd=work).stdout.strip()
run(["git", "diff", "--check", BASE, commit], cwd=work)
print(run(["git", "diff", "--stat", BASE, commit], cwd=work).stdout, flush=True)
run(["git", "push", "origin", commit + ":refs/heads/" + BRANCH], cwd=work)
print("FINAL_VERIFIED_COMMIT=" + commit, flush=True)
print("BASELINE_TEST_FAILURES=" + repr(sorted(baseline_failures)), flush=True)
print("FINAL_TEST_FAILURES=" + repr(sorted(final_failures)), flush=True)
