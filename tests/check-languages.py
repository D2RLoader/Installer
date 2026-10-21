"""Checks the translation files in src/languages.

- Every language file has exactly the names of english.isl (a missing name would show English text, and an extra name is a typo).
- Each text has the same % codes as the English text (%1 is replaced by Setup).
- Each file is UTF-8 with a byte order mark (Inno Setup needs it for letters that are not ASCII).
- Every CustomMessage('Name') and {cm:Name} in the code has an English text, and every English text is used.
- Every language in the [Languages] section of installer.iss has a file, and every file is in the section.

Run: python -I tests/check-languages.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ROOT / "src" / "languages"
# Standard Inno Setup texts that our code or our [Tasks] use. They come from Inno Setup, not from our files.
FROM_INNO = {"CreateDesktopIcon", "AdditionalIcons"}

failures = []


def check(ok, text):
	print(("PASS " if ok else "FAIL ") + text)
	if not ok:
		failures.append(text)


def read(path):
	raw = path.read_bytes()
	return raw.startswith(b"\xef\xbb\xbf"), raw.decode("utf-8-sig")


def parse(text):
	"""Returns {section: {name: text}}."""
	sections, current = {}, None
	for line in text.splitlines():
		line = line.strip()
		if not line or line.startswith(";"):
			continue
		if line.startswith("[") and line.endswith("]"):
			current = line[1:-1]
			sections[current] = {}
		elif current is not None and "=" in line:
			name, _, value = line.partition("=")
			sections[current][name] = value
	return sections


def codes(text):
	return sorted(re.findall(r"%\d|%n|%%", text))


def main():
	_, english_text = read(LANGUAGES / "english.isl")
	english = parse(english_text)
	check({"Messages", "CustomMessages"} <= set(english), "english.isl has [Messages] and [CustomMessages]")

	# The languages that the script lists, and the files.
	script = (ROOT / "src" / "installer.iss").read_text(encoding="utf-8")
	listed = re.findall(r'^Name: "([a-z]+)"; MessagesFile: "compiler:[^"]+,languages\\([a-z]+)\.isl"', script, re.M)
	files = {path.stem for path in LANGUAGES.glob("*.isl")}
	check(all(name == stem for name, stem in listed), "each language in installer.iss uses the file with its own name")
	check({stem for _, stem in listed} == files, f"installer.iss lists exactly the language files ({len(files)})")

	for path in sorted(LANGUAGES.glob("*.isl")):
		if path.name == "english.isl":
			continue
		bom, text = read(path)
		check(bom, f"{path.name}: UTF-8 with a byte order mark")
		parsed = parse(text)
		for section in ("Messages", "CustomMessages"):
			have, want = parsed.get(section, {}), english[section]
			check(set(have) == set(want), f"{path.name}: [{section}] has the names of english.isl"
				+ ("" if set(have) == set(want) else f" (missing {sorted(set(want) - set(have))}, extra {sorted(set(have) - set(want))})"))
			bad = [name for name in want if name in have and codes(have[name]) != codes(want[name])]
			check(not bad, f"{path.name}: [{section}] keeps the % codes" + ("" if not bad else f" (check {bad})"))
			empty = [name for name, value in have.items() if not value.strip()]
			check(not empty, f"{path.name}: [{section}] has no empty text" + ("" if not empty else f" ({empty})"))

	# The code uses names that exist.
	used = set()
	for path in list((ROOT / "src").glob("*.iss")) + list((ROOT / "src").glob("*.pas")):
		code = path.read_text(encoding="utf-8")
		used |= set(re.findall(r"CustomMessage\('([A-Za-z0-9]+)'\)", code))
		used |= set(re.findall(r"\{cm:([A-Za-z0-9]+)\}", code))
	known = set(english["CustomMessages"])
	missing = sorted(used - known - FROM_INNO)
	check(not missing, "every CustomMessage in the code has an English text" + ("" if not missing else f" (missing {missing})"))
	unused = sorted(known - used)
	check(not unused, "every English text is used in the code" + ("" if not unused else f" (not used: {unused})"))

	print(f"\n{len(failures)} failed" if failures else "\nALL LANGUAGE CHECKS PASSED")
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
