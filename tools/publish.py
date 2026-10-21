"""Uploads a release to the website over SSH. The easy way is publish-release.cmd and publish-installer.cmd in the main folder.

	python -I tools/publish.py release <release.zip> [--target test|live] [--allow-preview] [--yes]
	python -I tools/publish.py installer [--yes]

"release" makes the manifest from the zip (like make-release.cmd), shows what it will upload, and asks you to type yes.
Then it uploads the release ZIP and the four files, and uploads manifest.json last. Then it downloads every file from the
public address and checks its size and SHA-256. The target "test" uses the folder test/ on the server, without the ZIP.
"installer" uploads out/D2RLoader-Installer.exe to the live folder.

The settings are in publish.env (not committed; see publish.env.example). The script runs the programs ssh and scp from your PATH,
so the key, the port, and the user come from your SSH configuration. No password or key is in the project.
Each file is uploaded into a temporary folder on the server, and then moved into place, so nobody gets a half-written file.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "publish.env"
INSTALLER = ROOT / "out" / "D2RLoader-Installer.exe"
KNOWN_KEYS = {"SSH_TARGET", "REMOTE_DIR", "PUBLIC_URL"}
SAFE_NAME = re.compile(r"[A-Za-z0-9._-]+")
TEST_FOLDER = "test"


class PublishError(Exception):
	pass


def load_tool(file_name, module_name):
	spec = importlib.util.spec_from_file_location(module_name, ROOT / "tools" / file_name)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


# ---- Settings ----

def read_settings(path):
	"""Reads publish.env: lines of NAME=value. Returns a dict with the three checked values."""
	if not path.is_file():
		raise PublishError(f"{path.name} was not found. Copy publish.env.example to publish.env and change the values.")
	values = {}
	for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
		line = line.strip()
		if not line or line.startswith("#"):
			continue
		name, separator, value = line.partition("=")
		if not separator or name.strip() not in KNOWN_KEYS:
			raise PublishError(f"{path.name}, line {number}: '{line}' is not a setting. Write NAME=value, with one of these names: {', '.join(sorted(KNOWN_KEYS))}.")
		values[name.strip()] = value.strip()
	missing = sorted(KNOWN_KEYS - set(values))
	if missing:
		raise PublishError(f"{path.name} does not have: {', '.join(missing)}.")

	# The values go into commands for the server, so only plain characters are allowed.
	if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._@-]*", values["SSH_TARGET"]):
		raise PublishError("SSH_TARGET may have only letters, digits, . _ @ - and must not start with a dash. Use a Host entry from ~/.ssh/config.")
	directory = values["REMOTE_DIR"].rstrip("/")
	if not re.fullmatch(r"(/[A-Za-z0-9._-]+){2,}", directory) or {".", ".."} & set(directory.split("/")):
		raise PublishError("REMOTE_DIR must be an absolute path with at least two names, for example /srv/www/d2rloader.net-download. Only letters, digits, . _ - are allowed.")
	url = values["PUBLIC_URL"]
	if not re.fullmatch(r"(https://|http://127\.0\.0\.1:)[A-Za-z0-9._:/-]+/", url):
		raise PublishError("PUBLIC_URL must start with https:// and end with /, for example https://d2rloader.net/download/.")
	return {"target": values["SSH_TARGET"], "remote_dir": directory, "public_url": url}


def where(settings, target):
	"""Returns (folder on the server, public address) of the live folder or the test folder."""
	if target == "test":
		return settings["remote_dir"] + "/" + TEST_FOLDER, settings["public_url"] + TEST_FOLDER + "/"
	return settings["remote_dir"], settings["public_url"]


# ---- SSH ----

def command_for(variable, default):
	"""The program that talks to the server. A test can replace it with a JSON list in an environment variable."""
	given = os.environ.get(variable)
	return json.loads(given) if given else [default]


def ssh_options():
	return ["-o", "ConnectTimeout=20", "-o", "ServerAliveInterval=15"]


def run_on_server(settings, command):
	done = subprocess.run([*command_for("D2RL_SSH_COMMAND", "ssh"), *ssh_options(), settings["target"], command])
	return done.returncode == 0


def upload(settings, remote_dir, local_dir, names, create_folder):
	"""Uploads the files in `names` (in this order) from local_dir to remote_dir, and moves them into place on the server.

	Each file goes first into a temporary folder in remote_dir, because Nginx serves every file in remote_dir."""
	for name in names:
		if not SAFE_NAME.fullmatch(name):
			raise PublishError(f"The file name '{name}' has characters that are not allowed.")
	incoming = f".incoming-{secrets.token_hex(4)}"

	if create_folder:
		prepare = f"mkdir -p '{remote_dir}' && chmod 755 '{remote_dir}'"
	else:
		prepare = f"test -d '{remote_dir}' && test -w '{remote_dir}'"
	print("Checking the folder on the server ...")
	if not run_on_server(settings, f"{prepare} && mkdir '{remote_dir}/{incoming}'"):
		raise PublishError(f"Cannot use {remote_dir} on the server, or the SSH login failed.\n"
			f"Try this first: ssh {settings['target']}\nThen check SSH_TARGET and REMOTE_DIR in publish.env.")
	try:
		print("Uploading ...")
		copy = subprocess.run([*command_for("D2RL_SCP_COMMAND", "scp"), *ssh_options(), *names, f"{settings['target']}:{remote_dir}/{incoming}/"], cwd=local_dir)
		if copy.returncode != 0:
			raise PublishError("The upload failed. Nothing was changed in the public folder.")
		quoted = " ".join(f"'{incoming}/{name}'" for name in names)
		moves = " && ".join(f"mv -f '{incoming}/{name}' '{name}'" for name in names)
		print("Moving the files into place ...")
		if not run_on_server(settings, f"cd '{remote_dir}' && chmod 644 {quoted} && {moves} && rmdir '{incoming}'"):
			raise PublishError("The files were uploaded, but moving them into place failed. Some files may be replaced already. "
				"Run the upload again.")
	except BaseException:
		run_on_server(settings, f"rm -rf '{remote_dir}/{incoming}'")
		raise


# ---- Checks of the public files ----

def check_download(url, size, sha256):
	"""Downloads `url` and compares its size and SHA-256. Returns None if it is right, or the reason."""
	request = urllib.request.Request(url, headers={"Accept-Encoding": "identity", "Cache-Control": "no-cache", "User-Agent": "D2RLoader-publish"})
	digest, total = hashlib.sha256(), 0
	try:
		with urllib.request.urlopen(request, timeout=60) as response:
			for chunk in iter(lambda: response.read(1 << 20), b""):
				digest.update(chunk)
				total += len(chunk)
	except urllib.error.HTTPError as error:
		hint = " (the file may not be readable by Nginx: files need mode 644, folders 755)" if error.code == 403 else ""
		return f"HTTP {error.code}{hint}"
	except (urllib.error.URLError, OSError) as error:
		return f"cannot download: {error}"
	if total != size:
		return f"size {total}, expected {size}"
	if digest.hexdigest() != sha256:
		return "SHA-256 does not match"
	return None


def check_public_files(base_url, files):
	"""`files` is a list of (name, path of the local file). Returns True if every public file equals the local file."""
	print("Checking the public files ...")
	ok = True
	for name, path in files:
		data_hash = hashlib.sha256(path.read_bytes()).hexdigest()
		problem = check_download(base_url + name, path.stat().st_size, data_hash)
		print(("  OK     " if problem is None else "  FAILED ") + base_url + name + ("" if problem is None else "  " + problem))
		ok &= problem is None
	return ok


# ---- Questions ----

def ask(question):
	try:
		return input(question).strip()
	except EOFError:
		return ""


def choose_target():
	print("Where do you want to publish?")
	print("  1  The test folder. Players do not see it. Use it first.")
	print("  2  The live site. Players get this release.")
	answer = ask("Type 1 or 2: ")
	if answer not in ("1", "2"):
		raise PublishError("No place was chosen. Nothing was uploaded.")
	return "test" if answer == "1" else "live"


def confirm(assume_yes):
	if not assume_yes and ask("Type yes to upload: ").lower() != "yes":
		raise PublishError("Not confirmed. Nothing was uploaded.")


# ---- The commands ----

def publish_release(zip_path, settings, target, allow_preview, assume_yes):
	tool = load_tool("make-manifest.py", "make_manifest")
	remote_dir, public_url = where(settings, target)
	with tempfile.TemporaryDirectory(prefix="d2rl-publish-") as work:
		site = Path(work) / "site"
		try:
			manifest = tool.make(zip_path, site, None, public_url)
		except tool.ReleaseError as error:
			raise PublishError(str(error))
		version = manifest["version"]
		if target == "live" and "preview" in version.lower() and not allow_preview:
			raise PublishError(f"{version} is a preview version. Players must not get it. Publish it to the test folder, or add --allow-preview.")

		names = [item["url"].rsplit("/", 1)[-1] for item in manifest["files"]]
		if target == "live":
			shutil.copyfile(zip_path, site / zip_path.name)
			names.insert(0, zip_path.name)
		names.append("manifest.json")

		print(f"\nPublish D2RLoader {version} to the {'TEST folder' if target == 'test' else 'LIVE site'}")
		print(f"  Server:  {settings['target']}  {remote_dir}")
		print(f"  Address: {public_url}")
		for name in names:
			print(f"  {(site / name).stat().st_size:>12,}  {name}")
		print("  manifest.json is uploaded last.")
		if target == "live":
			print(f"  In D2RLoader.net run `pnpm release:update {zip_path}` first. It writes the version and hash for the page.")
		print()
		confirm(assume_yes)

		upload(settings, remote_dir, site, names, create_folder=target == "test")
		if not check_public_files(public_url, [(name, site / name) for name in names]):
			raise PublishError("Some public files are wrong. Read the lines above. Do not deploy the page yet.")
	print("\nDone. The files are on the server and match.")
	if target == "live":
		print("Next: in D2RLoader.net run `pnpm download:verify`, then commit and deploy the page.")
	else:
		print(f"Next: build a test installer with build-installer.cmd {public_url}manifest.json, and try it. Delete the files in the test folder afterwards.")


def publish_installer(settings, installer, assume_yes):
	if not installer.is_file():
		raise PublishError(f"{installer} was not found. Build it first with build-installer.cmd.")
	build = load_tool("build.py", "build")
	status, signer = build.signature_of(installer)
	print("\nPublish the installer to the LIVE site")
	print(f"  Server:    {settings['target']}  {settings['remote_dir']}")
	print(f"  Address:   {settings['public_url']}{installer.name}")
	print(f"  File:      {installer.stat().st_size:,} bytes")
	print(f"  SHA-256:   {hashlib.sha256(installer.read_bytes()).hexdigest()}")
	print(f"  Signature: {status}" + (f", signer {signer}" if signer else ""))
	if not signer:
		print("  WARNING: this installer is NOT signed.")
	print("  In D2RLoader.net run `pnpm installer:update` with this same file first. It writes the size and hash for the page.\n")
	confirm(assume_yes)

	upload(settings, settings["remote_dir"], installer.parent, [installer.name], create_folder=False)
	if not check_public_files(settings["public_url"], [(installer.name, installer)]):
		raise PublishError("The public file is wrong. Read the line above.")
	print("\nDone. Next: in D2RLoader.net run `pnpm download:verify`, then commit and deploy the page.")


def main():
	parser = argparse.ArgumentParser(description="Uploads a release or the installer to the website over SSH.")
	commands = parser.add_subparsers(dest="command", required=True)
	release = commands.add_parser("release", help="upload a release (the ZIP, the four files, and the manifest)")
	release.add_argument("zip", type=Path, help="the release zip (D2RLoader-<version>.zip)")
	release.add_argument("--target", choices=["test", "live"], help="where to publish (default: ask)")
	release.add_argument("--allow-preview", action="store_true", help="allow a preview version on the live site")
	installer = commands.add_parser("installer", help="upload out/D2RLoader-Installer.exe to the live folder")
	for command in (release, installer):
		command.add_argument("--yes", action="store_true", help="do not ask for confirmation (for tests)")
	args = parser.parse_args()

	try:
		settings = read_settings(ENV_FILE)
		if args.command == "installer":
			publish_installer(settings, INSTALLER, args.yes)
		else:
			publish_release(args.zip, settings, args.target or choose_target(), args.allow_preview, args.yes)
	except PublishError as error:
		print("\nERROR: " + str(error), file=sys.stderr)
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
