"""Try the installer wizard by hand, with a fake website and two fake game folders.

Nothing real is touched. The test installer never reads the real registry. It gets the two game folders
(a "Battle.net" copy and a "Steam" copy) from this script, and the folders are made in a temporary folder.
The script starts a slow local web server, so the progress bar stays visible, and opens the installer window.
You click through the pages. A menu lets you open the installer again, publish a new release,
or start a fake D2RLoader.exe to see the "game is running" message.

Build the test installer first (python -I tests/run-all.py does it). Run:
	python -I tests/try-wizard.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e  # The web server and the helpers are shared with the automatic tests.

EXE = b"fake D2RLoader.exe " + os.urandom(6_000_000)
DLL = b"fake D2RCore.dll " + os.urandom(4_000_000)
TOML = b"# default config\nvalue = 1\n"
FOLDERS = ["mods", "d2rloader/plugins", "d2rloader/data", "d2rloader/logs"]
LANGUAGE = sys.argv[1] if len(sys.argv) > 1 else "english"  # python -I tests/try-wizard.py german


def publish_release(version, mpq_size):
	"""Puts a release on the fake website. A new mpq makes the installer download that file again."""
	e2e.reset_site()
	files = [
		e2e.entry("D2RLoader.exe", EXE),
		e2e.entry("D2RCore.dll", DLL),
		e2e.entry("d2rloader.mpq", os.urandom(mpq_size)),
		e2e.entry("d2rloader/config/d2rloader.toml", TOML, onlyIfMissing=True),
	]
	return e2e.publish(files, FOLDERS, version=version)


def show_folders(battle, steam, custom):
	for label, folder in (("Battle.net copy", battle), ("Steam copy", steam), ("Other folder copy", custom)):
		print(f"\n{label}: {folder}")
		files = sorted(p for p in folder.rglob("*") if p.is_file())
		if not files:
			print("  (no files)")
		for path in files:
			print(f"  {path.relative_to(folder).as_posix():45} {path.stat().st_size:>12,} bytes")
	shortcuts = sorted((battle.parent / "shortcuts").rglob("*.lnk"))
	print("\nShortcuts (in a test folder, not on your desktop):")
	for path in shortcuts or [None]:
		print("  " + (path.relative_to(battle.parent / "shortcuts").as_posix() if path else "(none)"))


def open_installer(url, battle, steam, custom, log, uninstall_base):
	print("\nThe installer window opens now. Click through it, then come back here.")
	if log.exists():
		log.unlink()
	subprocess.run([
		str(e2e.INSTALLER), "/CURRENTUSER", f"/Manifest={url}", f"/LANG={LANGUAGE}",
		f"/FakeBattleNet={battle}", f"/FakeSteam={steam}", f"/LOG={log}", f"/UninstBase={uninstall_base}",
		f"/IconDir={uninstall_base.parent / 'shortcuts'}",  # The shortcuts go here, not to your real desktop.
	])
	print(f"The installer closed.")
	if log.exists():
		lines = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines() if "D2RL:" in line]
		if lines:
			print("What Setup logged:")
			for line in lines:
				print("  " + line.split("D2RL:", 1)[1].strip())
	show_folders(battle, steam, custom)


def main():
	if not e2e.INSTALLER.exists():
		print(f"Missing {e2e.INSTALLER}. Run: python -I tests/run-all.py")
		return 2

	server = e2e.start_server()
	e2e.SITE.chunk_delay = 0.02
	work = Path(tempfile.mkdtemp(prefix="d2rl-wizard-"))
	battle = e2e.new_game(work, "Battle.net copy")
	steam = e2e.new_game(work, "Steam copy")
	custom = e2e.new_game(work, "Other folder copy")  # Setup does not know this one. Use the "Other folder" tile and paste its path.
	log = work / "setup.log"
	uninstall_base = work / "uninstall"
	url = publish_release("demo-1.0", 14_000_000)
	fake_game = None

	print("Fake game folders:")
	print(f"  Battle.net tile: {battle}")
	print(f"  Steam tile:      {steam}")
	print(f"  Other folder:    {custom}")
	print("    (Setup does not know the third folder. Click the 'Other folder' tile, then paste this path in the folder box.)")
	print("The fake website is at " + e2e.SITE.url(""))
	try:
		while True:
			print("\n[Enter] open the installer      n  publish a new release, then open the installer")
			print("u  open the uninstaller of a game folder")
			print("g  start a fake D2RLoader.exe in the Battle.net copy (the installer and uninstaller should refuse)")
			print("k  stop the fake D2RLoader.exe   s  show the two folders   q  quit and clean up")
			choice = input("> ").strip().lower()
			if choice == "":
				open_installer(url, battle, steam, custom, log, uninstall_base)
			elif choice == "n":
				url = publish_release(f"demo-{int(time.time()) % 100000}", 9_000_000)
				print("A new release is published: only d2rloader.mpq changed.")
				open_installer(url, battle, steam, custom, log, uninstall_base)
			elif choice == "u":
				found = sorted(uninstall_base.glob("*/unins000.exe"))
				if not found:
					print("There is no uninstaller yet. Install first.")
					continue
				for number, path in enumerate(found, 1):
					print(f"  {number}. {path}")
				pick = input("Which one? (number) > ").strip()
				if pick.isdigit() and 1 <= int(pick) <= len(found):
					print("The uninstaller opens now. It starts a copy of itself, so this script goes on at once. Use [s] to look at the folders.")
					subprocess.Popen([str(found[int(pick) - 1])])
			elif choice == "g":
				if fake_game is None or fake_game.poll() is not None:
					loader = battle / "D2RLoader.exe"
					if not loader.exists() or loader.stat().st_size < 1_000_000:
						shutil.copyfile(e2e.PING, loader)
					fake_game = subprocess.Popen([str(loader), "-n", "600", "127.0.0.1"], stdout=subprocess.DEVNULL)
					print("A fake D2RLoader.exe runs in the Battle.net copy. Now open the installer and click the Battle.net tile.")
			elif choice == "k":
				if fake_game is not None and fake_game.poll() is None:
					fake_game.kill()
					fake_game.wait()
					print("The fake D2RLoader.exe is stopped.")
			elif choice == "s":
				show_folders(battle, steam, custom)
			elif choice == "q":
				break
	finally:
		if fake_game is not None and fake_game.poll() is None:
			fake_game.kill()
			fake_game.wait()
		server.shutdown()
		time.sleep(0.5)
		shutil.rmtree(work, ignore_errors=True)
		print("Cleaned up.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
