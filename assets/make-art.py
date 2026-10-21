"""Makes the installer pictures from the D2RLoader portal logo (assets/portal.png).

It writes PNG files for the Setup window and a multi-size icon. The results are in the repository,
so you only need this script when you change the art. It needs `ffmpeg` on PATH.

	python -I assets/make-art.py

Files written to assets/generated:
	wizard-<width>x<height>.png   The tall picture on the Welcome and Finish pages, for each screen scale.
	small-<width>x<height>.png    The small picture at the top right of the other pages (with transparency).
	d2rloader.ico                 The icon of Setup, in 7 sizes. It joins the files in assets/icons.
"""

import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "portal.png"
OUT = HERE / "generated"

# The sizes that Inno Setup uses for 100%, 125%, 150%, 175%, 200%, 225%, and 250% screen scale.
WIZARD_SIZES = [(164, 314), (192, 386), (246, 459), (273, 556), (328, 604), (355, 700)]
SMALL_SIZES = [(55, 55), (64, 68), (83, 80), (92, 97), (110, 106), (138, 140)]
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def ffmpeg(*args):
	command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
	done = subprocess.run(command, capture_output=True, text=True)
	if done.returncode != 0:
		sys.exit("ffmpeg failed:\n" + done.stderr)


def make_wizard(width, height):
	"""A dark picture with the portal in the middle. The portal is dimmed, and the edges go dark."""
	portal = int(width * 1.10)
	graph = (
		# 1: the portal, faded so it does not shine, then placed on the background.
		f"[1:v]format=rgba,scale={portal}:{portal},colorchannelmixer=rr=0.62:gg=0.55:bb=0.55:aa=0.80[portal];"
		# 0: a very dark background that gets a little red at the bottom.
		f"[0:v][portal]overlay=(W-w)/2:(H*0.42)-(h/2):format=auto,"
		# The edges of the picture go dark.
		f"vignette=angle=PI/3.2,format=rgb24"
	)
	ffmpeg(
		"-f", "lavfi", "-i", f"gradients=s={width}x{height}:c0=0x050202:c1=0x2b0907:x0={width // 2}:y0=0:x1={width // 2}:y1={height}:d=1",
		"-i", str(SOURCE), "-filter_complex", graph, "-frames:v", "1",
		str(OUT / f"wizard-{width}x{height}.png"),
	)


def make_small(width, height):
	"""The portal on a transparent background. It works on a light page and on a dark page."""
	side = min(width, height)
	graph = f"scale={side}:{side},pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,format=rgba"
	ffmpeg("-i", str(SOURCE), "-vf", graph, "-frames:v", "1", str(OUT / f"small-{width}x{height}.png"))


def make_icon():
	"""Joins the single-size D2RLoader icons in assets/icons into one icon with 7 sizes."""
	entries = []
	for size in ICON_SIZES:
		raw = (HERE / "icons" / f"d2rloader_{size}.ico").read_bytes()
		reserved, kind, count = struct.unpack_from("<HHH", raw, 0)
		if kind != 1 or count != 1:
			sys.exit(f"d2rloader_{size}.ico must be an icon file with one image.")
		width, height, colors, zero, planes, bits, length, offset = struct.unpack_from("<BBBBHHII", raw, 6)
		entries.append((width, height, colors, planes, bits, raw[offset:offset + length]))

	header = struct.pack("<HHH", 0, 1, len(entries))
	position = 6 + 16 * len(entries)
	directory = b""
	data = b""
	for width, height, colors, planes, bits, image in entries:
		directory += struct.pack("<BBBBHHII", width, height, colors, 0, planes, bits, len(image), position + len(data))
		data += image
	(OUT / "d2rloader.ico").write_bytes(header + directory + data)


def main():
	if not SOURCE.exists():
		sys.exit(f"Missing {SOURCE}")
	OUT.mkdir(exist_ok=True)
	only = sys.argv[1] if len(sys.argv) > 1 else ""
	for width, height in WIZARD_SIZES:
		if only in ("", "wizard"):
			make_wizard(width, height)
	for width, height in SMALL_SIZES:
		if only in ("", "small"):
			make_small(width, height)
	if only in ("", "icon"):
		make_icon()
	print("Done:", ", ".join(sorted(p.name for p in OUT.iterdir())))


if __name__ == "__main__":
	main()
