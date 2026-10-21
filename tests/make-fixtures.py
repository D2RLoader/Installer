"""Writes the manifest test files in tests/fixtures/manifests.

A file named ok-*.json must be accepted by the installer. A file named bad-*.json must be rejected.
Each bad file breaks exactly one rule of docs/manifest.md. Files named ok-real-* are kept as they are.

Run: python -I tests/make-fixtures.py
"""

import copy
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "fixtures" / "manifests"
SHA = "93021dad48533bcfca8a95c69a0cc00cdb9008a3ce6ceba1d04c7aca71985a10"


def good():
	return {
		"schema": 1,
		"version": "1.0.0-test",
		"files": [
			{
				"path": "D2RLoader.exe",
				"url": "https://d2rloader.net/download/D2RLoader.exe",
				"size": 1234,
				"sha256": SHA,
			}
		],
		"folders": ["mods"],
	}


def with_file(**changes):
	data = good()
	data["files"][0].update(changes)
	return data


def without_file_key(key):
	data = good()
	del data["files"][0][key]
	return data


def with_top(**changes):
	data = good()
	data.update(changes)
	return data


def without_top(key):
	data = good()
	del data[key]
	return data


def two_files(path_a, path_b):
	data = good()
	second = copy.deepcopy(data["files"][0])
	data["files"][0]["path"] = path_a
	second["path"] = path_b
	data["files"].append(second)
	return data


OK = {
	"ok-minimal": without_top("folders"),
	"ok-two-files": two_files("D2RLoader.exe", "d2rloader/config/d2rloader.toml"),
	"ok-only-if-missing-true": with_file(onlyIfMissing=True),
	"ok-only-if-missing-false": with_file(onlyIfMissing=False),
	"ok-unknown-fields": {**good(), "note": "ignored", "files": [{**good()["files"][0], "extra": [1, 2, 3]}]},
	"ok-uppercase-scheme": with_file(url="HTTPS://d2rloader.net/download/D2RLoader.exe"),
	"ok-size-one": with_file(size=1),
	"ok-size-four-gib": with_file(size=4294967296),
	"ok-folders-empty": with_top(folders=[]),
	"ok-nested-folder": with_top(folders=["d2rloader/plugins/data"]),
	"ok-brackets-in-text": with_file(path="mods/[a]/{b}.txt"),
	"ok-unicode-path": with_file(path="mods/\u00dcn\u00ef/\u0411.txt"),
	"ok-version-64-chars": with_top(version="v" * 64),
}

BAD = {
	"bad-schema-two": with_top(schema=2),
	"bad-schema-zero": with_top(schema=0),
	"bad-schema-text": with_top(schema="1"),
	"bad-schema-missing": without_top("schema"),
	"bad-version-missing": without_top("version"),
	"bad-version-empty": with_top(version=""),
	"bad-version-too-long": with_top(version="v" * 65),
	"bad-version-number": with_top(version=1),
	"bad-files-missing": without_top("files"),
	"bad-files-empty": with_top(files=[]),
	"bad-files-not-list": with_top(files="D2RLoader.exe"),
	"bad-files-entry-not-object": with_top(files=["D2RLoader.exe"]),
	"bad-path-missing": without_file_key("path"),
	"bad-path-number": with_file(path=5),
	"bad-path-empty": with_file(path=""),
	"bad-path-dotdot": with_file(path="../D2R.exe"),
	"bad-path-dotdot-inside": with_file(path="mods/../../D2R.exe"),
	"bad-path-dot": with_file(path="mods/./a"),
	"bad-path-backslash": with_file(path="mods\\a.txt"),
	"bad-path-drive": with_file(path="C:/Windows/x.dll"),
	"bad-path-stream": with_file(path="D2RLoader.exe:evil"),
	"bad-path-double-slash": with_file(path="mods//a"),
	"bad-path-leading-slash": with_file(path="/mods/a"),
	"bad-path-trailing-slash": with_file(path="mods/"),
	"bad-path-trailing-dot": with_file(path="mods/a."),
	"bad-path-trailing-space": with_file(path="mods/a "),
	"bad-url-missing": without_file_key("url"),
	"bad-url-number": with_file(url=5),
	"bad-url-http": with_file(url="http://d2rloader.net/download/D2RLoader.exe"),
	"bad-url-http-loopback-no-port": with_file(url="http://127.0.0.1/x"),
	"bad-url-ftp": with_file(url="ftp://d2rloader.net/D2RLoader.exe"),
	"bad-url-file": with_file(url="file:///C:/Windows/System32/cmd.exe"),
	"bad-url-no-scheme": with_file(url="d2rloader.net/download/D2RLoader.exe"),
	"bad-size-missing": without_file_key("size"),
	"bad-size-zero": with_file(size=0),
	"bad-size-negative": with_file(size=-5),
	"bad-size-fraction": with_file(size=1.5),
	"bad-size-text": with_file(size="1234"),
	"bad-size-over-limit": with_file(size=4294967297),
	"bad-size-huge": with_file(size=10 ** 15),
	"bad-sha-missing": without_file_key("sha256"),
	"bad-sha-short": with_file(sha256=SHA[:63]),
	"bad-sha-long": with_file(sha256=SHA + "0"),
	"bad-sha-uppercase": with_file(sha256=SHA.upper()),
	"bad-sha-not-hex": with_file(sha256="g" * 64),
	"bad-sha-number": with_file(sha256=5),
	"bad-only-if-missing-text": with_file(onlyIfMissing="yes"),
	"bad-only-if-missing-number": with_file(onlyIfMissing=1),
	"bad-only-if-missing-null": with_file(onlyIfMissing=None),
	"bad-duplicate-path": two_files("D2RLoader.exe", "D2RLoader.exe"),
	"bad-duplicate-path-case": two_files("D2RLoader.exe", "D2RLOADER.EXE"),
	"bad-folders-not-list": with_top(folders="mods"),
	"bad-folders-entry-number": with_top(folders=[5]),
	"bad-folders-dotdot": with_top(folders=["../mods"]),
	"bad-folders-backslash": with_top(folders=["mods\\a"]),
}

RAW_BAD = {
	"bad-empty": "",
	"bad-not-json": "this is not json",
	"bad-root-array": "[]",
	"bad-root-string": '"text"',
	"bad-root-number": "5",
	"bad-truncated": '{"schema": 1, "files": [',
	"bad-missing-comma": '{"schema": 1 "version": "x"}',
	"bad-trailing-text": json.dumps(good()) + " extra",
	"bad-duplicate-key": '{"schema": 1, "schema": 1, "version": "x", "files": []}',
	"bad-deep-nesting": '{"schema": 1, "version": "x", "files": [], "x": ' + "[" * 20 + "]" * 20 + "}",
	"bad-deep-nesting-unclosed": '{"schema": 1, "x": ' + "[" * 3000,
	"bad-unterminated-string": '{"schema": 1, "version": "x',
}


def main():
	OUT.mkdir(parents=True, exist_ok=True)
	for old in list(OUT.glob("bad-*.json")) + list(OUT.glob("ok-*.json")):
		if not old.name.startswith("ok-real-"):
			old.unlink()
	for name, data in OK.items():
		(OUT / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
	for name, data in BAD.items():
		(OUT / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
	for name, text in RAW_BAD.items():
		(OUT / f"{name}.json").write_text(text, encoding="utf-8")
	print(f"{len(OK)} ok, {len(BAD) + len(RAW_BAD)} bad, plus the ok-real files")


if __name__ == "__main__":
	main()
