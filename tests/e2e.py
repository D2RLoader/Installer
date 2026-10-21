"""End-to-end tests for the installer.

The script starts a small web server on 127.0.0.1, builds a fake game folder, and runs the installer
test build in silent mode. Then it checks the files on disk and the requests that the server saw.

Build the test installer first (it allows http on 127.0.0.1 and reads /Manifest=<url>):
	ISCC /DTEST_LOOPBACK /DOutputName=installer-test src/installer.iss
Run:
	python -I tests/e2e.py
"""

import ctypes
import hashlib
import contextlib
import http.server
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "out" / "installer-test.exe"
PING = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "ping.exe"
PLACEHOLDER_DIR = r"C:\d2rl-test-build-needs-a-DIR-option"  # Must match src/installer.iss.

results = []


def check(condition, name):
	results.append((bool(condition), name))
	print(("PASS " if condition else "FAIL ") + name, flush=True)


# ---- A small web server ----

class Site:
	"""The files the server hands out, and a record of what was asked for."""

	def __init__(self):
		self.served = {}
		self.requests = []
		self.port = 0
		self.chunk_delay = 0.0  # Seconds to wait after each 64 KB. The demo uses it to show the progress bar.

	def url(self, name):
		return f"http://127.0.0.1:{self.port}/{name}"


SITE = Site()


class Handler(http.server.BaseHTTPRequestHandler):
	def do_GET(self):
		name = self.path.lstrip("/")
		SITE.requests.append(name)
		data = SITE.served.get(name)
		if data is None:
			self.send_response(404)
			self.end_headers()
			return
		self.send_response(200)
		self.send_header("Content-Type", "application/octet-stream")
		self.send_header("Content-Length", str(len(data)))
		self.end_headers()
		if not SITE.chunk_delay:
			self.wfile.write(data)
			return
		for start in range(0, len(data), 65536):
			self.wfile.write(data[start:start + 65536])
			time.sleep(SITE.chunk_delay)

	def log_message(self, *args):
		pass


def start_server():
	server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
	SITE.port = server.server_address[1]
	threading.Thread(target=server.serve_forever, daemon=True).start()
	return server


# ---- Helpers ----

def sha(data):
	return hashlib.sha256(data).hexdigest()


def entry(path, data, serve_as=None, **changes):
	"""One manifest entry. The server hands out `serve_as` (default: data) at a new address."""
	name = f"f{len(SITE.served)}"
	SITE.served[name] = data if serve_as is None else serve_as
	item = {"path": path, "url": SITE.url(name), "size": len(data), "sha256": sha(data)}
	item.update(changes)
	return item


def publish(files, folders=None, version="1.0.0-test", **top):
	"""Puts a manifest on the server and returns its address."""
	manifest = {"schema": 1, "version": version, "files": files}
	if folders is not None:
		manifest["folders"] = folders
	manifest.update(top)
	SITE.served["manifest.json"] = json.dumps(manifest).encode("utf-8")
	return SITE.url("manifest.json")


def reset_site():
	SITE.served.clear()
	SITE.requests.clear()


def new_game(work, name="game", with_exe=True):
	game = work / name
	game.mkdir(parents=True, exist_ok=True)
	if with_exe:
		(game / "D2R.exe").write_bytes(b"")
	return game


def uninstall_dir(game):
	"""Where the test installer keeps the uninstaller of this game folder. It is next to the game folder."""
	return game.parent / ("uninst-" + game.name)


def icon_dir(game):
	"""Where the test installer puts shortcuts for this game folder. It never uses the real desktop."""
	return game.parent / ("icons-" + game.name)


def run_installer(game, manifest_url, log_name="setup.log", extra=(), give_dir=True, timeout=300, uninst_base=None):
	"""Runs the test installer in silent mode. Returns (exit code, setup log text).

	`game` is the folder that the installer must use. With give_dir=False the installer has to find it itself
	(through /FakeBattleNet= and /FakeSteam= in `extra`)."""
	log = game.parent / log_name
	if log.exists():
		log.unlink()
	# The uninstaller goes to its own folder. With uninst_base, many installs share one base folder, as a real PC does.
	where = f"/UninstBase={uninst_base}" if uninst_base else f"/UninstDir={uninstall_dir(game)}"
	command = [
		str(INSTALLER), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/CURRENTUSER", "/NORESTART", "/LANG=english",  # The tests read English log lines.
		f"/Manifest={manifest_url}", f"/LOG={log}", where, f"/IconDir={icon_dir(game)}", *extra,
	]
	if give_dir:
		command.append(f"/DIR={game}")
	SITE.requests.clear()
	try:
		done = subprocess.run(command, timeout=timeout)
	except subprocess.TimeoutExpired:
		# Setup is stuck (for example, in a message box). Stop it, and tell the test.
		# Inno Setup runs the real Setup in a second process (name.tmp). Stop both.
		for name in (INSTALLER.name, INSTALLER.stem + ".tmp"):
			subprocess.run(["taskkill", "/F", "/T", "/IM", name], capture_output=True)
		return -999, log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
	text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""

	# Safety: the installer must work in the folder it was given. If not, stop the whole suite at once.
	# The placeholder is the folder that the test build uses when it finds nothing. It does not exist.
	folder = logged_game_folder(text)
	if folder is not None and folder != PLACEHOLDER_DIR:
		if os.path.normcase(os.path.normpath(folder)) != os.path.normcase(os.path.normpath(str(game))):
			abort_unsafe(f"the installer used {folder} but was given {game}")
	return done.returncode, text


