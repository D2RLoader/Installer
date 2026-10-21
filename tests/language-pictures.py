"""Takes pictures of the main pages of Setup and of the uninstaller window in each language.

The point is to find text that does not fit: German and Russian words are long, and Chinese and Japanese need a font.
It opens windows for about a minute for each language. They go to monitor 2 (set D2RL_MONITOR=3 for another monitor, or
D2RL_MONITOR=main to keep them on the main monitor). Do not use the mouse or the keyboard while it runs.
It needs ffmpeg. Build the test installer first (python -I tests/run-all.py does it). Run:

	python -I tests/language-pictures.py                 all languages
	python -I tests/language-pictures.py german russian  only these

The pictures are in out/lang/<language>/, and out/lang/<language>.png is one sheet with all of them.
Buttons are found by their place and class, not by their text, so this works in every language.
"""

import ctypes
import ctypes.wintypes as wt
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e
import screenshots as s

user32 = s.user32
LANGUAGES = ["english", "german", "spanish", "french", "italian", "japanese", "korean", "polish", "brazilianportuguese",
	"russian", "chinesesimplified", "chinesetraditional"]
OUT = Path(__file__).resolve().parent.parent / "out" / "lang"


def class_of(hwnd):
	name = ctypes.create_unicode_buffer(256)
	user32.GetClassNameW(hwnd, name, 256)
	return name.value


def rect_of(hwnd):
	rect = wt.RECT()
	user32.GetWindowRect(hwnd, ctypes.byref(rect))
	return rect


def visible_windows(class_name):
	found = []

	@s.WNDENUMPROC
	def collect(hwnd, _):
		if user32.IsWindowVisible(hwnd) and class_of(hwnd) == class_name:
			found.append(hwnd)
		return True

	user32.EnumWindows(collect, 0)
	return found


def wait_for_window(class_name, timeout=25, ignore=()):
	deadline = time.time() + timeout
	while time.time() < deadline:
		for hwnd in visible_windows(class_name):
			if hwnd not in ignore and any(class_of(c) == "TNewButton" for c in s.children(hwnd)):
				s.move_to_monitor(hwnd)
				return hwnd
		time.sleep(0.25)
	return None


def buttons_of(hwnd, class_name="TNewButton"):
	return [c for c in s.children(hwnd) if class_of(c) == class_name and user32.IsWindowVisible(c) and user32.IsWindowEnabled(c)]


def bottom_buttons(hwnd):
	"""The buttons in the bottom bar (Back, Next, Cancel), from left to right."""
	bottom = rect_of(hwnd).bottom
	found = [c for c in buttons_of(hwnd) if bottom - rect_of(c).bottom < 80]
	return sorted(found, key=lambda c: rect_of(c).left)


def tiles_of(hwnd):
	"""The big buttons (the tiles), from left to right. A grey tile (not clickable) counts too."""
	found = [c for c in s.children(hwnd) if class_of(c) == "TNewButton" and user32.IsWindowVisible(c) and rect_of(c).bottom - rect_of(c).top > 60]
	return sorted(found, key=lambda c: rect_of(c).left)


def press(button):
	user32.PostMessageW(button, s.BM_CLICK, 0, 0)


def wait_for_buttons(hwnd, count, timeout=60):
	"""Waits until the bottom bar has this many buttons. Returns the buttons."""
	deadline = time.time() + timeout
	while time.time() < deadline:
		found = bottom_buttons(hwnd)
		if len(found) == count:
			return found
		time.sleep(0.25)
	return bottom_buttons(hwnd)


