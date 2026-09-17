from pathlib import Path


def main() -> None:
    decisions = Path("common/decisions/ADISCORD_STP_decisions.txt")
    text = decisions.read_text(encoding="utf-8")
    old = (
        "\t\t\thas_war_with = STP\n"
        "\t\t\tcontrols_state = 3\n"
        "\t\t\tNOT = { has_country_flag = STP_cw_last_banquet_launched }\n"
        "\t\t\tNOT = {"
    )
    new = (
        "\t\t\thas_war_with = STP\n"
        "\t\t\tcontrols_state = 3\n"
        "\t\t\tNOT = {"
    )
    if text.count(old) != 1:
        raise SystemExit(
            f"expected one duplicated Last Banquet availability guard, found {text.count(old)}"
        )
    decisions.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    loc = Path("localisation/russian/ADISCORD_STP_l_russian.yml")
    raw = loc.read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        raise SystemExit("Russian localisation lost UTF-8 BOM before verification")
    text = raw.decode("utf-8-sig")
    old = ' STP_cw_command_power_35_cost: "£command_power §Y35§!"'
    new = "\n".join(
        (
            ' STP_cw_command_power_35_cost: "£command_power_texticon §Y35§!"',
            ' STP_cw_command_power_35_cost_blocked: "£command_power_texticon §R35§!"',
            ' STP_cw_command_power_35_cost_tooltip: "Стоимость: £command_power_texticon §Y35§!"',
        )
    )
    if text.count(old) != 1:
        raise SystemExit(f"expected one provisional CP35 key, found {text.count(old)}")
    if "STP_cw_command_power_35_cost_blocked:" in text:
        raise SystemExit("CP35 blocked key already exists unexpectedly")
    text = text.replace(old, new, 1)
    loc.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    if not loc.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise SystemExit("Russian localisation lost UTF-8 BOM after normalization")


if __name__ == "__main__":
    main()
