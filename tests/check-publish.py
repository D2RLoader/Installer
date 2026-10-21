"""Tests for tools/publish.py. The "server" is a folder on this PC, and tests/fake_ssh.py stands in for ssh and scp.

A small web server hands out that folder, so the check of the public files is real. Nothing leaves this PC.

Run: python -I tests/check-publish.py
"""

import contextlib
import hashlib
import http.server
import importlib.util
import io
import json
import os
import shlex
import shutil
import sys
import tempfile
import threading
import zipfile
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("publish", ROOT / "tools" / "publish.py")
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)

FAKE = ROOT / "tests" / "fake_ssh.py"
SERVER_DIR = "srv/www/d2rloader.net-download"
DIRS = ["mods/", "d2rloader/", "d2rloader/config/", "d2rloader/data/", "d2rloader/plugins/", "d2rloader/logs/", "d2rloader/crashes/"]
FILES = {"D2RLoader.exe": b"MZ-exe" * 100, "D2RCore.dll": b"dll" * 500, "d2rloader.mpq": bytes(range(256)) * 20,
	"d2rloader/config/d2rloader.toml": b"# config\n"}
FOUR = ["D2RLoader.exe", "D2RCore.dll", "d2rloader.mpq", "d2rloader.toml"]

failures = []


def check(ok, text):
	print(("PASS " if ok else "FAIL ") + text)
	if not ok:
		failures.append(text)


def make_zip(folder, version, entries=None):
	path = folder / f"D2RLoader-{version}.zip"
	with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
		for directory in DIRS:
			archive.writestr(directory, b"")
		for name, data in (FILES if entries is None else entries).items():
			archive.writestr(name, data)
	return path


class Quiet(http.server.SimpleHTTPRequestHandler):
	def log_message(self, *args):
		pass


def listing(folder):
	return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


def log_lines(root):
	log = root / "log.txt"
	return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def attempt(function, *args):
	"""Runs a publish function. Returns (None, output) if it works, or (error text, output) if it raises PublishError."""
	shown = io.StringIO()
	try:
		with contextlib.redirect_stdout(shown):
			function(*args)
	except publish.PublishError as error:
		return str(error), shown.getvalue()
	return None, shown.getvalue()