def logged_game_folder(log_text):
	marker = "D2RL: game folder "
	for line in log_text.splitlines():
		if marker in line:
			return line.split(marker, 1)[1].strip()
	return None


def abort_unsafe(message):
	print("ABORT: " + message, flush=True)
	os._exit(3)


def snapshot(game):
	"""Every file under the game folder and its hash."""
	result = {}
	for path in sorted(game.rglob("*")):
		if path.is_file():
			result[path.relative_to(game).as_posix()] = sha(path.read_bytes())
	return result


def file_requests():
	return [r for r in SITE.requests if r != "manifest.json"]


def lock_file(path):
	"""Opens a file with no sharing, so no other program can replace it."""
	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.CreateFileW.restype = ctypes.c_void_p
	kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
									ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
	kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
	handle = kernel32.CreateFileW(str(path), 0xC0000000, 0, None, 3, 0x80, None)
	if handle in (None, ctypes.c_void_p(-1).value):
		raise OSError(f"Could not lock {path}")
	return lambda: kernel32.CloseHandle(handle)


EXE_DATA = b"MZ-fake-exe-" + bytes(range(256)) * 40
DLL_DATA = b"fake-dll-" + os.urandom(5000)
MPQ_DATA = os.urandom(300_000)
TOML_DATA = b"# default config\nvalue = 1\n"
FOLDERS = ["mods", "d2rloader/plugins", "d2rloader/data", "d2rloader/logs"]


def standard_files():
	return [
		entry("D2RLoader.exe", EXE_DATA),
		entry("D2RCore.dll", DLL_DATA),
		entry("d2rloader.mpq", MPQ_DATA),
		entry("d2rloader/config/d2rloader.toml", TOML_DATA, onlyIfMissing=True),
	]


# ---- Tests ----

def test_fresh_install_and_update(work):
	reset_site()
	game = new_game(work, "fresh")
	code, log = run_installer(game, publish(standard_files(), FOLDERS))
	check(code == 0, "fresh install: exit code 0")
	files = snapshot(game)
	check(files.get("D2RLoader.exe") == sha(EXE_DATA), "fresh install: D2RLoader.exe has the right content")
	check(files.get("D2RCore.dll") == sha(DLL_DATA), "fresh install: D2RCore.dll has the right content")
	check(files.get("d2rloader.mpq") == sha(MPQ_DATA), "fresh install: d2rloader.mpq has the right content")
	check(files.get("d2rloader/config/d2rloader.toml") == sha(TOML_DATA), "fresh install: the config file is created")
	check(all((game / f).is_dir() for f in FOLDERS), "fresh install: the folders are created")
	check(files.get("D2R.exe") == sha(b""), "fresh install: D2R.exe is not touched")
	check(len(file_requests()) == 4, "fresh install: 4 files were downloaded")

	# Run again with nothing new: only the manifest is fetched.
	before = snapshot(game)
	code, log = run_installer(game, publish(standard_files(), FOLDERS))
	check(code == 0, "second run: exit code 0")
	check(file_requests() == [], "second run: no file is downloaded again")
	check(snapshot(game) == before, "second run: nothing changes on disk")

	# A new release changes two files. The user edited the config file.
	(game / "d2rloader/config/d2rloader.toml").write_bytes(b"# my own settings\n")
	reset_site()
	new_exe = EXE_DATA + b"-v2"
	new_mpq = os.urandom(120_000)
	files = [entry("D2RLoader.exe", new_exe), entry("D2RCore.dll", DLL_DATA), entry("d2rloader.mpq", new_mpq),
			entry("d2rloader/config/d2rloader.toml", b"# new default\n", onlyIfMissing=True)]
	code, log = run_installer(game, publish(files, FOLDERS, version="1.0.1-test"))
	after = snapshot(game)
	check(code == 0, "update: exit code 0")
	check(after.get("D2RLoader.exe") == sha(new_exe), "update: the changed exe is replaced")
	check(after.get("d2rloader.mpq") == sha(new_mpq), "update: the changed mpq is replaced")
	check(after.get("D2RCore.dll") == sha(DLL_DATA), "update: the unchanged dll stays")
	check(len(file_requests()) == 2, "update: only the 2 changed files are downloaded")
	check((game / "d2rloader/config/d2rloader.toml").read_bytes() == b"# my own settings\n",
		"update: the file the user edited is kept (onlyIfMissing)")

	# The user deletes the config file. It comes back.
	(game / "d2rloader/config/d2rloader.toml").unlink()
	reset_site()
	files = [entry("D2RLoader.exe", new_exe), entry("D2RCore.dll", DLL_DATA), entry("d2rloader.mpq", new_mpq),
			entry("d2rloader/config/d2rloader.toml", b"# new default\n", onlyIfMissing=True)]
	code, log = run_installer(game, publish(files, FOLDERS, version="1.0.1-test"))
	check(code == 0 and (game / "d2rloader/config/d2rloader.toml").read_bytes() == b"# new default\n",
		"update: a deleted config file is created again")

	# A damaged file is repaired.
	(game / "D2RCore.dll").write_bytes(b"broken")
	reset_site()
	files = [entry("D2RLoader.exe", new_exe), entry("D2RCore.dll", DLL_DATA), entry("d2rloader.mpq", new_mpq),
			entry("d2rloader/config/d2rloader.toml", b"# new default\n", onlyIfMissing=True)]
	code, log = run_installer(game, publish(files, FOLDERS, version="1.0.1-test"))
	check(code == 0 and snapshot(game).get("D2RCore.dll") == sha(DLL_DATA), "repair: a damaged file is replaced")
	check(len(file_requests()) == 1, "repair: only the damaged file is downloaded")