def one_language(language, url, work, out_dir):
	"""Returns the names of the pictures."""
	battle = e2e.new_game(work, r"Games\Diablo II Resurrected")
	steam = e2e.new_game(work, r"Steam\steamapps\common\Diablo II Resurrected")
	base = work / "un"
	taken = []

	def pic(name):
		taken.append(name)
		return out_dir / f"{len(taken):02d}-{name}.png"

	def start(*extra, steam_found=True):
		command = [str(e2e.INSTALLER), "/CURRENTUSER", f"/LANG={language}", f"/Manifest={url}", f"/FakeBattleNet={battle}",
			f"/UninstBase={base}", f"/IconDir={work / 'icons'}", *extra]
		if steam_found:
			command.append(f"/FakeSteam={steam}")
		process = subprocess.Popen(command)
		s.STARTED.append(process)
		return process, wait_for_window("TWizardForm")

	# A first install: Welcome, tiles, shortcuts, Ready to Install, download, finished.
	process, window = start()
	if not window:
		print(f"  {language}: the window did not open")
		return taken
	s.shoot(window, pic("welcome"), wait=2.5)
	press(bottom_buttons(window)[0])  # Next (Welcome has Next and Cancel)
	time.sleep(1.5)
	s.shoot(window, pic("tiles"))
	press(tiles_of(window)[0])  # The first tile: Battle.net
	time.sleep(1.0)
	s.shoot(window, pic("shortcuts"))
	buttons = wait_for_buttons(window, 3, 10)
	press(buttons[1])  # Next
	time.sleep(1.0)
	s.shoot(window, pic("ready"))
	buttons = wait_for_buttons(window, 3, 10)
	press(buttons[1])  # Install
	s.shoot(window, pic("downloading"), wait=1.5)
	deadline = time.time() + 90
	while time.time() < deadline and len(bottom_buttons(window)) != 1:  # The Finish button is the only one on the last page
		time.sleep(0.5)
	s.shoot(window, pic("finished"))
	if bottom_buttons(window):
		press(bottom_buttons(window)[0])
	process.wait(timeout=30)

	# A second run: the page "Update or Uninstall", then the folder page of "Other folder".
	process, window = start(steam_found=False)
	press(bottom_buttons(window)[0])  # Next on the Welcome page
	time.sleep(1.5)
	s.shoot(window, pic("update-or-uninstall"))
	press(wait_for_buttons(window, 3, 10)[1])  # Next ("Update" is marked)
	time.sleep(1.5)
	tiles = tiles_of(window)
	if len(tiles) == 3:
		press(tiles[2])  # Other folder
		time.sleep(1.5)
		s.shoot(window, pic("folder-page"))
	s.kill_setup()
	time.sleep(1.0)

	# A third run: "Uninstall" opens the uninstaller window.
	process, window = start(steam_found=False)
	press(bottom_buttons(window)[0])
	time.sleep(1.5)
	radios = sorted(buttons_of(window, "TNewRadioButton"), key=lambda c: rect_of(c).top)
	if len(radios) == 2:
		press(radios[1])  # Uninstall
		time.sleep(0.5)
		press(wait_for_buttons(window, 3, 10)[1])
		form = wait_for_window("TSetupForm", 20)
		if form:
			time.sleep(1.0)
			s.shoot(form, pic("uninstall-window"))
			cancel = bottom_buttons(form)
			if cancel:
				press(cancel[-1])
	s.kill_setup()
	time.sleep(2.0)
	return taken


def make_sheet(out_dir, sheet):
	"""One picture with all pictures of a language, 3 in a row."""
	files = sorted(out_dir.glob("[0-9][0-9]-*.png"))
	if not files:
		return
	inputs, filters = [], []
	for index, path in enumerate(files):
		inputs += ["-i", str(path)]
		filters.append(f"[{index}:v]scale=640:480:force_original_aspect_ratio=decrease,pad=640:480:(ow-iw)/2:(oh-ih)/2:color=0x303030[v{index}]")
	chain = ";".join(filters) + ";" + "".join(f"[v{i}]" for i in range(len(files))) + f"xstack=inputs={len(files)}:layout=" + \
		"|".join(f"{(i % 3) * 640}_{(i // 3) * 480}" for i in range(len(files))) + ":fill=0x303030"
	done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", chain, "-frames:v", "1", str(sheet)],
		capture_output=True, text=True)
	if done.returncode != 0:
		print("  sheet failed:", done.stderr.strip()[:300])


def main():
	wanted = sys.argv[1:] or LANGUAGES
	unknown = [name for name in wanted if name not in LANGUAGES]
	if unknown:
		print("Unknown language:", unknown, "\nKnown:", LANGUAGES)
		return 2
	if not e2e.INSTALLER.exists():
		print(f"Missing {e2e.INSTALLER}. Run: python -I tests/run-all.py")
		return 2
	if s.other_setups_running():
		print("Another installer-test window is open (for example from try-wizard.py). Close it and run this again.")
		return 2

	print("The windows go to:", "monitor 2, the area " + str(s.target_monitor()) if s.target_monitor() else "the monitor that Windows picks")
	OUT.mkdir(parents=True, exist_ok=True)
	server = e2e.start_server()
	e2e.SITE.chunk_delay = 0.05
	try:
		for language in wanted:
			print(f"-- {language}", flush=True)
			out_dir = OUT / language
			if out_dir.exists():
				shutil.rmtree(out_dir)
			out_dir.mkdir(parents=True)
			e2e.reset_site()
			files = [e2e.entry("D2RLoader.exe", e2e.PING.read_bytes()), e2e.entry("D2RCore.dll", b"d" * 3_000_000),
				e2e.entry("d2rloader.mpq", bytes(6_000_000)), e2e.entry("d2rloader/config/d2rloader.toml", b"# default\n", onlyIfMissing=True)]
			url = e2e.publish(files, e2e.FOLDERS, version="1.3.2-beta")
			work = Path(tempfile.mkdtemp(prefix="d2rl-lang-"))
			try:
				names = one_language(language, url, work, out_dir)
				print(f"   pictures: {len(names)}", flush=True)
			finally:
				s.kill_setup()
				time.sleep(0.5)
				shutil.rmtree(work, ignore_errors=True)
			make_sheet(out_dir, OUT / f"{language}.png")
	finally:
		server.shutdown()
		s.kill_setup()
	print("Pictures are in", OUT)
	return 0


if __name__ == "__main__":
	sys.exit(main())
