# Translations

Setup has the same languages as Diablo II: Resurrected (the list `LocaleExpectation` in D2RLoader):

| Game language | Setup language | File |
| --- | --- | --- |
| English (`enUS`) | English | `src/languages/english.isl` (the master file) |
| German (`deDE`) | Deutsch | `german.isl` |
| Spanish (`esES`, `esMX`) | Español | `spanish.isl` (Inno Setup has one Spanish, so it serves both) |
| French (`frFR`) | Français | `french.isl` |
| Italian (`itIT`) | Italiano | `italian.isl` |
| Japanese (`jaJP`) | 日本語 | `japanese.isl` |
| Korean (`koKR`) | 한국어 | `korean.isl` |
| Polish (`plPL`) | Polski | `polish.isl` |
| Portuguese, Brazil (`ptBR`) | Português Brasileiro | `brazilianportuguese.isl` |
| Russian (`ruRU`) | Русский | `russian.isl` |
| Chinese, simplified (`zhCN`) | 简体中文 | `chinesesimplified.isl` |
| Chinese, traditional (`zhTW`) | 繁體中文 | `chinesetraditional.isl` |

**Status: every language except English is a first draft. A native speaker has not checked it yet.** Please read your language and fix what is wrong. The most important texts are the ones near a deletion (`ConfirmUninstall`, `DeleteSettings`, `DeleteSettingsNote`, `UninstallOne`) and the ones about the game (`GameOpenRetry`, `GameStillOpen`).

## How Setup picks the language

Setup uses the language of Windows. If Windows has a language that Setup does not have, Setup shows a list. The standard texts (the buttons, "Welcome", and so on) come from Inno Setup, which has its own translation of each language. Our files add the texts that are special to D2RLoader. The uninstaller uses the language that was used to install.

## Fix a translation

1. Open the file of your language in `src/languages`. Keep the encoding: UTF-8 **with** a byte order mark (BOM). Most editors have this as "UTF-8 with BOM".
2. Change only the text after the `=`. Do not change the name before the `=`.
3. Keep the `%1`. Setup puts a version number or a file name in its place.
4. Use short sentences and common words. Many players are not native speakers, and many are older.
5. Use the same words as the standard Inno Setup file of your language for "Setup", "Uninstall", "shortcut", and "folder". The files are in the folder `Languages` of your Inno Setup 7 installation.
6. `Battle.net` and `Steam` are names. Do not translate them.
7. Run `python -I tests/check-languages.py`. It checks the names, the `%` codes, and the encoding.
8. To see the pages, run `python -I tests/language-pictures.py <language>`, for example `german`. It makes pictures in `out/lang`. It needs Inno Setup 7, Python, and `ffmpeg`. To try the pages by hand, run `python -I tests/try-wizard.py <language>`.

A text that is missing in a language shows the English text.

## Add a language

1. Copy `english.isl` to a new file with the name of the language (small letters).
2. Translate it.
3. Add a line to the section `[Languages]` in `src/installer.iss`. The standard file of Inno Setup for the language must exist in the folder `Languages` of Inno Setup.
4. Run `python -I tests/check-languages.py`.
