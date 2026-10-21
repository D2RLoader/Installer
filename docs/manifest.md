# Manifest format

The manifest is a JSON file on the D2RLoader website. It lists every file of one D2RLoader release. The installer reads it to learn what to download. Schema version: 1.

There is one manifest. It describes the latest release. There are no channels. Previews have no installer.

## Example

The size and hash of the first file are the real values of D2RLoader 1.3.1-beta. The other hashes are shortened. The URLs are examples.

```json
{
  "schema": 1,
  "version": "1.3.1-beta",
  "files": [
    {
      "path": "D2RLoader.exe",
      "url": "https://d2rloader.net/download/D2RLoader.exe",
      "size": 23331160,
      "sha256": "93021dad48533bcfca8a95c69a0cc00cdb9008a3ce6ceba1d04c7aca71985a10"
    },
    {
      "path": "d2rloader/config/d2rloader.toml",
      "url": "https://d2rloader.net/download/d2rloader.toml",
      "size": 9235,
      "sha256": "86be762e...",
      "onlyIfMissing": true
    }
  ],
  "folders": ["mods", "d2rloader/plugins", "d2rloader/data", "d2rloader/logs", "d2rloader/crashes"]
}
```

## Fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | integer | The format version. The installer stops if this number is higher than the one it knows. |
| `version` | string | The release name. The installer shows it to the user. It does not compare versions. |
| `files` | array | The files of the release. |
| `folders` | array | Folders to create if they are missing. Each name follows the `path` rules. |

Each entry in `files`:

| Field | Type | Meaning |
| --- | --- | --- |
| `path` | string | Where the file goes, relative to the game folder. Use `/` between names. |
| `url` | string | Where to download the file. It must start with `https://`. |
| `size` | integer | The exact size in bytes. |
| `sha256` | string | The SHA-256 hash of the file. Use 64 lowercase hexadecimal digits. |
| `onlyIfMissing` | boolean | Optional. Default `false`. If `true`, the installer writes the file only when it does not exist. Use it for files that the user edits, such as `d2rloader.toml`. |

## Path rules

The manifest decides where the installer writes files. The installer must reject the whole manifest if any `path` or `folders` entry breaks one of these rules:

- It is not empty.
- It does not start or end with `/`.
- It has no `\` and no `:`. This blocks drive letters and alternate data streams.
- No name in it is empty, `.`, or `..`.
- No name in it ends with a dot or a space.

Examples that the installer rejects: `../D2R.exe`, `C:/Windows/x.dll`, `mods//a`, `mods\a`.

## Limits

The installer rejects the manifest if it goes over one of these limits:

- The manifest has at most 262,144 characters.
- JSON lists and objects are nested at most 8 levels deep.
- `files` has 1 to 200 entries. `folders` has at most 100 entries.
- `version` has 1 to 64 characters.
- `size` is a whole number from 1 to 4,294,967,296 (4 GiB).
- Two files cannot have the same `path`. Letter case does not count: `D2RLoader.exe` and `d2rloader.EXE` are the same path.
- A key that appears twice in one object is an error.

The installer ignores keys that it does not know. A later version of the format can add keys.

## Make the manifest

`tools/make-manifest.py` makes the manifest and the download files from the release zip of D2RLoader:

```
python -I tools/make-manifest.py D2RLoader-1.4.0.zip out/site
```

The output folder gets `manifest.json` and each file of the release under its plain name (`D2RLoader.exe`, `D2RCore.dll`, `d2rloader.mpq`, `d2rloader.toml`). The `url` of a file is the base address and this name. The default base address is `https://d2rloader.net/download/`. Change it with `--base-url`. The version comes from the zip name (`D2RLoader-<version>.zip`). Change it with `--version`.

The script does these things:

- It checks the zip against `<zip>.sha256`, if that file is next to the zip.
- It sets `onlyIfMissing` for `d2rloader/config/d2rloader.toml`.
- It puts the empty folders of the zip in `folders`.
- It stops with an error if the release breaks a rule in this document. Examples: an empty file, two files with the same plain name, an unsafe path.
- It writes nothing when it stops. It does not write into a folder that has files.

Upload the files first and `manifest.json` last. Then no player gets a new manifest before its files are on the website.

## How an install or update works

1. The installer finds the game folder and checks that `D2R.exe` is in it.
2. It checks that the game is closed. If it is not, the installer asks the user to close it.
3. It downloads the manifest and checks the rules above.
4. For each file, it decides if the file is needed:
   - With `onlyIfMissing` and the file exists: skip.
   - If the local file has the same SHA-256 hash: skip.
   - Otherwise: download it to a temporary folder.
5. It checks the size and hash of each downloaded file. If one is wrong, it deletes the download and stops. The game folder has not changed yet.
6. Only after all downloads pass, Setup copies the files into the game folder. It also copies the files that are already up to date, so the uninstaller knows every file. If a file cannot be replaced, Setup stops and puts back the files that it copied in this run.

## URLs

During beta, the file URLs are fixed. Each release replaces the files at the same URLs. This works because the installer checks the hash of every download, and the hash comes from the manifest. A player who read the old manifest just before an upload can get a file that does not match it. The installer then stops and does not change the game folder. The player runs it again.

After beta, the `url` values can point to a folder for each version, for example `https://d2rloader.net/download/1.4.0/D2RLoader.exe`. The installer does not change. Only the manifest changes.

## Signature (phase 2)

Phase 2 adds a signature file next to the manifest: the manifest URL with `.issig` added. The installer holds the public key. It rejects a manifest with a missing or wrong signature.

Inno Setup 7 can do this check itself (the download page function `AddWithISSigVerify`), and its tool `ISSigTool.exe` makes the keys and the signature. We have not tried it yet.

The signature is a separate file so the JSON does not need a fixed byte order. The manifest format does not change in phase 2.

A hash from the same website only catches broken downloads. If someone controls the website, they can change the files and the hashes. The signature protects against that. Phase 1 does not have it.
