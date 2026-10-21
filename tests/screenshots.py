"""Takes a picture of each page of the installer wizard and of the uninstaller window.

It starts the test installer with a fake website and fake game folders, clicks the real buttons, waits for each
page to be drawn, and saves a PNG of the window with ffmpeg (needs `ffmpeg` on PATH). The windows go to monitor 2
(set D2RL_MONITOR=3 for another monitor, or D2RL_MONITOR=main to keep them on the main monitor).
Do not use the mouse or the keyboard while it runs: the script moves the mouse over a button once.

Build the test installer first (python -I tests/run-all.py does it). Run:
	python -I tests/screenshots.py [output folder]       (default: out/screens)
"""

import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e

ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Real screen pixels, so the picture area matches the window.
user32 = ctypes.windll.user32
user32.FindWindowW.restype = wt.HWND
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowEnabled.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

class MONITORINFO(ctypes.Structure):
	_fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HANDLE, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)
user32.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.EnumDisplayMonitors.argtypes = [wt.HDC, ctypes.POINTER(wt.RECT), MONITORENUMPROC, wt.LPARAM]


def monitors():
	"""The monitors in the order of Windows: the main monitor first. Each is the work area (left, top, right, bottom)."""
	found = []

	@MONITORENUMPROC
	def collect(monitor, dc, rect, data):
		info = MONITORINFO()
		info.cbSize = ctypes.sizeof(info)
		user32.GetMonitorInfoW(monitor, ctypes.byref(info))
		area = info.rcWork
		entry = (area.left, area.top, area.right, area.bottom)
		if info.dwFlags & 1:  # The main monitor
			found.insert(0, entry)
		else:
			found.append(entry)
		return True

	user32.EnumDisplayMonitors(None, None, collect, 0)
	return found


def target_monitor():
	"""The work area where the test windows go: monitor 2 by default, so that they do not cover the work on the main monitor.

	Set the environment variable D2RL_MONITOR to another number (1 is the main monitor), or to "main" to keep the windows
	where Windows puts them. If the PC has one monitor, nothing moves."""
	choice = os.environ.get("D2RL_MONITOR", "2").strip().lower()
	if choice in ("main", "off", "1"):
		return None
	found = monitors()
	if not choice.isdigit() or not 2 <= int(choice) <= len(found):
		return None
	return found[int(choice) - 1]