def test_rejections(work):
	# Each case must stop before anything is written. The game folder keeps only D2R.exe.
	def case(name, make_files, expect_in_log, **publish_args):
		reset_site()
		game = new_game(work, name)
		code, log = run_installer(game, publish(make_files(), **publish_args))
		check(code != 0, f"{name}: Setup stops")
		check(snapshot(game) == {"D2R.exe": sha(b"")}, f"{name}: nothing is written to the game folder")
		check(expect_in_log in log, f"{name}: the log says why ({expect_in_log})")

	case("wrong-hash", lambda: [entry("D2RLoader.exe", EXE_DATA, serve_as=b"X" * len(EXE_DATA))], "D2RL:")
	case("wrong-size", lambda: [entry("D2RLoader.exe", EXE_DATA, size=len(EXE_DATA) + 1)], "wrong size")
	case("not-found", lambda: [entry("D2RLoader.exe", EXE_DATA), {**entry("D2RCore.dll", DLL_DATA), "url": SITE.url("missing")}], "D2RL:")
	case("path-dotdot", lambda: [entry("../evil.txt", b"evil")], "not a safe path")
	case("path-backslash", lambda: [entry("mods\\evil.txt", b"evil")], "not a safe path")
	case("path-drive", lambda: [entry("C:/evil.txt", b"evil")], "not a safe path")
	case("url-http", lambda: [entry("a.txt", b"a", url="http://example.com/a.txt")], "must start with https://")
	case("bad-sha", lambda: [entry("a.txt", b"a", sha256="ABC")], "sha256")
	case("no-files", lambda: [], "files")
	case("schema-two", lambda: [entry("a.txt", b"a")], "schema", schema=2)

	# A file after a failing file must not be copied, even if its own download passed.
	reset_site()
	game = new_game(work, "half")
	files = [entry("D2RLoader.exe", EXE_DATA), {**entry("D2RCore.dll", DLL_DATA), "url": SITE.url("missing")}]
	code, log = run_installer(game, publish(files))
	check(code != 0 and snapshot(game) == {"D2R.exe": sha(b"")}, "half: a failed download leaves the good file uncopied")
	check(not (work / "evil.txt").exists(), "no file was written outside the game folder")


def test_broken_manifest(work):
	for name, body in (("garbage", b"this is not json"), ("truncated", b'{"schema": 1, "files": ['),
					("empty", b""), ("deep", b'{"schema":1,"x":' + b"[" * 5000)):
		reset_site()
		game = new_game(work, "manifest-" + name)
		SITE.served["manifest.json"] = body
		code, log = run_installer(game, SITE.url("manifest.json"))
		check(code != 0 and snapshot(game) == {"D2R.exe": sha(b"")}, f"broken manifest ({name}): Setup stops, nothing written")

	reset_site()
	game = new_game(work, "manifest-404")
	code, log = run_installer(game, SITE.url("manifest.json"))
	check(code != 0 and snapshot(game) == {"D2R.exe": sha(b"")}, "manifest not found (404): Setup stops")

	game = new_game(work, "manifest-noserver")
	code, log = run_installer(game, "http://127.0.0.1:1/manifest.json")
	check(code != 0 and snapshot(game) == {"D2R.exe": sha(b"")}, "no server: Setup stops")

	game = new_game(work, "manifest-http")
	code, log = run_installer(game, "http://example.com/manifest.json")
	check(code != 0 and "https://" in log, "manifest over http (not this computer): rejected before any download")


def test_game_folder(work):
	reset_site()
	game = new_game(work, "no-exe", with_exe=False)
	code, log = run_installer(game, publish(standard_files(), FOLDERS))
	check(code != 0 and snapshot(game) == {}, "no D2R.exe: Setup stops, nothing written")
	check("did not find the game" in log, "no D2R.exe: the log says why")
	check(SITE.requests == [], "no D2R.exe: nothing is downloaded")


