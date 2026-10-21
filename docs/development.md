# Development

## Folders

| Folder | Content |
| --- | --- |
| `src` | The installer. `installer.iss` is the main script. The other `.pas` files are its parts: `manifest.pas`, `gamefolder.pas`, `processcheck.pas`, `installs.pas`, `tiles.pas`, and `dialog.pas`. |
| `src/languages` | The texts of Setup in each language (`.isl` files). See [translations.md](translations.md). |
| `src/third_party` | A JSON reader for Inno Setup scripts. See [NOTICE.md](../src/third_party/NOTICE.md). |
| `tests` | Automatic tests. |
| `tools` | `make-manifest.py` (the manifest and the download files), `build.py` (builds the installer, signed or not), `sign.ps1` (the signing step that `build.py` gives to Inno Setup), and `publish.py` (uploads over SSH). See [releasing.md](releasing.md). |
| `docs` | This documentation. |
| `assets` | The pictures of the Setup window, made from the D2RLoader logo (`portal.png`). `generated` has the finished files. Run `python -I assets/make-art.py` to make them again. It needs `ffmpeg`. |

The `.cmd` files in the main folder run the Python tools without options: `build-installer.cmd`, `make-release.cmd`, `publish-release.cmd`, `publish-installer.cmd`, and `run-tests.cmd`.

## Build

You need [Inno Setup 7](https://jrsoftware.org/isinfo.php).

```
ISCC src\installer.iss
```

The installer is `out\D2RLoader-Installer.exe`. It is not signed.

`python -I tools/build.py` builds the same installer and signs it. It uses the newest valid certificate with the subject `CN=D2RLoader` and a private key in the Windows certificate store. It adds a time stamp from a web request. It prints which certificate it uses and when the certificate ends. Without such a certificate, it builds the installer without a signature and says so. This is the case on the PC of a person who forks the project. `--unsigned` and `--thumbprint <thumbprint>` change this.

The pictures and the icon in `assets` are the D2RLoader logo, which is not under the GPL (see [NOTICE.md](../assets/NOTICE.md)). To build a version without them, give `/DNO_ART` to the compiler, or delete `assets/generated`. Setup then uses the standard Inno Setup pictures.

## Tests

You need Inno Setup 7 and Python 3. Double-click `run-tests.cmd`, or run `python -I tests/run-all.py`. It builds the installer and runs everything below.

- `tests/unit.iss` tests the manifest rules, the Steam file reader, the game folder lookup, and the check for a running `D2RLoader.exe`. It uses 80 test manifests from `tests/fixtures/manifests`. Run `python -I tests/make-fixtures.py` to write them again.
- `tests/e2e.py` starts a small web server on your computer, builds a fake game folder, and runs the installer in silent mode. Then it checks the result on disk. The cases include:
  - A first install, an update, a repair, and a changed config file.
  - Wrong hashes and sizes, unsafe paths, and a broken manifest.
  - The choice of game folder, a running game, and a locked file (Setup stops and puts back the files).
  - The uninstaller, also after an update, after a manual unpack, while the game runs, and with two game folders.
  - A 40 MB file, folder names with non-English letters, and an install from the files that `tools/make-manifest.py` writes.
- `tests/check-make-manifest.py` tests `tools/make-manifest.py` with small fake release zips: a good release, and many bad ones that each break one rule.
- `tests/check-publish.py` tests `tools/publish.py`. The "server" is a folder on your PC, `tests/fake_ssh.py` stands in for `ssh` and `scp`, and a small web server hands out that folder. Nothing leaves your PC.
- `tests/check-languages.py` checks that every translation file has the same texts and `%` codes as `english.isl`, and that every text used in the code exists.

### Continuous build

`.github/workflows/build.yml` runs on every push to `main`, on pull requests, and on request. It runs on a GitHub-hosted Windows runner with read-only permissions. The two actions that it uses are pinned to commits. The steps are:

1. Check out the source.
2. Download Inno Setup 7.1.0 from its GitHub release. The step stops if the SHA-256 hash is not the pinned one, or if the file does not have a valid signature of Pyrsys B.V.
3. Run `tests/run-all.py`. This is the same suite as `run-tests.cmd`.
4. Build the installer with `tools/build.py --unsigned`.
5. Write the size and the SHA-256 hash to the job summary, and keep the installer as the artifact `D2RLoader-Installer-unsigned`.

To use a newer Inno Setup, change the version in the URL and the hash in the workflow together.

A tag that starts with `v` (for example `v0.1.0`) also starts a second job, `release`. The build job first checks that the tag is `v` plus the `InstallerVersion` in `src/installer.iss`, so a wrong tag stops the build. The `release` job gets the installer from the build and checks its hash against the one that the build reported. Then it makes a GitHub release with the file `D2RLoader-Installer-<version>-unsigned.exe`. This job has write access to releases. It does not check out the repository and runs none of its code. The release notes have the commit, the hash, and a note that the file is not signed.

### The test build

The test build (`/DTEST_LOOPBACK`) exists only for the tests. It allows `http://127.0.0.1` and reads the manifest address from `/Manifest=`. It never reads the real registry, so a test cannot change a real game folder. It takes its "found" game folders from `/FakeBattleNet=` and `/FakeSteam=`, and keeps its uninstaller in the folder from `/UninstDir=`. It does not change the list of installed apps. The test script stops at once if the installer uses another folder than the one it was given. The production build has none of these options.

### Try the wizard

The automatic tests run Setup in silent mode. To click through the pages yourself, run this after `run-all.py`:

```
python -I tests/try-wizard.py
```

It makes two fake game folders and a slow fake website, and opens the installer window. Nothing real is touched. A menu lets you do four things. You can open the installer again (an update), publish a new release, and open the uninstaller of a game folder. You can also start a fake `D2RLoader.exe` to see the "game is open" message. Give a language name to try another language, for example `python -I tests/try-wizard.py german`.

To save a picture of every page and window (needs `ffmpeg`), run `python -I tests/screenshots.py`. It opens windows on your screen for about a minute. Do not use the mouse or the keyboard while it runs. The pictures are in `out/screens`. `python -I tests/language-pictures.py` does the same for each language, to find text that does not fit.