def move_to_monitor(hwnd):
	"""Puts the window in the middle of the target monitor, if it is not there yet."""
	area = target_monitor()
	if area is None or not hwnd:
		return
	rect = wt.RECT()
	user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(rect))
	width, height = rect.right - rect.left, rect.bottom - rect.top
	if area[0] <= rect.left and rect.right <= area[2] and area[1] <= rect.top and rect.bottom <= area[3]:
		return
	x = area[0] + (area[2] - area[0] - width) // 2
	y = area[1] + (area[3] - area[1] - height) // 2
	SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0004, 0x0010
	user32.SetWindowPos(wt.HWND(hwnd), wt.HWND(0), x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
BM_CLICK = 0x00F5

SETUP_TITLE = "Setup - D2RLoader"


def window_text(hwnd):
	buffer = ctypes.create_unicode_buffer(512)
	user32.GetWindowTextW(hwnd, buffer, 512)
	return buffer.value


def children(hwnd):
	found = []

	@WNDENUMPROC
	def collect(child, _):
		found.append(child)
		return True

	user32.EnumChildWindows(hwnd, collect, 0)
	return found


def top_windows(title):
	"""All top-level windows with this title. Setup has two: a hidden one and the one with the buttons."""
	found = []

	@WNDENUMPROC
	def collect(hwnd, _):
		if window_text(hwnd) == title:
			found.append(hwnd)
		return True

	user32.EnumWindows(collect, 0)
	return found


def find_window(title, timeout=20):
	"""The window with this title that has a Cancel button (the real window, not the hidden one)."""
	deadline = time.time() + timeout
	while time.time() < deadline:
		for hwnd in top_windows(title):
			if user32.IsWindowVisible(hwnd) and any(window_text(c).replace("&", "") == "Cancel" for c in children(hwnd)):
				move_to_monitor(hwnd)
				return hwnd
		time.sleep(0.25)
	return None


def find_button(hwnd, text):
	"""The enabled, visible button with this label (without &, and without a trailing > or ...).

	The label must match exactly. A page description such as "... then click Next." is a text label, not a button,
	and a click on it does nothing."""
	for child in children(hwnd):
		label = window_text(child).replace("&", "").strip().rstrip(">.").strip()
		if label.lower() == text.lower() and user32.IsWindowVisible(child) and user32.IsWindowEnabled(child):
			return child
	return None


def click(hwnd, text, quiet=False):
	"""Clicks the button with this label. Returns False (and prints the short labels) if there is none."""
	button = find_button(hwnd, text)
	if button:
		# Post the click. SendMessage waits until Setup has handled it, and Setup downloads and installs inside
		# the click on the last page, so a picture taken after SendMessage would show the finished page.
		user32.PostMessageW(button, BM_CLICK, 0, 0)
		if not quiet:
			print(f"clicked {text!r}", flush=True)
		return True
	if not quiet:
		labels = [(window_text(c).replace("&", ""), bool(user32.IsWindowVisible(c)), bool(user32.IsWindowEnabled(c))) for c in children(hwnd)]
		print(f"no button {text!r}; short labels (text, visible, enabled):", [b for b in labels if b[0] and len(b[0]) < 20][:12], flush=True)
	return False


def hover(hwnd, text):
	"""Moves the mouse onto the button with this label, and moves it a little so that Windows shows the tip."""
	button = find_button(hwnd, text)
	if not button:
		print(f"no button {text!r} to hover")
		return
	user32.SetForegroundWindow(wt.HWND(hwnd))  # A tip shows only in the active window.
	time.sleep(0.5)
	rect = wt.RECT()
	user32.GetWindowRect(button, ctypes.byref(rect))
	x, y = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
	for step in (12, 8, 4, 0):
		user32.SetCursorPos(x - step, y - step // 2)
		time.sleep(0.15)


def move_mouse_to_title(hwnd):
	"""Puts the mouse on the title bar of the window, where a click does nothing."""
	rect = wt.RECT()
	user32.GetWindowRect(hwnd, ctypes.byref(rect))
	user32.SetCursorPos((rect.left + rect.right) // 2, rect.top + 12)


def find_message(timeout=10, titles=("Setup", "Exit Setup")):
	"""A message box of Setup ("Exit Setup" is the question after Cancel). The uninstaller uses other titles."""
	deadline = time.time() + timeout
	while time.time() < deadline:
		for title in titles:
			for hwnd in top_windows(title):
				if user32.IsWindowVisible(hwnd) and children(hwnd):
					move_to_monitor(hwnd)
					return hwnd
		time.sleep(0.25)
	return None


UNINSTALL_TITLES = ("Uninstall", "D2RLoader Uninstall")


def answer_uninstall_boxes(uninstaller, pic, timeout=40):
	"""Takes a picture of each message box of the uninstaller (the question and the result), and answers it."""
	deadline = time.time() + timeout
	last_seen = time.time()
	# The first uninstaller ends at once and starts a copy of itself, so do not wait for its process.
	# Stop when no box has shown for 10 seconds.
	while time.time() < deadline and time.time() - last_seen < 10:
		box = find_message(timeout=0.5, titles=UNINSTALL_TITLES)
		if not box:
			continue
		last_seen = time.time()
		shoot(box, pic("uninstall-box"), wait=0.5)
		for label in ("Yes", "OK"):
			if click(box, label, quiet=True):
				break
		time.sleep(1.0)


STARTED = []  # The Setup programs that this script started.
LANGUAGE = "english"  # The language of Setup. The buttons are found by their English names, so the walk needs English.


def kill_setup():
	"""Stops the Setup programs that this script started, with their child programs.

	Inno Setup runs the real Setup in a second program (name.tmp), which holds the window.
	The kill is by program number and not by name, so a Setup window that you opened yourself stays open."""
	for process in STARTED:
		subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
	STARTED.clear()


def other_setups_running():
	"""True if a program called installer-test is running, for example the window of try-wizard.py."""
	for name in (e2e.INSTALLER.name, e2e.INSTALLER.stem + ".tmp"):
		found = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"], capture_output=True, text=True).stdout
		if name.lower() in found.lower():
			return True
	return False


def close_setup(installer, timeout=25):
	"""Closes Setup the polite way, so that it removes its temporary folder: answer each message box, then click Cancel."""
	deadline = time.time() + timeout
	while installer.poll() is None and time.time() < deadline:
		box = find_message(timeout=0.3)
		window = find_window(SETUP_TITLE, timeout=0.3)
		if box:
			for label in ("OK", "Yes", "Cancel"):
				if click(box, label, quiet=True):
					break
		elif window:
			click(window, "Cancel", quiet=True)
		time.sleep(0.8)
	if installer.poll() is None:
		kill_setup()


def wait_for_button(hwnd, text, timeout=60):
	deadline = time.time() + timeout
	while time.time() < deadline:
		if find_button(hwnd, text):
			return True
		time.sleep(0.25)
	return False


def open_windows():
	"""The titles of all visible top-level windows. It helps to find a message box that blocks Setup."""
	titles = []

	@WNDENUMPROC
	def collect(hwnd, _):
		text = window_text(hwnd)
		if text and user32.IsWindowVisible(hwnd):
			titles.append(text)
		return True

	user32.EnumWindows(collect, 0)
	return titles


def window_rectangle(hwnd):
	"""The visible rectangle of a window in screen pixels, without the invisible border that Windows adds."""
	rect = wt.RECT()
	DWMWA_EXTENDED_FRAME_BOUNDS = 9
	if ctypes.windll.dwmapi.DwmGetWindowAttribute(wt.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)) != 0:
		user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(rect))
	return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def shoot(hwnd, path, wait=1.6, raise_window=True):
	"""Saves a picture of the window. The wait gives the window time to draw itself.

	The window is brought to the front and the screen area of the window is saved. This way the picture shows
	what the user sees, including the styled parts that a picture of the window handle would miss."""
	time.sleep(wait)
	if not hwnd:
		print("FAILED  " + path.name + " (no window)")
		return False
	move_to_monitor(hwnd)
	SW_SHOW, HWND_TOPMOST, HWND_NOTOPMOST, SWP_NOMOVE_NOSIZE = 5, -1, -2, 0x0003
	if raise_window:
		user32.ShowWindow(wt.HWND(hwnd), SW_SHOW)
		user32.SetWindowPos(wt.HWND(hwnd), wt.HWND(HWND_TOPMOST), 0, 0, 0, 0, SWP_NOMOVE_NOSIZE)
		user32.SetForegroundWindow(wt.HWND(hwnd))
		time.sleep(0.6)
	x, y, width, height = window_rectangle(hwnd)
	if width < 2 or height < 2:
		print("skipped " + path.name + " (the window has no size: it was closing)")
		return False
	width, height = width - width % 2, height - height % 2  # The video encoder needs even numbers.
	done = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "gdigrab", "-framerate", "1", "-draw_mouse", "0",
		"-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{width}x{height}", "-i", "desktop", "-frames:v", "1", str(path)],
		capture_output=True, text=True)
	user32.SetWindowPos(wt.HWND(hwnd), wt.HWND(HWND_NOTOPMOST), 0, 0, 0, 0, SWP_NOMOVE_NOSIZE)
	ok = done.returncode == 0 and path.exists()
	print(("saved   " if ok else "FAILED  ") + path.name + ("" if ok else " " + done.stderr.strip()[:200]), flush=True)
	return ok