def test_folder_choice(work):
	not_touched = {"D2R.exe": sha(b"")}

	# A silent run without /DIR= uses the first folder that it finds: Battle.net before Steam.
	reset_site()
	battle = new_game(work, "choice-battlenet")
	steam = new_game(work, "choice-steam")
	manifest = publish(standard_files(), FOLDERS)
	both = (f"/FakeBattleNet={battle}", f"/FakeSteam={steam}")
	code, log = run_installer(battle, manifest, extra=both, give_dir=False)
	check(code == 0 and "D2RLoader.exe" in snapshot(battle), "folder choice: a silent run without /DIR= uses the Battle.net folder")
	check(snapshot(steam) == not_touched, "folder choice: the Steam folder is not touched")

	# /DIR= wins over every folder that the installer finds. This once wrote to a real game folder.
	reset_site()
	given = new_game(work, "choice-given")
	found = new_game(work, "choice-found")
	manifest = publish(standard_files(), FOLDERS)
	code, log = run_installer(given, manifest, extra=(f"/FakeBattleNet={found}", f"/FakeSteam={found}"))
	check(code == 0 and "D2RLoader.exe" in snapshot(given), "folder choice: /DIR= is used")
	check(snapshot(found) == not_touched, "folder choice: a found folder is not touched when /DIR= is given")

	# Only a Steam folder is found.
	reset_site()
	only_steam = new_game(work, "choice-only-steam")
	manifest = publish(standard_files(), FOLDERS)
	code, log = run_installer(only_steam, manifest, extra=(f"/FakeSteam={only_steam}",), give_dir=False)
	check(code == 0 and "D2RLoader.exe" in snapshot(only_steam), "folder choice: a silent run uses the Steam folder if it is the only one")

	# A found folder without D2R.exe is ignored. The next one is used.
	reset_site()
	empty = new_game(work, "choice-empty", with_exe=False)
	good = new_game(work, "choice-good")
	manifest = publish(standard_files(), FOLDERS)
	code, log = run_installer(good, manifest, extra=(f"/FakeBattleNet={empty}", f"/FakeSteam={good}"), give_dir=False)
	check(code == 0 and "D2RLoader.exe" in snapshot(good), "folder choice: a folder without D2R.exe is ignored")
	check(snapshot(empty) == {}, "folder choice: the folder without D2R.exe is not touched")

	# Nothing is found and no /DIR=: Setup stops and writes nothing.
	reset_site()
	nowhere = new_game(work, "choice-nowhere")
	manifest = publish(standard_files(), FOLDERS)
	code, log = run_installer(nowhere, manifest, give_dir=False)
	check(code != 0 and "did not find the game" in log, "folder choice: no folder found and no /DIR= stops Setup")


