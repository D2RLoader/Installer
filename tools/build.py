"""Builds the installer: out/D2RLoader-Installer.exe. The easy way is build-installer.cmd in the main folder.

	python -I tools/build.py                                   signed, if the D2RLoader certificate is in the Windows store
	python -I tools/build.py --unsigned                        not signed
	python -I tools/build.py --thumbprint <thumbprint>         signed with this certificate
	python -I tools/build.py --manifest-url <https address>    a staging build that reads another manifest, to test before the release

A staging build is written to out/D2RLoader-Installer-staging.exe, so it cannot replace the real installer by mistake.

The signature needs a code signing certificate with a private key in the Windows certificate store. Without --thumbprint, the
script uses the newest valid certificate with the subject CN=D2RLoader. If there is none, it builds without a signature and says so.
The signature has a time stamp from --timestamp-url (a web request). Setup and the uninstaller are both signed.
Needs Inno Setup 7. Set ISCC to the path of ISCC.exe if it is not in a normal place.
"""

import argparse
import datetime
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "out"
DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"
CERTIFICATE_SUBJECT = "CN=D2RLoader"
WARN_DAYS_BEFORE_EXPIRY = 60

# Prints the thumbprint and the end date of the best certificate, or nothing.
FIND_CERTIFICATE = r"""
$now = Get-Date
$certificates = @('CurrentUser', 'LocalMachine') | ForEach-Object { Get-ChildItem "Cert:\$_\My" -CodeSigningCert }
$best = $certificates | Where-Object { $_.Subject -eq 'SUBJECT' -and $_.HasPrivateKey -and $_.NotBefore -le $now -and $_.NotAfter -gt $now } |
	Sort-Object NotAfter -Descending | Select-Object -First 1
if ($best) { $best.Thumbprint; $best.NotAfter.ToString('yyyy-MM-dd') }
"""


def find_iscc():
	candidates = [
		os.environ.get("ISCC"),
		os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"),
		r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe",
		r"C:\Program Files\Inno Setup 7\ISCC.exe",
	]
	for path in candidates:
		if path and Path(path).exists():
			return path
	sys.exit("ISCC.exe was not found. Install Inno Setup 7 (https://jrsoftware.org/isdl.php) or set the ISCC variable to the path of ISCC.exe.")


def find_certificate():
	"""Returns (thumbprint, valid until as YYYY-MM-DD) of the certificate to sign with, or None."""
	script = FIND_CERTIFICATE.replace("SUBJECT", CERTIFICATE_SUBJECT)
	done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
	lines = done.stdout.split()
	return (lines[0].upper(), lines[1]) if len(lines) >= 2 else None


def sign_tool_command(thumbprint, timestamp_url):
	"""The command that Inno Setup runs for each file to sign. $q is a quote and $f is the file (Inno Setup fills them in)."""
	script = ROOT / "tools" / "sign.ps1"
	command = f"powershell -NoProfile -ExecutionPolicy Bypass -File $q{script}$q -Thumbprint {thumbprint} -TargetPath $f"
	return command + (f" -TimestampUrl {timestamp_url}" if timestamp_url else "")


def signature_of(path):
	"""Returns (status, thumbprint of the signer) as PowerShell reports them."""
	script = f"$s = Get-AuthenticodeSignature -LiteralPath '{path}'; $s.Status; $s.SignerCertificate.Thumbprint"
	done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
	lines = done.stdout.split()
	return (lines[0] if lines else "Unknown"), (lines[1].upper() if len(lines) > 1 else "")


def choose_signing(args):
	"""Returns the thumbprint to sign with, or "" for no signature. Prints what it decided."""
	if args.unsigned:
		return ""
	if args.thumbprint:
		return args.thumbprint.replace(" ", "").upper()
	found = find_certificate()
	if not found:
		print(f"No valid certificate {CERTIFICATE_SUBJECT} with a private key is in the Windows certificate store.")
		print("The installer will NOT be signed.")
		return ""
	thumbprint, until = found
	print(f"Signing with the certificate {CERTIFICATE_SUBJECT} ({thumbprint}), valid until {until}.")
	days_left = (datetime.date.fromisoformat(until) - datetime.date.today()).days
	if days_left < WARN_DAYS_BEFORE_EXPIRY:
		print(f"WARNING: the certificate ends in {days_left} days. Make a new one before it ends.")
	return thumbprint


def main():
	parser = argparse.ArgumentParser(description="Builds the installer.")
	choice = parser.add_mutually_exclusive_group()
	choice.add_argument("--thumbprint", help="sign with the certificate with this thumbprint (default: the certificate CN=D2RLoader in the Windows store)")
	choice.add_argument("--unsigned", action="store_true", help="do not sign")
	parser.add_argument("--timestamp-url", default=DEFAULT_TIMESTAMP_URL, help=f"the time stamp server (default: {DEFAULT_TIMESTAMP_URL})")
	parser.add_argument("--manifest-url", help="the address of the manifest for a staging build (default: the address in src/installer.iss)")
	args = parser.parse_args()
	if args.manifest_url and not args.manifest_url.startswith("https://"):
		print("ERROR: the manifest address must start with https://")
		return 1

	iscc = find_iscc()
	thumbprint = choose_signing(args)
	name = "D2RLoader-Installer-staging" if args.manifest_url else "D2RLoader-Installer"
	output = OUTPUT_DIR / (name + ".exe")
	command = [iscc, "/DOutputName=" + name]
	if args.manifest_url:
		command.append("/DManifestUrl=" + args.manifest_url)
	if thumbprint:
		command += ["/DSIGN", "-sd2rloader=" + sign_tool_command(thumbprint, args.timestamp_url)]
	command.append(str(ROOT / "src" / "installer.iss"))
	if output.exists():
		output.unlink()
	done = subprocess.run(command, capture_output=True, text=True)
	if done.returncode != 0 or not output.exists():
		print(done.stdout[-3000:] + done.stderr[-1000:])
		print("ERROR: the build failed.")
		return 1

	print(f"Built {output}")
	print(f"  {output.stat().st_size:,} bytes, SHA-256 {hashlib.sha256(output.read_bytes()).hexdigest()}")
	if args.manifest_url:
		print(f"  Staging build. It reads {args.manifest_url}")
	if not thumbprint:
		print("  Not signed.")
		return 0
	status, signer = signature_of(output)
	print(f"  Signature: {status}, signer {signer}")
	if signer != thumbprint or status != "Valid":
		print("ERROR: the installer is not signed with the certificate that was asked for, or Windows does not trust it.")
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
