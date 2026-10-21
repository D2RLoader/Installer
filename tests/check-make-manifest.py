"""Tests for tools/make-manifest.py. They make small fake release zips in a temporary folder.

The test of the real result (the installer installs from the files that the script writes) is test_make_manifest in e2e.py.

Run: python -I tests/check-make-manifest.py
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("make_manifest", ROOT / "tools" / "make-manifest.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)

DIRS = ["mods/", "d2rloader/", "d2rloader/config/", "d2rloader/data/", "d2rloader/plugins/", "d2rloader/logs/", "d2rloader/crashes/"]
FILES = {"D2RLoader.exe": b"MZ-exe" * 100, "D2RCore.dll": b"dll" * 500, "d2rloader.mpq": bytes(range(256)) * 20,
	"d2rloader/config/d2rloader.toml": b"# config\n"}
BASE = "https://d2rloader.net/download/"

failures = []


def check(ok, text):
	print(("PASS " if ok else "FAIL ") + text)
	if not ok:
		failures.append(text)


def make_zip(folder, name="D2RLoader-1.2.3.zip", entries=None, dirs=DIRS, checksum=True):
	"""Writes a release zip like the D2RLoader build. `entries` is {name: bytes}. Returns the path."""
	path = folder / name
	with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
		for directory in dirs:
			archive.writestr(directory, b"")
		for entry, data in (FILES if entries is None else entries).items():
			archive.writestr(entry, data)
	if checksum:
		path.with_name(path.name + ".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n")
	return path


def run(zip_path, out, version=None, base=BASE):
	"""Returns (manifest, None) or (None, error text). The tool prints notes; they are not part of the result."""
	try:
		with contextlib.redirect_stdout(io.StringIO()):
			return tool.make(zip_path, out, version, base), None
	except tool.ReleaseError as error:
		return None, str(error)


def rejects(work, what, text_part, **how):
	"""The tool must stop with an error that has `text_part`, and must leave no output folder."""
	folder = Path(tempfile.mkdtemp(dir=work))
	entries = how.pop("entries", None)
	zip_options = {key: how.pop(key) for key in ("name", "dirs", "checksum") if key in how}
	zip_path = make_zip(folder, entries=entries, **zip_options)
	after = how.pop("after", None)
	if after:
		after(zip_path)
	out = folder / "site"
	manifest, error = run(zip_path, out, **how)
	check(manifest is None and error is not None and text_part in error and not out.exists(), f"rejects {what}" + ("" if error else " (no error)")
		+ ("" if error is None or text_part in error else f" (error was: {error})"))


def main():
	work = Path(tempfile.mkdtemp(prefix="d2rl-manifest-"))
	try:
		# A good release, like the real one.
		folder = Path(tempfile.mkdtemp(dir=work))
		zip_path = make_zip(folder)
		out = folder / "site"
		manifest, error = run(zip_path, out)
		check(error is None, "a good release is accepted" + (f" ({error})" if error else ""))
		manifest = manifest or {}
		written = json.loads((out / "manifest.json").read_text(encoding="utf-8")) if (out / "manifest.json").exists() else {}
		check(written == manifest, "manifest.json has the manifest that the tool returns")
		check(manifest.get("schema") == 1 and manifest.get("version") == "1.2.3", "schema is 1, and the version comes from the zip name")
		files = {item["path"]: item for item in manifest.get("files", [])}
		check(set(files) == set(FILES), "the manifest lists the four files")
		check(all(item["size"] == len(FILES[path]) and item["sha256"] == hashlib.sha256(FILES[path]).hexdigest() for path, item in files.items()),
			"each file has its real size and SHA-256 hash")
		check(all(item["url"] == BASE + path.rsplit("/", 1)[-1] for path, item in files.items()), "each url is the base address plus the plain file name")
		check(all((out / path.rsplit("/", 1)[-1]).read_bytes() == data for path, data in FILES.items()), "the files are unpacked under their plain names")
		check([path for path, item in files.items() if item.get("onlyIfMissing")] == ["d2rloader/config/d2rloader.toml"], "only the config file is 'only if missing'")
		check(sorted(manifest.get("folders", [])) == ["d2rloader/crashes", "d2rloader/data", "d2rloader/logs", "d2rloader/plugins", "mods"],
			"folders are the empty folders (not the parents of files)")
		check(sorted(path.name for path in out.iterdir()) == sorted(["manifest.json", "D2RLoader.exe", "D2RCore.dll", "d2rloader.mpq", "d2rloader.toml"]),
			"the output folder has the files and the manifest, and nothing else")

		# Options.
		folder = Path(tempfile.mkdtemp(dir=work))
		manifest, error = run(make_zip(folder), folder / "site", version="9.9.9-x", base="https://example.org/files")
		check(error is None and manifest["version"] == "9.9.9-x" and manifest["files"][0]["url"] == "https://example.org/files/D2RLoader.exe",
			"--version is used, and a base address without / at the end gets one")
		folder = Path(tempfile.mkdtemp(dir=work))
		manifest, error = run(make_zip(folder, checksum=False), folder / "site", base="http://127.0.0.1:8000/dl/")
		check(error is None and manifest["files"][0]["url"].startswith("http://127.0.0.1:8000/dl/"), "a loopback address is allowed (for the test installer), and a missing .sha256 file is not an error")
		folder = Path(tempfile.mkdtemp(dir=work))
		(folder / "site").mkdir()
		manifest, error = run(make_zip(folder), folder / "site")
		check(error is None, "an existing empty output folder is accepted")
		folder = Path(tempfile.mkdtemp(dir=work))
		manifest, error = run(make_zip(folder, name="D2RLoader-1.4.0-beta-preview.1.zip"), folder / "site")
		check(error is None and manifest["version"] == "1.4.0-beta-preview.1", "a version with a dash and a dot is read from the name")

		# Zips that must be rejected. The rule is in docs/manifest.md.
		rejects(work, "a wrong .sha256", "does not match", after=lambda z: z.with_name(z.name + ".sha256").write_text("0" * 64 + "  " + z.name))
		rejects(work, "a .sha256 with a wrong format", "format", after=lambda z: z.with_name(z.name + ".sha256").write_text("not a hash"))
		rejects(work, "a .sha256 for another zip name", "format", after=lambda z: z.with_name(z.name + ".sha256").write_text("0" * 64 + "  other.zip"))
		rejects(work, "a zip name without a version", "--version", name="release.zip")
		rejects(work, "a version over 64 characters", "1 to 64", version="v" * 65)
		rejects(work, "an entry with ..", "..", entries={**FILES, "mods/../D2R.exe": b"x"})
		rejects(work, "a drive letter", "colon", entries={**FILES, "C:/Windows/x.dll": b"x"})
		rejects(work, "a name that ends with a dot", "dot", entries={**FILES, "a./x.txt": b"x"})
		rejects(work, "a name that ends with a space", "space", entries={**FILES, "a /x.txt": b"x"})
		rejects(work, "a path that starts with /", "empty name", entries={**FILES, "/x.txt": b"x"})
		rejects(work, "an empty file", "size", entries={**FILES, "empty.txt": b""})
		rejects(work, "a zip without files", "0 files", entries={})
		rejects(work, "the same path in two letter cases", "same path", entries={**FILES, "D2RLOADER.EXE": b"other"})
		rejects(work, "two files with the same plain name", "same file name", entries={**FILES, "mods/d2rcore.dll": b"other"})
		rejects(work, "more than 200 files", "201 files", entries={f"f{number}.bin": b"x" for number in range(201)})
		rejects(work, "more than 100 empty folders", "101 empty folders", dirs=[f"folder{number}/" for number in range(101)])
		rejects(work, "an address that is not https", "https://", base="http://example.org/")
		rejects(work, "an address with a loopback look-alike", "https://", base="http://127.0.0.1.example.org/")

		# An output folder that has files must stay as it is.
		folder = Path(tempfile.mkdtemp(dir=work))
		(folder / "site").mkdir()
		(folder / "site" / "keep.txt").write_text("keep")
		manifest, error = run(make_zip(folder), folder / "site")
		check(manifest is None and error and "not empty" in error and [p.name for p in (folder / "site").iterdir()] == ["keep.txt"],
			"rejects an output folder with files, and leaves it as it is")
		manifest, error = run(folder / "missing.zip", folder / "other-site")
		check(manifest is None and error and "was not found" in error and not (folder / "other-site").exists(), "rejects a zip that does not exist")

		# The command line: exit code and message.
		folder = Path(tempfile.mkdtemp(dir=work))
		zip_path = make_zip(folder, entries={"empty.txt": b""})
		sys.argv = ["make-manifest.py", str(zip_path), str(folder / "site")]
		errors = io.StringIO()
		with contextlib.redirect_stderr(errors):
			code = tool.main()
		check(code == 1 and errors.getvalue().startswith("ERROR: "), "the command line exits with 1 and prints ERROR: for a bad release")
		sys.argv = ["make-manifest.py", str(make_zip(folder / "..", name="D2RLoader-3.0.0.zip")), str(folder / "good")]
		with contextlib.redirect_stdout(io.StringIO()) as shown:
			code = tool.main()
		check(code == 0 and "Release 3.0.0: 4 files, 5 empty folders" in shown.getvalue(), "the command line exits with 0 and prints a summary for a good release")
	finally:
		import shutil
		shutil.rmtree(work, ignore_errors=True)

	print(f"\n{len(failures)} failed" if failures else "\nALL MANIFEST TOOL CHECKS PASSED")
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
