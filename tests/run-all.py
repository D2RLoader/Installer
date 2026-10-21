"""Builds and runs every test of the installer.

Steps:
  1. Make the manifest test files. Check the translation files, tools/make-manifest.py, and tools/publish.py.
  2. Build and run the unit tests (tests/unit.iss). They read out/unit-report.txt.
  3. Build the installer twice: the production build (compile check) and the test build.
  4. Run the end-to-end tests (tests/e2e.py).

Needs Inno Setup 7. Set ISCC to the path of ISCC.exe if it is not in a normal place.
Run: python -I tests/run-all.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from build import find_iscc


def compile_script(iscc, script, *defines):
	command = [iscc, *defines, str(ROOT / script)]
	done = subprocess.run(command, capture_output=True, text=True, timeout=300)
	ok = done.returncode == 0
	print(("PASS " if ok else "FAIL ") + f"compile {script} {' '.join(defines)}".rstrip())
	if not ok:
		print(done.stdout[-2000:])
	return ok


def main():
	iscc = find_iscc()
	failed = False

	subprocess.run([sys.executable, "-I", str(ROOT / "tests" / "make-fixtures.py")], check=True)
	failed |= subprocess.run([sys.executable, "-I", str(ROOT / "tests" / "check-languages.py")]).returncode != 0
	failed |= subprocess.run([sys.executable, "-I", str(ROOT / "tests" / "check-make-manifest.py")]).returncode != 0
	failed |= subprocess.run([sys.executable, "-I", str(ROOT / "tests" / "check-publish.py")]).returncode != 0

	failed |= not compile_script(iscc, "tests/unit.iss")
	report = ROOT / "out" / "unit-report.txt"
	if report.exists():
		report.unlink()
	subprocess.run([str(ROOT / "out" / "unit-tests.exe"), "/VERYSILENT"], timeout=300)
	text = report.read_text(encoding="utf-8", errors="replace") if report.exists() else ""
	passed = sum(1 for line in text.splitlines() if line.startswith("PASS "))
	bad = [line for line in text.splitlines() if line.startswith("FAIL ")]
	print(f"unit tests: {passed} passed, {len(bad)} failed" + ("" if text.rstrip().endswith("DONE") else " (the report is incomplete)"))
	for line in bad:
		print("  " + line)
	failed |= bool(bad) or not text.rstrip().endswith("DONE")

	# A compile check only. It has its own file name, so it cannot replace the real (signed) installer in out/.
	failed |= not compile_script(iscc, "src/installer.iss", "/DOutputName=installer-compile-check")
	failed |= not compile_script(iscc, "src/installer.iss", "/DTEST_LOOPBACK", "/DOutputName=installer-test")

	done = subprocess.run([sys.executable, "-I", str(ROOT / "tests" / "e2e.py")], timeout=1800)
	failed |= done.returncode != 0

	print("\nALL TESTS PASSED" if not failed else "\nSOME TESTS FAILED")
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