def main():
	work = Path(tempfile.mkdtemp(prefix="d2rl-publish-test-"))
	server = None
	try:
		root = work / "server"
		live = root / SERVER_DIR
		live.mkdir(parents=True)
		handler = partial(Quiet, directory=str(live))
		server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
		threading.Thread(target=server.serve_forever, daemon=True).start()
		url = f"http://127.0.0.1:{server.server_address[1]}/"

		os.environ["D2RL_SSH_COMMAND"] = json.dumps([sys.executable, "-I", str(FAKE), "ssh"])
		os.environ["D2RL_SCP_COMMAND"] = json.dumps([sys.executable, "-I", str(FAKE), "scp"])
		os.environ["D2RL_FAKE_ROOT"] = str(root)
		for name in ("D2RL_FAKE_FAIL", "D2RL_FAKE_CORRUPT"):
			os.environ.pop(name, None)

		def env_file(**changes):
			values = {"SSH_TARGET": "d2rloader-web", "REMOTE_DIR": "/" + SERVER_DIR, "PUBLIC_URL": url}
			values.update(changes)
			path = work / "publish.env"
			path.write_text("# test\n" + "".join(f"{key}={value}\n" for key, value in values.items() if value is not None), encoding="utf-8")
			return path

		# ---- The settings file ----
		missing = attempt(publish.read_settings, work / "nothing.env")[0]
		check(missing is not None and "publish.env.example" in missing, "no settings file: the message says to copy publish.env.example")
		for what, changes, part in [
			("an unknown key", {"COLOR": "red"}, "COLOR"),
			("a missing key", {"REMOTE_DIR": None}, "REMOTE_DIR"),
			("a target that starts with a dash", {"SSH_TARGET": "-oProxyCommand=x"}, "SSH_TARGET"),
			("a target with a space", {"SSH_TARGET": "a b"}, "SSH_TARGET"),
			("a relative folder", {"REMOTE_DIR": "srv/www/x"}, "REMOTE_DIR"),
			("a folder with ..", {"REMOTE_DIR": "/srv/../etc/x"}, "REMOTE_DIR"),
			("a folder with a quote", {"REMOTE_DIR": "/srv/www/it's"}, "REMOTE_DIR"),
			("a folder that is too shallow", {"REMOTE_DIR": "/srv"}, "REMOTE_DIR"),
			("an address that is not https", {"PUBLIC_URL": "http://example.org/download/"}, "PUBLIC_URL"),
			("an address without / at the end", {"PUBLIC_URL": "https://d2rloader.net/download"}, "PUBLIC_URL"),
		]:
			error = attempt(publish.read_settings, env_file(**changes))[0]
			check(error is not None and part in error, f"settings: rejects {what}")
		settings = publish.read_settings(env_file(REMOTE_DIR="/" + SERVER_DIR + "/"))
		check(settings["remote_dir"] == "/" + SERVER_DIR and settings["public_url"] == url, "settings: a good file is read, and a / at the end of the folder is removed")

		# ---- A release to the test folder ----
		releases = work / "releases"
		releases.mkdir()
		zip1 = make_zip(releases, "1.2.3")
		error, shown = attempt(publish.publish_release, zip1, settings, "test", False, True)
		test_dir = live / "test"
		check(error is None, "test target: the release is published" + (f" ({error})" if error else ""))
		check(sorted(p.name for p in test_dir.iterdir()) == sorted(FOUR + ["manifest.json"]), "test target: the test folder has the four files and the manifest, and no ZIP, and no temporary folder")
		manifest = json.loads((test_dir / "manifest.json").read_text(encoding="utf-8")) if (test_dir / "manifest.json").exists() else {}
		check(all(item["url"].startswith(url + "test/") for item in manifest.get("files", [])) and manifest.get("files"), "test target: the manifest points to the test folder")
		check(sorted(p.name for p in live.iterdir()) == ["test"], "test target: nothing was put in the live folder")
		log = log_lines(root)
		check(any(line.startswith("ssh chmod 755 ") for line in log), "test target: the test folder gets mode 755")
		check(any(line.startswith("ssh chmod 644 ") for line in log), "test target: the files get mode 644")
		check(sum(1 for line in log if line.startswith("ssh mv -f ")) == 5, "test target: five files are moved into place")

		# ---- A release to the live folder ----
		(root / "log.txt").unlink()
		error, shown = attempt(publish.publish_release, zip1, settings, "live", False, True)
		check(error is None, "live target: the release is published" + (f" ({error})" if error else ""))
		check(sorted(p.name for p in live.iterdir() if p.name != "test") == sorted(FOUR + ["manifest.json", zip1.name]), "live target: the folder has the ZIP, the four files, and the manifest")
		expected = {Path(name).name: data for name, data in FILES.items()}
		check(all((live / name).read_bytes() == expected[name] for name in FOUR), "live target: the files have the right content")
		check((live / zip1.name).read_bytes() == zip1.read_bytes(), "live target: the ZIP is the same file")
		check(not any(p.name.startswith(".incoming") for p in live.rglob("*")), "live target: no temporary folder is left")
		order = [shlex.split(line)[-1] for line in log_lines(root) if line.startswith("ssh mv -f ")]
		check(len(order) == 6 and order[0] == zip1.name and order[-1] == "manifest.json", "live target: the ZIP is moved first and manifest.json last")
		check("OK" in shown and "FAILED" not in shown, "live target: the public files were checked")

		# ---- A second release: files are replaced, older ZIPs stay ----
		zip2 = make_zip(releases, "1.2.4", {**FILES, "D2RLoader.exe": b"MZ-new" * 300})
		error, _ = attempt(publish.publish_release, zip2, settings, "live", False, True)
		check(error is None and (live / "D2RLoader.exe").read_bytes() == b"MZ-new" * 300, "second release: the changed file is replaced")
		check((live / zip1.name).exists() and (live / zip2.name).exists(), "second release: the old ZIP stays, and the new ZIP is added")
		check(json.loads((live / "manifest.json").read_text(encoding="utf-8"))["version"] == "1.2.4", "second release: the manifest has the new version")

		# ---- Preview versions ----
		before = listing(live)
		zip_preview = make_zip(releases, "1.3.0-beta-preview.1")
		error, _ = attempt(publish.publish_release, zip_preview, settings, "live", False, True)
		check(error is not None and "preview" in error and listing(live) == before, "preview: the live site refuses it, and nothing is uploaded")
		error, _ = attempt(publish.publish_release, zip_preview, settings, "test", False, True)
		check(error is None, "preview: the test folder accepts it")
		error, _ = attempt(publish.publish_release, zip_preview, settings, "live", True, True)
		check(error is None and (live / zip_preview.name).exists(), "preview: --allow-preview lets it go live")

		# ---- Confirmation ----
		before = listing(live)
		zip3 = make_zip(releases, "1.2.5")
		real_ask = publish.ask
		publish.ask = lambda question: "no"
		error, _ = attempt(publish.publish_release, zip3, settings, "live", False, False)
		check(error is not None and "Not confirmed" in error and listing(live) == before, "confirmation: any answer except yes uploads nothing")
		publish.ask = lambda question: "YES"
		error, _ = attempt(publish.publish_release, zip3, settings, "live", False, False)
		check(error is None and (live / zip3.name).exists(), "confirmation: yes (any letter case) uploads")
		publish.ask = lambda question: ""
		check(attempt(publish.choose_target)[0] is not None, "menu: no answer chooses nothing")
		with contextlib.redirect_stdout(io.StringIO()):
			publish.ask = lambda question: "1"
			chose_test = publish.choose_target()
			publish.ask = lambda question: "2"
			chose_live = publish.choose_target()
		check(chose_test == "test", "menu: 1 is the test folder")
		check(chose_live == "live", "menu: 2 is the live site")
		publish.ask = real_ask

		# ---- Failures on the way ----
		zip4 = make_zip(releases, "1.2.6", {**FILES, "D2RCore.dll": b"new-dll" * 100})
		for fail, text in (("login", "ssh"), ("scp", "upload failed"), ("move", "moving them into place")):
			before = {name: (live / name).read_bytes() for name in FOUR + ["manifest.json"]}
			listing_before = listing(live)
			os.environ["D2RL_FAKE_FAIL"] = fail
			error, _ = attempt(publish.publish_release, zip4, settings, "live", False, True)
			os.environ.pop("D2RL_FAKE_FAIL")
			check(error is not None and text in error, f"failure '{fail}': the error says what went wrong")
			check(not any(p.name.startswith(".incoming") for p in live.rglob("*")), f"failure '{fail}': the temporary folder is removed")
			if fail != "move":
				check(listing(live) == listing_before and all((live / name).read_bytes() == data for name, data in before.items()),
					f"failure '{fail}': the live folder is not changed")
		os.environ["D2RL_FAKE_CORRUPT"] = "D2RCore.dll"
		error, shown = attempt(publish.publish_release, zip4, settings, "live", False, True)
		os.environ.pop("D2RL_FAKE_CORRUPT")
		check(error is not None and "wrong" in error and "FAILED" in shown and "D2RCore.dll" in shown, "a file that is wrong on the server is found by the check of the public files")

		# ---- The installer ----
		exe = work / "D2RLoader-Installer.exe"
		exe.write_bytes(os.urandom(5000))
		before = listing(live)
		error, shown = attempt(publish.publish_installer, settings, exe, True)
		check(error is None and (live / exe.name).read_bytes() == exe.read_bytes(), "installer: the exe is uploaded to the live folder" + (f" ({error})" if error else ""))
		check(sorted(set(listing(live)) - set(before)) == [exe.name], "installer: only the exe is added")
		check("NOT signed" in shown and "pnpm installer:update" in shown, "installer: an unsigned exe gets a warning, and the page step is named")
		error, _ = attempt(publish.publish_installer, settings, work / "missing.exe", True)
		check(error is not None and "build-installer.cmd" in error, "installer: a missing exe says how to build it")
		publish.ask = lambda question: "no"
		error, _ = attempt(publish.publish_installer, settings, exe, False)
		publish.ask = real_ask
		check(error is not None and "Not confirmed" in error, "installer: needs a yes")

		# ---- The command line ----
		old_env_file = publish.ENV_FILE
		publish.ENV_FILE = work / "no-such.env"
		sys.argv = ["publish.py", "release", str(zip1), "--target", "test", "--yes"]
		errors = io.StringIO()
		with contextlib.redirect_stderr(errors):
			code = publish.main()
		check(code == 1 and errors.getvalue().startswith("\nERROR: "), "command line: exits with 1 and prints ERROR: when the settings are missing")
		publish.ENV_FILE = env_file()
		with contextlib.redirect_stdout(io.StringIO()):
			code = publish.main()
		check(code == 0, "command line: exits with 0 after a good upload to the test folder")
		publish.ENV_FILE = old_env_file
	finally:
		if server:
			server.shutdown()
		shutil.rmtree(work, ignore_errors=True)

	print(f"\n{len(failures)} failed" if failures else "\nALL PUBLISH CHECKS PASSED")
	return 1 if failures else 0


if __name__ == "__main__":
	sys.exit(main())