def main():
	out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "out" / "screens"
	if out.exists():
		shutil.rmtree(out)
	out.mkdir(parents=True)
	counter = []

	def pic(name):
		"""The next picture file: 01-name.png, 02-name.png, and so on."""
		counter.append(name)
		return out / f"{len(counter):02d}-{name}.png"

	if not e2e.INSTALLER.exists():
		print(f"Missing {e2e.INSTALLER}. Run: python -I tests/run-all.py")
		return 2

	if other_setups_running():
		print("Another installer-test window is open (for example from try-wizard.py). Close it and run this again.")
		return 2
	print("The windows go to:", "monitor 2, the area " + str(target_monitor()) if target_monitor() else "the monitor that Windows picks")
	server = e2e.start_server()
	e2e.SITE.chunk_delay = 0.05
	work = Path(tempfile.mkdtemp(prefix="d2rl-screens-"))
	try:
		e2e.reset_site()
		battle = e2e.new_game(work, r"Games\Diablo II Resurrected")
		steam = e2e.new_game(work, r"Steam\steamapps\common\Diablo II Resurrected")
		files = [e2e.entry("D2RLoader.exe", e2e.PING.read_bytes()), e2e.entry("D2RCore.dll", b"d" * 3_000_000),
			e2e.entry("d2rloader.mpq", bytes(6_000_000)), e2e.entry("d2rloader/config/d2rloader.toml", b"# default\n", onlyIfMissing=True)]
		url = e2e.publish(files, e2e.FOLDERS, version="1.3.2-beta")
		base = work / "uninstall"

		runs = []

		def start_installer(*extra, steam_found=True):
			runs.append(work / f"setup-{len(runs) + 1}.log")  # One log for each run, so a slow exit cannot lock the next log.
			found = [f"/FakeSteam={steam}"] if steam_found else []
			process = subprocess.Popen([str(e2e.INSTALLER), "/CURRENTUSER", f"/LANG={LANGUAGE}", f"/Manifest={url}", f"/FakeBattleNet={battle}",
				*found, f"/UninstBase={base}", f"/IconDir={work / 'icons'}", f"/LOG={runs[-1]}", *extra])
			STARTED.append(process)
			return process

		# 1. A first install into the Battle.net copy: every page.
		installer = start_installer()
		window = find_window(SETUP_TITLE)
		if not window:
			print("The installer window did not open.")
			return 1
		shoot(window, pic("welcome"), wait=2.5)
		click(window, "Next")
		shoot(window, pic("tiles-both-found"))
		hover(window, "Steam")
		# The folder shows in a tip (a THintWindow) when the mouse stays over a tile. The picture tool does not capture
		# the tip, so this picture shows only the highlight of the tile.
		shoot(window, pic("tile-hover"), wait=0.8, raise_window=False)
		move_mouse_to_title(window)  # A stray click must not hit a tile.
		click(window, "Battle.net")  # A tile: it chooses the place and goes on. The page has no Next button.
		shoot(window, pic("shortcuts"))
		click(window, "Next")
		wait_for_button(window, "Install", timeout=20)
		shoot(window, pic("ready-to-install"))
		click(window, "Install")
		shoot(window, pic("downloading"), wait=1.0)
		if wait_for_button(window, "Finish", timeout=90):
			shoot(window, pic("finished"))
			click(window, "Finish")
		else:
			print("No Finish button. Open windows:", [t for t in open_windows() if "D2R" in t or "Setup" in t or "Error" in t or "Retry" in t])
			print("Buttons:", [window_text(c) for c in children(window) if window_text(c)][:20])
			shoot(window, pic("stuck"), wait=0.2)
			log = runs[-1]
			print("Setup log:")
			for line in (log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:] if log.exists() else ["(no log)"]):
				print("   " + line[:200].encode("ascii", "replace").decode("ascii"))
		installer.wait(timeout=30)

		# 1b. Only Battle.net is found (most players). The Steam tile is grey. Then "Other folder": an empty folder page.
		installer = start_installer(steam_found=False)
		window = find_window(SETUP_TITLE)
		click(window, "Next")  # Welcome
		shoot(window, pic("update-or-uninstall"))  # D2RLoader is installed now, so Setup asks what to do.
		click(window, "Next")  # "Update" is marked.
		shoot(window, pic("tiles-one-found"))
		click(window, "Other folder")
		shoot(window, pic("other-folder-page"))
		click(window, "Next")  # The folder is the usual place, and it has no game. Setup says what to do.
		box = find_message(timeout=15)
		if box:
			shoot(box, pic("other-folder-no-game"), wait=0.5)
		else:
			print("No message about the folder without the game.")
		close_setup(installer)

		# 1c. "Uninstall" on the page "Update or Uninstall": the uninstaller opens, and Setup closes without a question.
		installer = start_installer(steam_found=False)
		window = find_window(SETUP_TITLE)
		click(window, "Next")  # Welcome
		time.sleep(1.0)
		click(window, "Uninstall")  # The choice on the new page
		click(window, "Next")
		form = find_window("D2RLoader Uninstall", timeout=15)
		print(("PASS" if form else "FAIL") + ": the uninstall window opens after the choice 'Uninstall'")
		ended = e2e.wait_until(lambda: installer.poll() is not None, 15)
		print(("PASS" if ended else "FAIL") + ": Setup closes after the choice 'Uninstall' (no question)")
		if form:
			shoot(form, pic("uninstall-from-setup"))
			click(form, "Cancel")
		close_setup(installer)
		time.sleep(2)

		# 2. The game is running in the Steam copy: Setup asks the user to close it.
		running = steam / "D2RLoader.exe"
		shutil.copyfile(e2e.PING, running)
		process = subprocess.Popen([str(running), "-n", "120", "127.0.0.1"], stdout=subprocess.DEVNULL)
		try:
			time.sleep(1)
			installer = start_installer("/DIR=" + str(steam))
			window = find_window(SETUP_TITLE)
			click(window, "Next")  # Welcome
			shoot(window, pic("folder-page"))  # With /DIR= the choice page is hidden and the folder page shows.
			click(window, "Next")
			time.sleep(1.0)
			click(window, "Next")  # The shortcuts page.
			wait_for_button(window, "Install", timeout=20)
			click(window, "Install")
			box = find_message(timeout=15)
			if box:
				shoot(box, pic("game-running"), wait=0.5)
			else:
				print("No message about the running game.")
			close_setup(installer)
		finally:
			process.kill()
			process.wait()
			running.unlink()

		# 3. A folder without D2R.exe: Setup says so.
		empty = e2e.new_game(work, "Empty folder", with_exe=False)
		installer = start_installer("/DIR=" + str(empty))
		window = find_window(SETUP_TITLE)
		click(window, "Next")  # Welcome
		time.sleep(1.0)
		click(window, "Next")  # The folder page. Setup checks the folder.
		box = find_message(timeout=15)
		if box:
			shoot(box, pic("wrong-folder"), wait=0.5)
		else:
			print("No message about the wrong folder.")
		close_setup(installer)

		# 3b. The player cancels during the download with the Cancel button in the corner.
		# Setup must ask "Exit Setup?", end after "Yes", and write nothing into the game folder.
		cancel_game = e2e.new_game(work, "Cancel copy")
		e2e.SITE.chunk_delay = 0.3  # A slow download, so that there is time to click Cancel.
		installer = start_installer("/DIR=" + str(cancel_game))
		window = find_window(SETUP_TITLE)
		for _ in range(3):  # Welcome, folder, shortcuts
			time.sleep(1.0)
			click(window, "Next")
		wait_for_button(window, "Install", timeout=20)
		click(window, "Install")
		time.sleep(1.5)
		shoot(window, pic("downloading-with-cancel"), wait=0.1, raise_window=False)
		print("The 'Stop download' button is hidden:", not any(window_text(c).replace("&", "") == "Stop download" and user32.IsWindowVisible(c) for c in children(window)))
		click(window, "Cancel")
		box = find_message(timeout=10)
		if box:
			shoot(box, pic("exit-setup-question"), wait=0.4)
			click(box, "Yes")
		else:
			print("FAIL: no 'Exit Setup?' question")
		ended = e2e.wait_until(lambda: installer.poll() is not None, 20)
		print(("PASS" if ended else "FAIL") + ": Setup ends after Cancel during the download")
		left = sorted(p.name for p in cancel_game.iterdir())
		print(("PASS" if left == ["D2R.exe"] else "FAIL") + f": nothing is written into the game folder {left}")
		close_setup(installer)
		e2e.SITE.chunk_delay = 0.05

		# 4. A second install, into the Steam copy, so that the uninstaller has two installs to show.
		installer = start_installer("/DIR=" + str(steam))
		window = find_window(SETUP_TITLE)
		for _ in range(3):
			time.sleep(1.5)
			click(window, "Next")
		wait_for_button(window, "Install", timeout=20)
		click(window, "Install")
		wait_for_button(window, "Finish", timeout=90)
		click(window, "Finish")
		installer.wait(timeout=30)

		# 5. The uninstaller with two installs.
		exes = sorted(base.glob("*/unins000.exe"))
		print("uninstallers:", len(exes))
		if exes:
			uninstaller = subprocess.Popen([str(exes[0]), f"/LOG={work / 'uninstall.log'}"])
			form = find_window("D2RLoader Uninstall")
			if form:
				shoot(form, pic("uninstall-choose"))  # The tile of this uninstaller is marked.
				click(form, "Steam")
				shoot(form, pic("uninstall-steam-marked"), wait=0.6)
				click(form, "Battle.net")
				shoot(form, pic("uninstall-battlenet-marked"), wait=0.6)
				click(form, "Cancel")
			else:
				print("The uninstall window did not open.")
			uninstaller.wait(timeout=30)

		# 6. The uninstaller with one install (remove the other one first, silently). This one runs to the end.
		if len(exes) == 2:
			subprocess.run([str(exes[1]), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/Picked=1"], timeout=60)
			e2e.wait_until(lambda: not exes[1].exists(), 60)
			time.sleep(1)
			uninstaller = subprocess.Popen([str(exes[0]), f"/LOG={work / 'uninstall.log'}"])
			form = find_window("D2RLoader Uninstall")
			if form:
				shoot(form, pic("uninstall-one"))
				click(form, "Uninstall")
				answer_uninstall_boxes(uninstaller, pic)
			uninstaller.wait(timeout=30)
	finally:
		server.shutdown()
		time.sleep(0.5)
		logs = out / "logs"  # Keep the Setup logs. They show why a window closed.
		logs.mkdir(exist_ok=True)
		for log in list(work.glob("setup-*.log")) + list(work.glob("uninstall*.log")):
			shutil.copyfile(log, logs / log.name)
		shutil.rmtree(work, ignore_errors=True)
		kill_setup()
	print("Pictures are in", out)
	return 0


if __name__ == "__main__":
	sys.exit(main())
