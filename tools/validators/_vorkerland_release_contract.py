"""Scope-aware structural checks shared by the collapse/recovery gates."""

from __future__ import annotations

import re


def _braced_block(text: str, start: int) -> str:
    brace = text.find("{", start)
    if brace < 0:
        return ""
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def direct_named_blocks(text: str, name: str) -> list[str]:
    """Return balanced blocks named *name* that are direct children of text."""
    opener = text.find("{")
    if opener < 0:
        return []
    blocks: list[str] = []
    pattern = re.compile(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{")
    for match in pattern.finditer(text):
        depth = text[opener : match.start()].count("{") - text[opener : match.start()].count("}")
        if depth == 1:
            block = _braced_block(text, match.start())
            if block:
                blocks.append(block)
    return blocks


def direct_statements(text: str, name: str) -> list[str]:
    """Return scalar assignments named *name* at the block's immediate scope."""
    opener = text.find("{")
    if opener < 0:
        return []
    pattern = re.compile(rf"(?m)\b{re.escape(name)}\s*=\s*([^{{}}\s]+)")
    values: list[str] = []
    for match in pattern.finditer(text):
        depth = text[opener : match.start()].count("{") - text[opener : match.start()].count("}")
        if depth == 1:
            values.append(match.group(1))
    return values


def direct_block_sequence(text: str) -> list[tuple[str, str, int, int]]:
    """Return direct if/else blocks with their exact source spans."""
    names = ("if", "else_if", "else")
    matches: list[tuple[int, str, str, int]] = []
    opener = text.find("{")
    for name in names:
        pattern = re.compile(rf"(?m)^\s*{name}\s*=\s*\{{")
        for match in pattern.finditer(text):
            depth = text[opener : match.start()].count("{") - text[opener : match.start()].count("}")
            if depth == 1:
                block = _braced_block(text, match.start())
                if block:
                    matches.append((match.start(), name, block, match.start() + len(block)))
    return [(name, block, start, end) for start, name, block, end in sorted(matches)]


def _direct_limit_has(limit: str, *tokens: str) -> bool:
    return all(
        "yes" in direct_statements(limit, token.split(" = ", 1)[0])
        for token in tokens
    ) and not direct_named_blocks(limit, "FROM")


def _direct_from_has(limit: str, *tokens: str) -> bool:
    from_blocks = direct_named_blocks(limit, "FROM")
    return len(from_blocks) == 1 and all(
        token in from_blocks[0] for token in tokens
    ) and all(
        token in direct_statements(from_blocks[0], token.split(" = ", 1)[0])
        for token in ()
    )


def validate_release_interceptor_structure(interceptor: str, issues: list[str]) -> None:
    """Reject routing that merely contains required tokens in wrong scopes."""
    outer_if = direct_named_blocks(interceptor, "if")
    outer_else_if = direct_named_blocks(interceptor, "else_if")
    if len(outer_if) != 1 or len(outer_else_if) != 1:
        issues.append("premature WRK shared interceptor must have one outer if and one else_if")
        return
    if interceptor.find("if = {") > interceptor.find("else_if = {"):
        issues.append("premature WRK shared interceptor branch order must be if then else_if")
    current = outer_if[0]
    outer_limits = direct_named_blocks(current, "limit")
    if len(outer_limits) != 1 or not _direct_limit_has(
        outer_limits[0], "ADISCORD_vorkerland_is_premature_wrk = yes"
    ):
        issues.append("premature WRK current-country guard must be a direct outer limit")
    if "ADISCORD_vorkerland_premature_wrk_release_intercepted_v1" not in direct_statements(current, "set_global_flag"):
        issues.append("premature WRK current-country flag must be a direct effect")
    current_nested = direct_named_blocks(current, "if")
    current_else = direct_named_blocks(current, "else")
    if len(current_nested) != 1 or len(current_else) != 1:
        issues.append("premature WRK current-country branch must have claimant if/else")
    else:
        claimant_limit = direct_named_blocks(current_nested[0], "limit")
        from_scopes = direct_named_blocks(claimant_limit[0], "FROM") if claimant_limit else []
        if len(from_scopes) != 1 or not (
            "yes" in direct_statements(from_scopes[0], "ADISCORD_vorkerland_is_main_claimant")
            and "yes" in direct_statements(from_scopes[0], "exists")
            and "no" in direct_statements(from_scopes[0], "is_subject")
            and any(
                direct_statements(block, "has_capitulated") == ["yes"]
                and not direct_named_blocks(block, "ROOT")
                and not direct_named_blocks(block, "FROM")
                for block in direct_named_blocks(from_scopes[0], "NOT")
            )
        ):
            issues.append("premature WRK claimant branch lacks exact live independent FROM guard")
        dissolve = direct_named_blocks(current_nested[0], "FROM")
        if len(dissolve) != 1 or "yes" not in direct_statements(dissolve[0], "ADISCORD_vorkerland_dissolve_premature_wrk_as_claimant"):
            issues.append("premature WRK claimant branch must dissolve through FROM")
        if "yes" not in direct_statements(current_else[0], "ADISCORD_vorkerland_route_premature_wrk_release_to_living_claimant"):
            issues.append("premature WRK current-country fallback must route in current scope")
    inverse = outer_else_if[0]
    inverse_limits = direct_named_blocks(inverse, "limit")
    inverse_from = direct_named_blocks(inverse_limits[0], "FROM") if inverse_limits else []
    inverse_not = direct_named_blocks(inverse_limits[0], "NOT") if inverse_limits else []
    if len(inverse_limits) != 1 or len(inverse_from) != 1 or len(inverse_not) != 1 or "yes" not in direct_statements(inverse_from[0], "ADISCORD_vorkerland_is_premature_wrk") or direct_statements(inverse_not[0], "has_global_flag") != ["ADISCORD_vorkerland_premature_wrk_subject_cleanup_active"] or direct_named_blocks(inverse_not[0], "ROOT") or direct_named_blocks(inverse_not[0], "FROM"):
        issues.append("premature WRK inverse branch lacks cleanup and FROM liveness guards")
    if "ADISCORD_vorkerland_premature_wrk_release_intercepted_v1" not in direct_statements(inverse, "set_global_flag"):
        issues.append("premature WRK inverse branch lacks interception flag")
    if "yes" not in direct_statements(inverse, "ADISCORD_vorkerland_route_premature_wrk_release_to_living_claimant"):
        issues.append("premature WRK inverse branch lacks current-scope routing")


def validate_release_hook_normal_branches(on_actions: str, named_block, issues: list[str]) -> None:
    """Require each hook's differentiated normal else branch."""
    expected = {
        "on_puppet": (True, True),
        "on_release_as_puppet": (True, True),
        "on_release_as_free": (False, True),
    }
    for hook_name, (needs_sync, needs_cosmetic) in expected.items():
        hook = named_block(on_actions, hook_name)
        effect_blocks = direct_named_blocks(hook, "effect")
        normal_source = effect_blocks[0] if len(effect_blocks) == 1 else hook
        sequence = direct_block_sequence(normal_source)
        guard_pairs = []
        for index, (kind, block, _, _) in enumerate(sequence[:-1]):
            if kind != "if" or sequence[index + 1][0] != "else":
                continue
            limits = direct_named_blocks(block, "limit")
            if len(limits) == 1 and _direct_limit_has(
                limits[0], "ADISCORD_vorkerland_release_requires_interception = yes"
            ) and "yes" in direct_statements(
                block, "ADISCORD_vorkerland_intercept_premature_wrk_release"
            ):
                guard_pairs.append((index, block, sequence[index + 1][1]))
        if len(guard_pairs) != 1:
            issues.append(f"{hook_name} must expose one paired interception if/else")
            continue
        pair_index, _, normal = guard_pairs[0]
        _, _, normal_start, normal_end = sequence[pair_index + 1]
        outside_text = normal_source[:normal_start] + normal_source[normal_end:]
        normal_behavior_patterns = (
            ("ADISCORD_vorkerland_sync_republics_from_ruins", r"\bADISCORD_vorkerland_sync_republics_from_ruins\s*="),
            ("VLA tag guard", r"\btag\s*=\s*VLA\b"),
            ("VLA subject guard", r"\bis_subject_of\s*=\s*(?:WKR|WRK)\b"),
            ("ADISCORD_vorkerland_wrk_activate_vla_auxiliaries", r"\bADISCORD_vorkerland_wrk_activate_vla_auxiliaries\s*="),
            ("independence cosmetic tag guard", r"\btag\s*=\s*(?:ROM|TRU|ZAO|SOL)\b"),
            ("ADISCORD_vorkerland_sync_independence_cosmetic", r"\bADISCORD_vorkerland_sync_independence_cosmetic\s*="),
        )
        for behavior, pattern in normal_behavior_patterns:
            if re.search(pattern, outside_text):
                issues.append(f"{hook_name} normal behavior exists outside paired else: {behavior}")
        if needs_sync and "ADISCORD_vorkerland_sync_republics_from_ruins = yes" not in normal:
            issues.append(f"{hook_name} normal branch lacks republic sync")
        if not needs_sync and "ADISCORD_vorkerland_sync_republics_from_ruins = yes" in normal:
            issues.append(f"{hook_name} normal branch must not sync republics")
        conditional_blocks = direct_named_blocks(normal, "if") + direct_named_blocks(normal, "else_if")
        cosmetic_blocks = [
            block for block in conditional_blocks
            if re.search(r"limit\s*=\s*\{\s*OR\s*=\s*\{\s*tag = ROM\s+tag = TRU\s+tag = ZAO\s+tag = SOL\s*\}\s*\}", block)
        ]
        if needs_cosmetic and (
            len(cosmetic_blocks) != 1
            or "ADISCORD_vorkerland_sync_independence_cosmetic = yes" not in cosmetic_blocks[0]
            or "ADISCORD_vorkerland_sync_independence_cosmetic" in direct_statements(normal, "ADISCORD_vorkerland_sync_independence_cosmetic")
        ):
            issues.append(f"{hook_name} normal branch lacks ROM/TRU/ZAO/SOL cosmetics")
        if hook_name == "on_puppet":
            for scope in ("WKR", "WRK"):
                blocks = []
                for block in conditional_blocks:
                    limits = direct_named_blocks(block, "limit")
                    if len(limits) == 1 and (
                        "VLA" in direct_statements(limits[0], "tag")
                        and scope in direct_statements(limits[0], "is_subject_of")
                    ):
                        blocks.append(block)
                aux_scopes = direct_named_blocks(blocks[0], scope) if len(blocks) == 1 else []
                if len(blocks) != 1 or len(aux_scopes) != 1 or "yes" not in direct_statements(aux_scopes[0], "ADISCORD_vorkerland_wrk_activate_vla_auxiliaries"):
                    issues.append(f"on_puppet normal branch lacks exact VLA {scope} auxiliary branch")
