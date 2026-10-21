# Releasing

This page is for the maintainer. It describes how a D2RLoader release reaches players. The installer itself does not change for each release. It reads a manifest from the website, and the manifest lists the files of the newest D2RLoader.

The website has its own steps (the download page with the version and the hash, and a check of the live files). They are in the website project.

## Publish a release

1. Build D2RLoader. Its build writes the release ZIP `D2RLoader-<version>.zip` and the file `D2RLoader-<version>.zip.sha256`.
2. Drag the ZIP onto `publish-release.cmd`. It asks where to publish: the test folder or the live site. It shows the files and waits until you type `yes`. Then it uploads the ZIP and the four files, and `manifest.json` last. At the end it downloads every public file and checks its size and SHA-256 hash. Do the test folder first (see below). Then do the live site.
3. Build the installer with `build-installer.cmd`, and upload it with `publish-installer.cmd`. Do this only when the installer code changed.

`make-release.cmd` does only the first half of step 2. It writes `manifest.json` and the files into `out\release` and uploads nothing. Use it to look at the result, or to upload by hand. It checks the ZIP against the `.sha256` file, and it stops with an error if the release breaks a rule of [manifest.md](manifest.md).

## Settings for the upload

Copy `publish.env.example` to `publish.env`. The file is not committed. It holds only the name of the SSH target (a `Host` entry in `~/.ssh/config`), the folder on the server, and the public address of that folder. No key and no password are in the project. The scripts use the `ssh` and `scp` programs from your PATH, so test your login first with `ssh <your SSH target> true`. If the key has a passphrase, load it into the ssh-agent (`ssh-add`), or you must type it for each connection.

How the upload keeps the live site safe:

- Each file goes into a temporary folder on the server first, and then moves into place, so nobody gets a half-written file. The temporary folder is removed after an error too.
- `manifest.json` moves last, after the ZIP and the four files.
- The script sets the permissions that the web server needs (files 644, folders 755).
- A preview version (for example `1.4.0-beta-preview.1`) goes only to the test folder, unless you give `--allow-preview` in a terminal.
- If a public file is wrong after the upload, the script says which one and stops.

## Test a release before it goes live

Choose the test folder in `publish-release.cmd`. The files go to the `test` folder of the server (`https://d2rloader.net/download/test/`), without the ZIP. Then build an installer that reads the test manifest, and click through it:

```
.\build-installer.cmd https://d2rloader.net/download/test/manifest.json
```

This makes `out\D2RLoader-Installer-staging.exe`. It never replaces the real installer. Remove the files in the test folder afterwards.

## Release the installer on GitHub

The installer on the website and the installer on GitHub are two different files. The website offers the build from the maintainer's PC, signed with the project's own certificate. The GitHub release has the build from GitHub Actions, which is not signed.

1. Set `InstallerVersion` in `src/installer.iss` and commit. Push `main` and wait for a green build.
2. Make a signed tag with the same version, and push it. The tag must be `v` plus the version:

   ```
   git tag -s v0.1.0 -m "D2RLoader Installer 0.1.0"
   git push github v0.1.0
   ```

3. The workflow builds again from the tagged commit and makes the release. Open the release page. Check the file name, the hash in the notes, and the text.

If the job fails, remove the tag (`git push github :refs/tags/v0.1.0` and `git tag -d v0.1.0`), fix the problem, and tag again. A tag whose version does not match `InstallerVersion` stops the build before it starts.

## Signing

`build-installer.cmd` signs Setup and its uninstaller when the certificate `CN=D2RLoader` is in the Windows certificate store. See [development.md](development.md#build) and the "Code signing policy" in the [README](../README.md#code-signing-policy).

The scripts call the Python tools in `tools`. Their options are in the first lines of each file: `python -I tools/build.py --help`, `python -I tools/make-manifest.py --help`, and `python -I tools/publish.py --help`.
