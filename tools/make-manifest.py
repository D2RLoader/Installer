"""Makes the manifest and the download files for one D2RLoader release.

It reads the release zip that the D2RLoader build writes (D2RLoader-<version>.zip). It unpacks each file into the
output folder under its plain file name, and writes manifest.json next to them. The manifest has the size and the
SHA-256 hash of every file. Upload the whole output folder to the web address (the default is https://d2rloader.net/download/).

	python -I tools/make-manifest.py <release.zip> <output folder>
	python -I tools/make-manifest.py <release.zip> <output folder> --version 1.4.0 --base-url https://example.org/files/

The output folder must not exist yet, or it must be empty. If the zip has a file with the name <release.zip>.sha256 next to it,
the script checks the zip against it first.

The rules are in docs/manifest.md. The script follows the same rules as the installer. It stops with an error if the release
breaks one of them, so it never writes a manifest that the installer would reject.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

DEFAULT_BASE_URL = "https://d2rloader.net/download/"
ONLY_IF_MISSING = {"d2rloader/config/d2rloader.toml"}  # The user edits these. Setup writes them only when they are missing.
MAX_FILES, MAX_FOLDERS, MAX_SIZE, MAX_MANIFEST_CHARS = 200, 100, 4 * 1024 ** 3, 262_144


class ReleaseError(Exception):
	pass


def path_error(path):
	"""Why `path` is not allowed in the manifest, or None. These are the path rules of docs/manifest.md."""
	if not path:
		return "it is empty"
	if "\\" in path or ":" in path:
		return "it has a backslash or a colon"
	for name in path.split("/"):
		if name in ("", ".", ".."):
			return "it has an empty name, or the name . or .."
		if name.endswith((".", " ")):
			return "a name in it ends with a dot or a space"
	return None


def check_zip_sha256(zip_path):
	"""Checks the zip against <zip>.sha256 (the line 'hash  name' that the D2RLoader build writes), if that file exists."""
	checksum = zip_path.with_name(zip_path.name + ".sha256")
	if not checksum.is_file():
		print(f"Note: {checksum.name} was not found. The zip was not checked against it.")
		return
	fields = checksum.read_text(encoding="utf-8").split(None, 1)
	if len(fields) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", fields[0]) or fields[1].strip() != zip_path.name:
		raise ReleaseError(f"{checksum.name} has a format that this script does not know. Expected: <64 hex digits>  {zip_path.name}")
	digest = hashlib.sha256()
	with open(zip_path, "rb") as stream:
		for chunk in iter(lambda: stream.read(1 << 20), b""):
			digest.update(chunk)
	if digest.hexdigest() != fields[0].lower():
		raise ReleaseError(f"The zip does not match {checksum.name}. Do not publish it.")


def release_version(zip_path, given):
	version = given
	if version is None:
		found = re.fullmatch(r"D2RLoader-(.+)\.zip", zip_path.name)
		if not found:
			raise ReleaseError(f"Cannot read the version from the file name {zip_path.name}. Give it with --version.")
		version = found.group(1)
	if not 1 <= len(version) <= 64:
		raise ReleaseError("The version must have 1 to 64 characters.")
	return version


def base_url_error(base_url):
	if base_url.startswith("https://"):
		return None
	if base_url.startswith("http://127.0.0.1:"):
		print("Warning: this address is only for the test installer. The real installer accepts https:// only.")
		return None
	return "The base address must start with https://"


def read_entries(archive):
	"""Returns (files, folders). files is a list of (path, ZipInfo). folders is a list of paths."""
	files, folders = [], []
	for info in archive.infolist():
		path = info.filename.rstrip("/") if info.is_dir() else info.filename
		reason = path_error(path)
		if reason:
			raise ReleaseError(f"The zip has the entry '{info.filename}' and {reason}.")
		if info.is_dir():
			folders.append(path)
			continue
		if info.file_size == 0 or info.file_size > MAX_SIZE:
			raise ReleaseError(f"'{path}' has the size {info.file_size}. The size must be from 1 byte to 4 GiB.")
		files.append((path, info))
	return files, folders


def leaf_folders(folders, files):
	"""Folders that no file and no other folder is inside. Setup makes the folders of the files by itself."""
	parents = set()
	for path in [path for path, _ in files] + folders:
		parts = path.split("/")
		parents.update("/".join(parts[:count]) for count in range(1, len(parts)))
	return [folder for folder in folders if folder not in parents]


def check_names_are_unique(files):
	"""No two paths may be the same without letter case, and no two files may have the same plain name (they share one web folder)."""
	for label, names in (("path", [path for path, _ in files]), ("file name", [path.rsplit("/", 1)[-1] for path, _ in files])):
		seen = set()
		for name in names:
			if name.lower() in seen:
				raise ReleaseError(f"Two files have the same {label} ('{name}', without letter case).")
			seen.add(name.lower())


def write_release(archive, files, out_dir, base_url):
	"""Unpacks the files into out_dir and returns the manifest entries."""
	entries = []
	for path, info in files:
		name = path.rsplit("/", 1)[-1]
		digest, size = hashlib.sha256(), 0
		with archive.open(info) as source, open(out_dir / name, "wb") as target:
			for chunk in iter(lambda: source.read(1 << 20), b""):
				digest.update(chunk)
				target.write(chunk)
				size += len(chunk)
		if size != info.file_size:
			raise ReleaseError(f"'{path}' has {size} bytes in the zip, but the zip header says {info.file_size}.")
		entry = {"path": path, "url": base_url + quote(name), "size": size, "sha256": digest.hexdigest()}
		if path in ONLY_IF_MISSING:
			entry["onlyIfMissing"] = True
		entries.append(entry)
	return entries


def make(zip_path, out_dir, version, base_url):
	if not zip_path.is_file():
		raise ReleaseError(f"The zip was not found: {zip_path}")
	check_zip_sha256(zip_path)
	version = release_version(zip_path, version)
	reason = base_url_error(base_url)
	if reason:
		raise ReleaseError(reason)
	base_url = base_url if base_url.endswith("/") else base_url + "/"

	if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
		raise ReleaseError(f"The output folder is not empty: {out_dir}")

	with zipfile.ZipFile(zip_path) as archive:
		files, folders = read_entries(archive)
		check_names_are_unique(files)
		folders = leaf_folders(folders, files)
		if not 1 <= len(files) <= MAX_FILES:
			raise ReleaseError(f"The zip has {len(files)} files. The manifest allows 1 to {MAX_FILES}.")
		if len(folders) > MAX_FOLDERS:
			raise ReleaseError(f"The zip has {len(folders)} empty folders. The manifest allows {MAX_FOLDERS}.")

		created = not out_dir.exists()
		out_dir.mkdir(parents=True, exist_ok=True)
		try:
			entries = write_release(archive, files, out_dir, base_url)
			manifest = {"schema": 1, "version": version, "files": entries, "folders": folders}
			text = json.dumps(manifest, indent=2) + "\n"
			if len(text) > MAX_MANIFEST_CHARS:
				raise ReleaseError(f"The manifest has {len(text)} characters. The limit is {MAX_MANIFEST_CHARS}.")
			(out_dir / "manifest.json").write_text(text, encoding="utf-8", newline="\n")
		except BaseException:
			if created:
				shutil.rmtree(out_dir, ignore_errors=True)
			raise
	return manifest


def main():
	parser = argparse.ArgumentParser(description="Makes the manifest and the download files for one D2RLoader release.")
	parser.add_argument("zip", type=Path, help="the release zip (D2RLoader-<version>.zip)")
	parser.add_argument("out", type=Path, help="the output folder (new or empty)")
	parser.add_argument("--version", help="the release name for the manifest (default: from the zip name)")
	parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"the web folder of the files (default: {DEFAULT_BASE_URL})")
	args = parser.parse_args()
	try:
		manifest = make(args.zip, args.out, args.version, args.base_url)
	except (ReleaseError, zipfile.BadZipFile, OSError) as error:
		print("ERROR: " + str(error), file=sys.stderr)
		return 1

	print(f"Release {manifest['version']}: {len(manifest['files'])} files, {len(manifest['folders'])} empty folders")
	for item in manifest["files"]:
		print(f"  {item['size']:>12,}  {item['sha256'][:12]}  {item['path']}" + ("  (only if missing)" if item.get("onlyIfMissing") else ""))
	print(f"Upload the files in {args.out} to {args.base_url if args.base_url.endswith('/') else args.base_url + '/'}")
	print("Upload manifest.json last.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
