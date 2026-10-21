"""A stand-in for ssh and scp, for tests/check-publish.py. The "server" is a folder on this PC (D2RL_FAKE_ROOT).

	python fake_ssh.py ssh <the arguments that tools/publish.py gives to ssh>
	python fake_ssh.py scp <the arguments that tools/publish.py gives to scp>

It understands only the commands that tools/publish.py sends: test -d, test -w, mkdir, mkdir -p, chmod, cd, mv -f, rmdir, rm -rf.
A server path such as /srv/www/x is the folder D2RL_FAKE_ROOT/srv/www/x. Every command is written to D2RL_FAKE_ROOT/log.txt.
D2RL_FAKE_FAIL makes it fail on purpose: "login" (ssh and scp), "scp" (the copy), "move" (the second mv).
D2RL_FAKE_CORRUPT=<file name> changes one byte of that file after it is moved into place.
"""

import os
import shlex
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ["D2RL_FAKE_ROOT"])
FAIL = os.environ.get("D2RL_FAKE_FAIL", "")
CORRUPT = os.environ.get("D2RL_FAKE_CORRUPT", "")


def local(remote, cwd):
	path = remote if remote.startswith("/") else cwd + "/" + remote
	return ROOT / path.lstrip("/")


def log(text):
	with open(ROOT / "log.txt", "a", encoding="utf-8") as stream:
		stream.write(text + "\n")


def do_ssh(arguments):
	if FAIL == "login":
		return 255
	cwd, moves = "/", 0
	for part in arguments[-1].split(" && "):
		words = shlex.split(part)
		log("ssh " + part)
		name, rest = words[0], words[1:]
		if name == "cd":
			cwd = rest[0]
		elif name == "test":
			path = local(rest[1], cwd)
			if not path.is_dir():
				return 1
		elif name == "mkdir":
			recursive = rest[0] == "-p"
			path = local(rest[-1], cwd)
			if path.exists() and not recursive:
				return 1
			path.mkdir(parents=recursive, exist_ok=recursive)
		elif name == "chmod":
			for file in rest[1:]:
				if not local(file, cwd).exists():
					return 1
		elif name == "mv":
			moves += 1
			if FAIL == "move" and moves == 2:
				return 1
			source, target = local(rest[1], cwd), local(rest[2], cwd)
			os.replace(source, target)
			if target.name == CORRUPT:
				data = bytearray(target.read_bytes())
				data[0] ^= 1
				target.write_bytes(bytes(data))
		elif name == "rmdir":
			local(rest[0], cwd).rmdir()
		elif name == "rm":
			shutil.rmtree(local(rest[-1], cwd), ignore_errors=True)
		else:
			print("fake ssh: unknown command " + part, file=sys.stderr)
			return 2
	return 0


def do_scp(arguments):
	if FAIL in ("login", "scp"):
		return 255 if FAIL == "login" else 1
	words, index = [], 0
	while index < len(arguments):
		if arguments[index] == "-o":
			index += 2
			continue
		words.append(arguments[index])
		index += 1
	destination = words[-1].split(":", 1)[1]
	folder = local(destination, "/")
	for name in words[:-1]:
		log("scp " + name + " -> " + destination)
		shutil.copyfile(name, folder / name)
	return 0


if __name__ == "__main__":
	program, rest = sys.argv[1], sys.argv[2:]
	sys.exit(do_ssh(rest) if program == "ssh" else do_scp(rest))