def test_game_running(work):
	reset_site()
	game = new_game(work, "running")
	loader = game / "D2RLoader.exe"
	shutil.copyfile(PING, loader)
	other = new_game(work, "running-other")
	process = subprocess.Popen([str(loader), "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL)
	try:
		import time
		time.sleep(1)
		manifest = publish(standard_files()[1:], FOLDERS)
		code, log = run_installer(game, manifest)
		check(code != 0 and "D2RLoader.exe is running" in log, "game running: Setup stops")
		check("D2RCore.dll" not in snapshot(game), "game running: nothing is written")
		check(SITE.requests == [], "game running: nothing is downloaded")

		# A copy of the loader in another folder does not block this folder.
		code, log = run_installer(other, manifest)
		check(code == 0, "game running in another folder: Setup goes on")
	finally:
		process.kill()
		process.wait()

	import time
	time.sleep(1)
	code, log = run_installer(game, manifest)
	check(code == 0 and "D2RCore.dll" in snapshot(game), "game closed: Setup goes on")


def test_locked_file(work):
	reset_site()
	game = new_game(work, "locked")
	manifest = publish(standard_files(), FOLDERS)
	code, log = run_installer(game, manifest)
	check(code == 0, "locked: first install works")

	# A new release, but a program holds D2RCore.dll open without sharing.
	new_dll = DLL_DATA + b"-v2"
	reset_site()
	files = [entry("D2RLoader.exe", EXE_DATA), entry("D2RCore.dll", new_dll), entry("d2rloader.mpq", MPQ_DATA),
			entry("d2rloader/config/d2rloader.toml", TOML_DATA, onlyIfMissing=True)]
	manifest = publish(files, FOLDERS, version="1.0.1-test")
	before = snapshot(game)
	unlock = lock_file(game / "D2RCore.dll")
	try:
		code, log = run_installer(game, manifest, timeout=90)
	finally:
		unlock()
	(ROOT / "out" / "locked.log").write_text(log, encoding="utf-8")
	check(code not in (0, -999), f"locked: Setup stops when a file cannot be replaced (exit code {code})")
	check(snapshot(game).get("D2RCore.dll") == sha(DLL_DATA), "locked: the locked file is unchanged")
	check(snapshot(game) == before, "locked: no other file was changed (Setup rolled back)")

	# Running Setup again finishes the job.
	code, log = run_installer(game, manifest)
	check(code == 0 and snapshot(game).get("D2RCore.dll") == sha(new_dll), "locked: a second run repairs it")


def wait_until(condition, seconds):
	deadline = time.time() + seconds
	while time.time() < deadline:
		if condition():
			return True
		time.sleep(0.25)
	return condition()


def run_uninstaller(game, log_name="uninstall.log", wait=True, extra=(), exe=None):
	"""Runs the uninstaller of this game folder in silent mode. Returns the path of its log.

	The uninstaller starts a copy of itself and quits. With wait=True this function waits until the uninstaller
	has removed itself, which is the last thing it does. Use wait=False when the uninstaller must refuse
	or hand over to another uninstaller. `exe` is another uninstaller, for example when many installs share a base folder."""
	exe = exe or (uninstall_dir(game) / "unins000.exe")
	log = game.parent / log_name
	if log.exists():
		log.unlink()
	subprocess.run([str(exe), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/LOG={log}", *extra], timeout=120)
	if wait:
		wait_until(lambda: not exe.exists(), 60)
		time.sleep(0.5)
	return log


def read_log(log):
	return log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""


def test_uninstall(work):
	not_touched = {"D2R.exe": sha(b"")}

	# A normal uninstall: the installed files go. The settings file, the user's own files, and D2R.exe stay.
	reset_site()
	game = new_game(work, "un-basic")
	code, log = run_installer(game, publish(standard_files(), FOLDERS))
	check(code == 0 and (uninstall_dir(game) / "unins000.exe").exists(), "uninstall: Setup keeps an uninstaller outside the game folder")
	check(not any(p.name.startswith("unins") for p in game.iterdir()), "uninstall: the game folder gets no uninstaller files")
	(game / "mods" / "MyMod").mkdir(parents=True)
	(game / "mods" / "MyMod" / "readme.txt").write_bytes(b"my mod")
	(game / "d2rloader" / "data" / "state.json").write_bytes(b"{}")
	(game / "D2RLoader.exe").write_bytes(b"changed by the user")  # An installed file that changed is still removed.
	(game / "d2rloader/config/d2rloader.toml").write_bytes(b"# my settings\n")
	run_uninstaller(game)
	check(wait_until(lambda: not (game / "D2RLoader.exe").exists(), 60), "uninstall: D2RLoader.exe is removed")
	files = snapshot(game)
	check("D2RCore.dll" not in files and "d2rloader.mpq" not in files, "uninstall: the other installed files are removed")
	check(files.get("D2R.exe") == sha(b""), "uninstall: D2R.exe is not touched")
	check(files.get("d2rloader/config/d2rloader.toml") == sha(b"# my settings\n"), "uninstall: the settings file stays")
	check(files.get("mods/MyMod/readme.txt") == sha(b"my mod") and files.get("d2rloader/data/state.json") == sha(b"{}"),
		"uninstall: the user's own files stay")
	check(set(files) == {"D2R.exe", "d2rloader/config/d2rloader.toml", "mods/MyMod/readme.txt", "d2rloader/data/state.json"},
		"uninstall: nothing else is left")
	check(not (game / "d2rloader" / "plugins").exists(), "uninstall: an empty folder that Setup made is removed")
	check((game / "mods").is_dir() and (game / "d2rloader" / "data").is_dir(), "uninstall: a folder with the user's files stays")
	check(wait_until(lambda: not (uninstall_dir(game) / "unins000.exe").exists(), 30), "uninstall: the uninstaller removes itself")

	# Install, update, then uninstall. The files of the first install and of the update are all removed.
	reset_site()
	game = new_game(work, "un-update")
	run_installer(game, publish(standard_files(), FOLDERS))
	reset_site()
	files = [entry("D2RLoader.exe", EXE_DATA + b"-v2"), entry("D2RCore.dll", DLL_DATA), entry("d2rloader.mpq", os.urandom(50_000)),
			entry("d2rloader/config/d2rloader.toml", TOML_DATA, onlyIfMissing=True)]
	run_installer(game, publish(files, FOLDERS, version="1.0.1-test"))
	run_uninstaller(game)
	check(wait_until(lambda: not (game / "D2RLoader.exe").exists(), 60), "uninstall after an update: D2RLoader.exe is removed")
	left = set(snapshot(game))
	check(left == {"D2R.exe", "d2rloader/config/d2rloader.toml"}, f"uninstall after an update: only D2R.exe and the settings file are left {sorted(left)}")

	# The user unpacked the release by hand first. Setup then adds nothing to download, but it records the files.
	reset_site()
	game = new_game(work, "un-by-hand")
	for name, data in (("D2RLoader.exe", EXE_DATA), ("D2RCore.dll", DLL_DATA), ("d2rloader.mpq", MPQ_DATA)):
		(game / name).write_bytes(data)
	(game / "d2rloader" / "config").mkdir(parents=True)
	(game / "d2rloader/config/d2rloader.toml").write_bytes(TOML_DATA)
	code, log = run_installer(game, publish(standard_files(), FOLDERS))
	check(code == 0 and file_requests() == [], "unpacked by hand: Setup downloads nothing")
	run_uninstaller(game)
	check(wait_until(lambda: not (game / "D2RLoader.exe").exists(), 60), "unpacked by hand: the uninstaller still removes the files")
	check(set(snapshot(game)) == {"D2R.exe", "d2rloader/config/d2rloader.toml"}, "unpacked by hand: only D2R.exe and the settings file are left")

	# The uninstaller refuses while D2RLoader.exe runs from the game folder.
	reset_site()
	game = new_game(work, "un-running")
	run_installer(game, publish(standard_files(), FOLDERS))
	shutil.copyfile(PING, game / "D2RLoader.exe")  # A program that really runs, in the place of the fake exe.
	process = subprocess.Popen([str(game / "D2RLoader.exe"), "-n", "120", "127.0.0.1"], stdout=subprocess.DEVNULL)
	try:
		time.sleep(1)
		log = run_uninstaller(game, wait=False)
		time.sleep(6)
		check((game / "D2RCore.dll").exists() and (game / "d2rloader.mpq").exists(), "uninstall while the game runs: nothing is removed")
		check("D2RLoader.exe is running" in read_log(log), "uninstall while the game runs: the log says why")
	finally:
		process.kill()
		process.wait()
	time.sleep(1)
	run_uninstaller(game)
	check(wait_until(lambda: not (game / "D2RCore.dll").exists(), 60), "uninstall after the game closed: the files are removed")

	# Two game folders (for example Battle.net and Steam). Each one has its own uninstaller.
	reset_site()
	first = new_game(work, "un-two-a")
	second = new_game(work, "un-two-b")
	manifest = publish(standard_files(), FOLDERS)
	run_installer(first, manifest)
	run_installer(second, manifest)
	check((uninstall_dir(first) / "unins000.exe").exists() and (uninstall_dir(second) / "unins000.exe").exists(),
		"two game folders: each one has its own uninstaller")
	run_uninstaller(first)
	check(wait_until(lambda: not (first / "D2RLoader.exe").exists(), 60), "two game folders: the first uninstall removes its files")
	check((second / "D2RLoader.exe").exists() and (second / "D2RCore.dll").exists(), "two game folders: the second install is not touched")
	run_uninstaller(second)
	check(wait_until(lambda: not (second / "D2RLoader.exe").exists(), 60), "two game folders: the second uninstall works")
	check(snapshot(first).keys() == snapshot(second).keys(), "two game folders: both end the same")


def read_install_info(folder):
	"""The two lines of install.txt: the kind and the game folder. None if the file is missing."""
	path = folder / "install.txt"
	if not path.exists():
		return None
	return path.read_text(encoding="utf-8").replace("\r", "").split("\n")[:2]


def find_uninstall_folder(base, game):
	"""The folder under `base` that belongs to this game folder (many installs share one base folder)."""
	for folder in base.iterdir():
		info = read_install_info(folder) if folder.is_dir() else None
		if info and os.path.normcase(info[1]) == os.path.normcase(str(game).replace("/", "\\")):
			return folder
	return None


def real_program_files():
	"""Like standard_files(), but D2RLoader.exe is a real Windows program. Setup makes a .pif (DOS) shortcut for a fake one."""
	return [entry("D2RLoader.exe", PING.read_bytes())] + standard_files()[1:]


def test_shortcuts(work):
	start_name = "Test D2RLoader ({}).lnk"

	# By default (a silent run with no /TASKS) there is a Start menu shortcut and no desktop shortcut.
	reset_site()
	game = new_game(work, "icons-default")
	code, log = run_installer(game, publish(real_program_files(), FOLDERS))
	icons = icon_dir(game)
	check(code == 0 and (icons / "Start" / start_name.format("Other folder")).exists(), "shortcuts: the Start menu shortcut is made by default")
	check(not (icons / "Desktop" / start_name.format("Other folder")).exists(), "shortcuts: the desktop shortcut is not made by default")
	run_uninstaller(game)
	check(not (icons / "Start" / start_name.format("Other folder")).exists(), "shortcuts: the uninstaller removes the Start menu shortcut")

	# Both shortcuts, named after the kind of the game folder.
	for kind, option in (("Battle.net", "/FakeBattleNet={}"), ("Steam", "/FakeSteam={}")):
		reset_site()
		game = new_game(work, "icons-" + kind.lower().replace(".", ""))
		code, log = run_installer(game, publish(real_program_files(), FOLDERS), extra=(option.format(game), "/TASKS=startmenuicon,desktopicon"))
		icons = icon_dir(game)
		check(code == 0 and (icons / "Start" / start_name.format(kind)).exists() and (icons / "Desktop" / start_name.format(kind)).exists(),
			f"shortcuts: both shortcuts are made, and the name has {kind}")
		check(read_install_info(find_uninstall_folder(work, game)) == [kind, str(game).replace("/", "\\")], f"install info: the kind {kind} is recorded")
		run_uninstaller(game)
		check(not any(icons.rglob("*.lnk")), f"shortcuts: the uninstaller removes both shortcuts ({kind})")

	# No shortcut at all.
	reset_site()
	game = new_game(work, "icons-none")
	code, log = run_installer(game, publish(real_program_files(), FOLDERS), extra=("/TASKS=",))
	check(code == 0 and not any(icon_dir(game).rglob("*.lnk")), "shortcuts: /TASKS= makes no shortcut")

	# A shortcut starts D2RLoader.exe in the game folder. Read the shortcut with Windows itself.
	reset_site()
	game = new_game(work, "icons-target")
	run_installer(game, publish(real_program_files(), FOLDERS), extra=("/TASKS=startmenuicon",))
	link = icon_dir(game) / "Start" / start_name.format("Other folder")
	link_text = str(link).replace("/", "\\").replace("'", "''")
	script = f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link_text}'); Write-Output $s.TargetPath; Write-Output $s.WorkingDirectory"
	done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=60)
	lines = [line.strip() for line in done.stdout.splitlines() if line.strip()]
	want = [str(game).replace("/", "\\") + "\\D2RLoader.exe", str(game).replace("/", "\\")]
	check(lines[:2] == want, f"shortcuts: the shortcut starts D2RLoader.exe in the game folder (got {lines} {done.stderr.strip()[:200]})")


def test_settings_and_installs(work):
	# The settings question. The answer is Keep unless /RemoveSettings=1 is given.
	for remove in (False, True):
		reset_site()
		game = new_game(work, "settings-" + ("remove" if remove else "keep"))
		run_installer(game, publish(standard_files(), FOLDERS))
		(game / "d2rloader/config/charm-inv.toml").write_bytes(b"# a plugin setting\n")
		(game / "d2rloader/config/d2rloader.toml").write_bytes(b"# my settings\n")
		(game / "d2rloader/data/state.json").write_bytes(b"{}")
		(game / "mods" / "MyMod").mkdir(parents=True)
		(game / "mods/MyMod/readme.txt").write_bytes(b"my mod")
		run_uninstaller(game, extra=("/RemoveSettings=1",) if remove else ())
		files = set(snapshot(game))
		if remove:
			check(not (game / "d2rloader" / "config").exists(), "settings: /RemoveSettings=1 deletes the folder d2rloader\\config")
			check("d2rloader/data/state.json" in files and "mods/MyMod/readme.txt" in files, "settings: saved data and mods stay when the settings are deleted")
		else:
			check({"d2rloader/config/d2rloader.toml", "d2rloader/config/charm-inv.toml"} <= files, "settings: the settings stay by default")

	# With no settings folder at all, /RemoveSettings=1 does nothing bad.
	reset_site()
	game = new_game(work, "settings-none")
	run_installer(game, publish(standard_files()[:3], FOLDERS))
	run_uninstaller(game, extra=("/RemoveSettings=1",))
	check(set(snapshot(game)) == {"D2R.exe"}, "settings: no settings folder, nothing else happens")

	# Three installs share one base folder, as on a real computer. One uninstaller can remove another install.
	reset_site()
	base = work / "shared-base"
	base.mkdir()
	manifest = publish(standard_files(), FOLDERS)
	battle = new_game(work, "multi-battlenet")
	steam = new_game(work, "multi-steam")
	custom = new_game(work, "multi-custom")
	run_installer(battle, manifest, extra=(f"/FakeBattleNet={battle}",), uninst_base=base)
	run_installer(steam, manifest, extra=(f"/FakeSteam={steam}",), uninst_base=base)
	run_installer(custom, manifest, uninst_base=base)
	kinds = sorted(read_install_info(folder)[0] for folder in base.iterdir() if folder.is_dir())
	check(kinds == ["Battle.net", "Custom", "Steam"], f"installs: three installs share one base folder {kinds}")
	exe = {name: find_uninstall_folder(base, game) / "unins000.exe" for name, game in (("battle", battle), ("steam", steam), ("custom", custom))}

	# A pick that matches no install is the same as Cancel.
	run_uninstaller(custom, wait=False, exe=exe["custom"], extra=(f"/Pick={work / 'nowhere'}",))
	time.sleep(4)
	check((battle / "D2RLoader.exe").exists() and (steam / "D2RLoader.exe").exists() and (custom / "D2RLoader.exe").exists(),
		"installs: choosing no install removes nothing")

	# The uninstaller of the custom install is asked to remove the Steam install.
	run_uninstaller(custom, wait=False, exe=exe["custom"], extra=(f"/Pick={steam}",))
	check(wait_until(lambda: not (steam / "D2RLoader.exe").exists(), 60), "installs: one uninstaller removes another install")
	check(wait_until(lambda: not exe["steam"].exists(), 30), "installs: the other uninstaller removes itself")
	check((battle / "D2RLoader.exe").exists() and (custom / "D2RLoader.exe").exists(), "installs: the other installs stay")
	check(exe["custom"].exists() and exe["battle"].exists(), "installs: their uninstallers stay")
	check(not (find_uninstall_folder(base, steam) is not None), "installs: the removed install is gone from the list")

	# The settings choice is passed on to the other uninstaller.
	(custom / "d2rloader/config/charm-inv.toml").write_bytes(b"# setting\n")
	(battle / "d2rloader/config/charm-inv.toml").write_bytes(b"# setting\n")
	run_uninstaller(battle, wait=False, exe=exe["battle"], extra=(f"/Pick={custom}", "/RemoveSettings=1"))
	check(wait_until(lambda: not (custom / "D2RLoader.exe").exists(), 60), "installs: the install that was picked is removed")
	check(wait_until(lambda: not (custom / "d2rloader" / "config").exists(), 30), "installs: the settings of the picked install are removed")
	check((battle / "D2RLoader.exe").exists() and (battle / "d2rloader/config/charm-inv.toml").exists(), "installs: the install that asked is not touched, and neither are its settings")

	# The last one removes itself.
	run_uninstaller(battle, exe=exe["battle"], extra=(f"/Pick={battle}",))
	check(not (battle / "D2RLoader.exe").exists(), "installs: an uninstaller can remove its own install when it is the one picked")
	check(not any(folder.is_dir() and read_install_info(folder) for folder in base.iterdir()), "installs: no install is left in the base folder")


def test_large_and_unicode(work):
	reset_site()
	game = new_game(work, "Diablo \u042e\u0416 \u00e9")
	big = os.urandom(40 * 1024 * 1024)
	name = "mods/\u00dcn\u00ef/\u0411.txt"
	files = [entry("big.bin", big), entry(name, b"unicode path")]
	code, log = run_installer(game, publish(files, ["mods/\u00dcn\u00ef"]))
	check(code == 0, "large file and unicode names: exit code 0")
	check((game / "big.bin").exists() and sha((game / "big.bin").read_bytes()) == sha(big), "large file: 40 MB arrives intact")
	check((game / "mods" / "\u00dcn\u00ef" / "\u0411.txt").read_bytes() == b"unicode path", "unicode: a path with non-ASCII letters is installed")


def test_make_manifest(work):
	"""The installer installs from the files that tools/make-manifest.py writes for a release zip."""
	spec = importlib.util.spec_from_file_location("make_manifest", ROOT / "tools" / "make-manifest.py")
	tool = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(tool)

	reset_site()
	release = work / "release"
	release.mkdir()
	wanted = {"D2RLoader.exe": EXE_DATA, "D2RCore.dll": DLL_DATA, "d2rloader.mpq": MPQ_DATA, "d2rloader/config/d2rloader.toml": TOML_DATA}
	folders = ["mods", "d2rloader", "d2rloader/config", "d2rloader/data", "d2rloader/plugins", "d2rloader/logs", "d2rloader/crashes"]
	zip_path = release / "D2RLoader-2.0.0-test.zip"
	with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
		for folder in folders:
			archive.writestr(folder + "/", b"")
		for path, data in wanted.items():
			archive.writestr(path, data)
	site = release / "site"
	with contextlib.redirect_stdout(io.StringIO()):
		tool.make(zip_path, site, None, SITE.url("download"))
	for item in site.iterdir():
		SITE.served["manifest.json" if item.name == "manifest.json" else "download/" + item.name] = item.read_bytes()

	game = new_game(work, "from-tool")
	code, log = run_installer(game, SITE.url("manifest.json"))
	check(code == 0, "make-manifest: the installer accepts the manifest and installs (exit code 0)")
	files = snapshot(game)
	check(all(files.get(path) == sha(data) for path, data in wanted.items()), "make-manifest: every file of the release is installed with the right content")
	check(all((game / folder).is_dir() for folder in ("mods", "d2rloader/data", "d2rloader/plugins", "d2rloader/logs", "d2rloader/crashes")),
		"make-manifest: the empty folders are created")

	# The config file is 'only if missing'.
	(game / "d2rloader/config/d2rloader.toml").write_bytes(b"# my own settings\n")
	code, log = run_installer(game, SITE.url("manifest.json"))
	check(code == 0 and (game / "d2rloader/config/d2rloader.toml").read_bytes() == b"# my own settings\n",
		"make-manifest: an update keeps the config file that the user edited")


def test_same_file_names(work):
	"""Files in different folders can have the same name. Setup keeps their temporary files apart."""
	reset_site()
	game = new_game(work, "same-names")
	wanted = {"a/data.txt": b"first", "b/data.txt": b"second", "c/DATA.txt": b"third", "d/_data.txt": b"fourth", "data.txt": b"fifth"}
	code, log = run_installer(game, publish([entry(path, data) for path, data in wanted.items()], ["a", "b", "c", "d"]))
	check(code == 0, "same file names: exit code 0")
	files = snapshot(game)
	check(all(files.get(path) == sha(data) for path, data in wanted.items()), "same file names: every file has its own content")


def main():
	if not INSTALLER.exists():
		print(f"Missing {INSTALLER}. Build it first (see the top of this file).")
		return 2

	server = start_server()
	work = Path(tempfile.mkdtemp(prefix="d2rl-e2e-"))
	try:
		# Canary: a run with no server cannot write anything. It proves that /DIR= is honored.
		canary_game = new_game(work, "canary")
		code, log = run_installer(canary_game, "http://127.0.0.1:1/manifest.json")
		if logged_game_folder(log) is None:
			abort_unsafe("the canary run did not log its game folder")
		check(code != 0 and snapshot(canary_game) == {"D2R.exe": sha(b"")}, "canary: /DIR= is honored and nothing is written")

		for test in (test_fresh_install_and_update, test_rejections, test_broken_manifest, test_game_folder,
					test_folder_choice, test_game_running, test_locked_file, test_uninstall, test_shortcuts,
					test_settings_and_installs, test_large_and_unicode, test_same_file_names, test_make_manifest):
			print(f"-- {test.__name__}", flush=True)
			try:
				test(work)
			except Exception as error:
				check(False, f"{test.__name__} raised {error!r}")
	finally:
		server.shutdown()
		if os.environ.get("D2RL_KEEP"):
			print(f"Kept the work folder: {work}")
		else:
			shutil.rmtree(work, ignore_errors=True)

	failed = [name for ok, name in results if not ok]
	print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
	for name in failed:
		print("  FAILED: " + name)
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
