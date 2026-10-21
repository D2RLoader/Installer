; Unit tests for the installer code in src\.
; Build: ISCC tests\unit.iss     Run: out\unit-tests.exe /VERYSILENT     Result: out\unit-report.txt
; The setup program runs every test in InitializeSetup, writes the report, and quits. It installs nothing.

[Setup]
AppName=D2RLoader Installer Unit Tests
AppVersion=0
CreateAppDir=no
Uninstallable=no
PrivilegesRequired=lowest
OutputDir=..\out
OutputBaseFilename=unit-tests
DisableProgramGroupPage=yes

[CustomMessages]
OtherFolder=Other folder

[Code]
#include "..\src\third_party\JsonParser.pas"
#include "..\src\gamefolder.pas"
#include "..\src\processcheck.pas"
#include "..\src\manifest.pas"
#include "..\src\installs.pas"

var
  Report: TStringList;

procedure Expect(Condition: Boolean; const Name: String);
begin
  if Condition then
    Report.Add('PASS ' + Name)
  else
    Report.Add('FAIL ' + Name);
end;

// Writes a UTF-8 file without a byte order mark, like Steam does.
procedure WriteUtf8(const FileName, Text: String);
var
  Lines: TArrayOfString;
begin
  ForceDirectories(ExtractFilePath(FileName));
  SetArrayLength(Lines, 1);
  Lines[0] := Text;
  SaveStringsToUTF8FileWithoutBOM(FileName, Lines, False);
end;

procedure WriteEmptyFile(const FileName: String);
begin
  ForceDirectories(ExtractFilePath(FileName));
  SaveStringToFile(FileName, '', False);
end;

// The text of one path inside a VDF file: backslashes are doubled.
function VdfEscape(const S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '\', '\\', True);
end;

// ---- Path, URL, and text rules ----

procedure CheckPath(const Path: String; Expected: Boolean);
begin
  Expect(IsSafePath(Path) = Expected, 'path "' + Path + '" safe=' + IntToStr(Ord(Expected)));
end;

procedure TestRules;
begin
  CheckPath('D2RLoader.exe', True);
  CheckPath('d2rloader/config/d2rloader.toml', True);
  CheckPath('a', True);
  CheckPath('../D2R.exe', False);
  CheckPath('C:/Windows/x.dll', False);
  CheckPath('mods//a', False);
  CheckPath('mods\a', False);
  CheckPath('/mods', False);
  CheckPath('mods/', False);
  CheckPath('mods/a.', False);
  CheckPath('mods/a ', False);
  CheckPath('mods/./a', False);
  CheckPath('mods/../a', False);
  CheckPath('', False);

  Expect(TargetPath('G:\Game', 'd2rloader/config/a.toml') = 'G:\Game\d2rloader\config\a.toml', 'target path: slashes become backslashes');
  Expect(TargetPath('G:\Game\', 'a.txt') = 'G:\Game\a.txt', 'target path: no double backslash');
  Expect(Length(FolderKey('G:\Blizzard\Diablo II Resurrected')) = 12, 'folder key: 12 characters');
  Expect(FolderKey('G:\Blizzard\Diablo II Resurrected') = FolderKey('g:\blizzard\diablo ii resurrected\'), 'folder key: letter case and a last backslash do not matter');
  Expect(FolderKey('G:\Blizzard\Diablo II Resurrected') <> FolderKey('M:\SteamLibrary\steamapps\common\Diablo II Resurrected'), 'folder key: two folders have two keys');
  Expect(LeafName('a/b/c.txt') = 'c.txt', 'leaf name: last part of a path');
  Expect(LeafName('c.txt') = 'c.txt', 'leaf name: a single name');

  // The unit test build has no TEST_LOOPBACK, so only https is allowed.
  Expect(IsAllowedUrl('https://d2rloader.net/a'), 'url: https is allowed');
  Expect(IsAllowedUrl('HTTPS://d2rloader.net/a'), 'url: the scheme is not case sensitive');
  Expect(not IsAllowedUrl('http://d2rloader.net/a'), 'url: http is rejected');
  Expect(not IsAllowedUrl('http://127.0.0.1:8000/a'), 'url: http on the local computer is rejected in a normal build');
  Expect(not IsAllowedUrl('https:/d2rloader.net/a'), 'url: one slash is rejected');
  Expect(not IsAllowedUrl('ftp://d2rloader.net/a'), 'url: ftp is rejected');
  Expect(not IsAllowedUrl(''), 'url: empty is rejected');

  Expect(IsSha256Text('93021dad48533bcfca8a95c69a0cc00cdb9008a3ce6ceba1d04c7aca71985a10'), 'sha256: a real hash is accepted');
  Expect(not IsSha256Text('93021DAD48533BCFCA8A95C69A0CC00CDB9008A3CE6CEBA1D04C7ACA71985A10'), 'sha256: upper case is rejected');
  Expect(not IsSha256Text('93021dad'), 'sha256: a short text is rejected');
  Expect(not IsSha256Text(StringOfChar('g', 64)), 'sha256: non-hex is rejected');

  Expect(JsonDepth('{"a":[[1]]}') = 3, 'depth: counts brackets');
  Expect(JsonDepth('{"a":"[[[["}') = 1, 'depth: brackets inside a string do not count');
  Expect(JsonDepth('{"a":"\"[[[["}') = 1, 'depth: an escaped quote does not end the string');
  Expect(JsonDepth('') = 0, 'depth: empty text');
end;

// ---- Manifest ----

procedure TestManifestFixtures;
var
  Dir, Name, Text, Err: String;
  FindRec: TFindRec;
  M: TManifest;
  Count: Integer;
begin
  Dir := ExpandConstant('{src}') + '\..\tests\fixtures\manifests\';
  Count := 0;
  if FindFirst(Dir + '*.json', FindRec) then
  begin
    try
      repeat
        Name := FindRec.Name;
        if not ReadUtf8File(Dir + Name, Text) then
          Text := '';
        Err := ParseManifest(Text, M);
        if Copy(Name, 1, 3) = 'ok-' then
          Expect(Err = '', 'manifest ' + Name + ' is accepted ' + Err)
        else
          Expect(Err <> '', 'manifest ' + Name + ' is rejected');
        Count := Count + 1;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
  Expect(Count >= 80, 'manifest: found ' + IntToStr(Count) + ' fixture files');
end;

procedure TestManifestValues;
var
  Dir, Text, Err, Expected: String;
  M: TManifest;
begin
  Dir := ExpandConstant('{src}') + '\..\tests\fixtures\manifests\';

  ReadUtf8File(Dir + 'ok-real-1.3.1-beta.json', Text);
  Err := ParseManifest(Text, M);
  Expect(Err = '', 'values: the 1.3.1-beta manifest is accepted');
  Expect(M.Version = '1.3.1-beta', 'values: version');
  Expect(GetArrayLength(M.Files) = 4, 'values: 4 files');
  Expect(GetArrayLength(M.Folders) = 5, 'values: 5 folders');
  if GetArrayLength(M.Files) = 4 then
  begin
    Expect(M.Files[0].Path = 'D2RLoader.exe', 'values: first path');
    Expect(M.Files[0].Size = 23331160, 'values: first size');
    Expect(M.Files[0].Sha256 = '93021dad48533bcfca8a95c69a0cc00cdb9008a3ce6ceba1d04c7aca71985a10', 'values: first hash');
    Expect(not M.Files[0].OnlyIfMissing, 'values: onlyIfMissing is false by default');
    Expect(M.Files[3].OnlyIfMissing, 'values: onlyIfMissing is true for the toml');
    Expect(M.Files[3].Path = 'd2rloader/config/d2rloader.toml', 'values: last path');
  end;

  ReadUtf8File(Dir + 'ok-unicode-path.json', Text);
  Err := ParseManifest(Text, M);
  Expected := 'mods/' + Chr($00DC) + 'n' + Chr($00EF) + '/' + Chr($0411) + '.txt';
  Expect((Err = '') and (GetArrayLength(M.Files) = 1), 'values: the unicode manifest is accepted');
  if GetArrayLength(M.Files) = 1 then
    Expect(M.Files[0].Path = Expected, 'values: \u escapes in a path are decoded');

  ReadUtf8File(Dir + 'ok-size-four-gib.json', Text);
  Err := ParseManifest(Text, M);
  Expect((Err = '') and (GetArrayLength(M.Files) = 1), 'values: a 4 GiB size is accepted');
  if GetArrayLength(M.Files) = 1 then
    Expect(M.Files[0].Size = 4294967296, 'values: a 4 GiB size is exact');
end;

procedure TestManifestEdges;
var
  Dir, Text, Err: String;
  M: TManifest;
  Lines: TArrayOfString;
begin
  Dir := ExpandConstant('{src}') + '\..\tests\fixtures\manifests\';

  // A manifest larger than the limit is rejected before it is parsed.
  Text := '{"schema": 1, "pad": "' + StringOfChar('a', ManifestMaxChars) + '"}';
  Err := ParseManifest(Text, M);
  Expect(Err <> '', 'edges: a manifest over the size limit is rejected');

  // A byte order mark at the start of the file is ignored.
  ReadUtf8File(Dir + 'ok-minimal.json', Text);
  SetArrayLength(Lines, 1);
  Lines[0] := Text;
  SaveStringsToUTF8File(ExpandConstant('{src}') + '\unit-bom.json', Lines, False);
  Expect(ReadUtf8File(ExpandConstant('{src}') + '\unit-bom.json', Text), 'edges: a file with a byte order mark is read');
  Expect(CharAt(Text, 1) = '{', 'edges: the byte order mark is removed');
  Expect(ParseManifest(Text, M) = '', 'edges: a manifest with a byte order mark is accepted');
  DeleteFile(ExpandConstant('{src}') + '\unit-bom.json');

  // A file that does not exist is not an exception.
  Expect(not ReadUtf8File(Dir + 'does-not-exist.json', Text), 'edges: a missing file gives False');
end;

// ---- The list of installs ----

// Makes one uninstall folder. With Exe=False the folder has no uninstaller.
procedure MakeInstallFolder(const Base, Name, InfoText: String; Exe, Info: Boolean);
var
  Dir: String;
begin
  Dir := Base + '\' + Name;
  ForceDirectories(Dir);
  if Exe then
    WriteEmptyFile(Dir + '\' + UninstallerFile);
  if Info then
    SaveStringToFile(Dir + '\' + InstallInfoFile, InfoText, False);
end;

procedure TestInstallList;
var
  Base: String;
  Items: TInstallInfos;
  Info: TInstallInfo;
begin
  Base := ExpandConstant('{src}') + '\unit-installs';
  DelTree(Base, True, True, True);
  ForceDirectories(Base);

  // Written in an odd order, to test the sort: Custom, Steam, Battle.net, Custom with another path.
  MakeInstallFolder(Base, 'a1', 'Custom' + #13#10 + 'Z:\Games\D2R custom' + #13#10, True, True);
  MakeInstallFolder(Base, 'b2', 'Steam' + #10 + 'M:\SteamLibrary\steamapps\common\Diablo II Resurrected', True, True);
  MakeInstallFolder(Base, 'c3', 'Battle.net' + #13#10 + 'G:\Blizzard\Diablo II Resurrected' + #13#10 + 'extra line', True, True);
  MakeInstallFolder(Base, 'd4', 'Custom' + #13#10 + 'A:\Another', True, True);
  // These four must be ignored.
  MakeInstallFolder(Base, 'e5-no-info', '', True, False);
  MakeInstallFolder(Base, 'f6-no-exe', 'Steam' + #13#10 + 'M:\x', False, True);
  MakeInstallFolder(Base, 'g7-bad-kind', 'Epic' + #13#10 + 'M:\x', True, True);
  MakeInstallFolder(Base, 'h8-one-line', 'Steam', True, True);
  MakeInstallFolder(Base, 'i9-empty-path', 'Steam' + #13#10 + #13#10, True, True);
  WriteEmptyFile(Base + '\not-a-folder.txt');

  FindInstalls(Base, Items);
  Expect(GetArrayLength(Items) = 4, 'installs: 4 installs found, 5 broken folders ignored');
  if GetArrayLength(Items) = 4 then
  begin
    Expect(Items[0].Kind = KindBattleNet, 'installs: Battle.net is first');
    Expect(Items[0].GameDir = 'G:\Blizzard\Diablo II Resurrected', 'installs: the game folder is the second line (CRLF)');
    Expect(Items[1].Kind = KindSteam, 'installs: Steam is second');
    Expect(Items[1].GameDir = 'M:\SteamLibrary\steamapps\common\Diablo II Resurrected', 'installs: LF line ends work, and no last line end is needed');
    Expect((Items[2].Kind = KindCustom) and (Items[2].GameDir = 'A:\Another'), 'installs: custom installs come last, sorted by folder (1)');
    Expect((Items[3].Kind = KindCustom) and (Items[3].GameDir = 'Z:\Games\D2R custom'), 'installs: custom installs come last, sorted by folder (2)');
    Expect(Items[0].UninstallDir = Base + '\c3', 'installs: the uninstall folder is kept');
  end;

  Expect(not ReadInstallInfo(Base + '\no-such-folder', Info), 'installs: a folder that does not exist gives False');
  FindInstalls(Base + '\no-such-folder', Items);
  Expect(GetArrayLength(Items) = 0, 'installs: a base folder that does not exist gives no installs');

  WriteInstallInfo(Base + '\w', KindSteam, 'M:\Game with ' + Chr($0411) + Chr(233));
  WriteEmptyFile(Base + '\w\' + UninstallerFile);
  Expect(ReadInstallInfo(Base + '\w', Info) and (Info.GameDir = 'M:\Game with ' + Chr($0411) + Chr(233)) and (Info.Kind = KindSteam),
    'installs: WriteInstallInfo and ReadInstallInfo agree, also with non-ASCII letters');

  Expect(InstallKindText(KindCustom) = 'Other folder', 'installs: the text of a custom install');
  Expect(InstallKindText(KindSteam) = 'Steam', 'installs: the text of a Steam install');
  DelTree(Base, True, True, True);
end;

// ---- Steam files (VDF) ----

procedure TestVdfParser;
var
  Tokens, Keys, Values: TArrayOfString;
  Text: String;
begin
  Text := '// comment' + #10 + '"root" { "path" "C:\\a\\b \"q\"" "n" "x\ty" "inner" { "installdir" "Game" } }';
  VdfTokens(Text, Tokens);
  VdfPairs(Tokens, Keys, Values);
  Expect(GetArrayLength(Keys) = 3, 'vdf: 3 pairs found');
  Expect(Values[0] = 'C:\a\b "q"', 'vdf: backslash and quote escapes');
  Expect(Values[1] = 'x' + #9 + 'y', 'vdf: tab escape');
  Expect(Keys[2] = 'installdir', 'vdf: pair inside a section');

  // Broken text must not hang or fail.
  VdfTokens('"abc', Tokens);
  VdfPairs(Tokens, Keys, Values);
  Expect(GetArrayLength(Keys) = 0, 'vdf: an unterminated string gives no pair');
  VdfTokens('', Tokens);
  VdfPairs(Tokens, Keys, Values);
  Expect(GetArrayLength(Keys) = 0, 'vdf: empty text gives no pair');
  VdfTokens('"a" { { } } "b" "c" }', Tokens);
  VdfPairs(Tokens, Keys, Values);
  Expect((GetArrayLength(Keys) = 1) and (Keys[0] = 'b'), 'vdf: stray braces are skipped');
  VdfTokens('"key"', Tokens);
  VdfPairs(Tokens, Keys, Values);
  Expect(GetArrayLength(Keys) = 0, 'vdf: a key without a value gives no pair');
end;

// One numbered library in libraryfolders.vdf. AppId '' means no "apps" list.
// ISPP treats a line that starts with # as a directive, so no line here starts with #9.
function LibraryEntry(const Index, Path, AppId: String): String;
var
  T: String;
begin
  T := #9;
  Result := T + '"' + Index + '"' + #10 + T + '{' + #10 +
    T + T + '"path"' + T + T + '"' + VdfEscape(Path) + '"' + #10;
  if AppId <> '' then
  begin
    Result := Result + T + T + '"apps"' + #10 + T + T + '{' + #10 +
      T + T + T + '"' + AppId + '"' + T + T + '"456"' + #10 + T + T + '}' + #10;
  end;
  Result := Result + T + '}' + #10;
end;

function AppManifest(const InstallDir: String): String;
var
  T: String;
begin
  T := #9;
  Result := '"AppState"' + #10 + '{' + #10 +
    T + '"appid"' + T + T + '"' + SteamAppId + '"' + #10 +
    T + '"installdir"' + T + T + '"' + VdfEscape(InstallDir) + '"' + #10 +
    '}' + #10;
end;

// Builds a fake Steam folder with four libraries and runs the lookup on it.
procedure TestFakeSteam;
var
  Base, SteamRoot, LibB, LibC, LibD, GoodDir, Vdf: String;
  Libraries, Dirs: TArrayOfString;
begin
  Base := ExpandConstant('{src}') + '\unit-fake-steam';
  DelTree(Base, True, True, True);
  SteamRoot := Base + '\Steam';
  // Folder names with letters outside ASCII: a Cyrillic B and an e with an accent.
  LibB := Base + '\Lib' + Chr($0411) + Chr(233);
  LibC := Base + '\LibC';
  LibD := Base + '\LibD';
  GoodDir := LibB + '\steamapps\common\Diablo II Resurrected Fake';

  // Library 0 is the Steam folder. Library 4 repeats library 1 in lower case.
  Vdf := '"libraryfolders"' + #10 + '{' + #10 +
    LibraryEntry('0', SteamRoot, '228980') +
    LibraryEntry('1', LibB, SteamAppId) +
    LibraryEntry('2', LibC, '') +
    LibraryEntry('3', LibD, '') +
    LibraryEntry('4', Lowercase(LibB), '') +
    '}' + #10;
  WriteUtf8(SteamRoot + '\steamapps\libraryfolders.vdf', Vdf);

  // LibB: a good install.
  WriteUtf8(LibB + '\steamapps\appmanifest_' + SteamAppId + '.acf', AppManifest('Diablo II Resurrected Fake'));
  WriteEmptyFile(GoodDir + '\' + GameExe);

  // LibC: installdir tries to leave steamapps\common. The target has a D2R.exe, so only the name check stops it.
  WriteUtf8(LibC + '\steamapps\appmanifest_' + SteamAppId + '.acf', AppManifest('..\Evil'));
  WriteEmptyFile(LibC + '\steamapps\Evil\' + GameExe);

  // LibD: the manifest is fine, but the folder has no D2R.exe.
  WriteUtf8(LibD + '\steamapps\appmanifest_' + SteamAppId + '.acf', AppManifest('NoExe'));
  ForceDirectories(LibD + '\steamapps\common\NoExe');

  SteamLibraries(SteamRoot, Libraries);
  Expect(GetArrayLength(Libraries) = 4, 'fake steam: 4 libraries, the lower-case duplicate is dropped');
  FindSteamFolders(SteamRoot, Dirs);
  Expect(GetArrayLength(Dirs) = 1, 'fake steam: exactly one game folder');
  if GetArrayLength(Dirs) = 1 then
    Expect(Dirs[0] = GoodDir, 'fake steam: the folder with non-ASCII letters is found and spelled correctly');

  // A Steam folder with no libraryfolders.vdf has only itself as a library.
  SteamLibraries(Base + '\NoSuchSteam', Libraries);
  Expect(GetArrayLength(Libraries) = 1, 'fake steam: a missing libraryfolders.vdf gives one library');

  DelTree(Base, True, True, True);
end;

// ---- Running program ----

// Ends the program that runs from exactly this path. Test cleanup only: it never touches another copy.
procedure KillProcessAtPath(const ExeName, FullPath: String);
var
  Locator, Wmi, Items, Item, ExePath: Variant;
  I: Integer;
  S: String;
begin
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Wmi := Locator.ConnectServer('.', 'root\CIMV2');
    Items := Wmi.ExecQuery('SELECT ProcessId, ExecutablePath FROM Win32_Process WHERE Name = ''' + ExeName + '''');
    for I := 0 to Items.Count - 1 do
    begin
      Item := Items.ItemIndex(I);
      ExePath := Item.ExecutablePath;
      if not VarIsNull(ExePath) then
      begin
        S := ExePath;
        if SameFilePath(S, FullPath) then
          Item.Terminate();
      end;
    end;
  except
    Report.Add('FAIL cleanup could not end the test program');
  end;
end;

// Uses a renamed copy of ping.exe as a stand-in for D2RLoader.exe. It lives in a test folder and ends by itself after 30 pings.
procedure TestProcessCheck;
var
  Paths: TArrayOfString;
  FakeDir, OtherDir, FakeExe: String;
  Running, Known: Boolean;
  ResultCode: Integer;
begin
  Expect(FindProcessPaths('svchost.exe', Paths), 'process: WMI can be used');
  Expect(GetArrayLength(Paths) > 0, 'process: svchost.exe is found');
  FindProcessPaths('D2RLoaderNotARealName.exe', Paths);
  Expect(GetArrayLength(Paths) = 0, 'process: a name that does not run is not found');

  FakeDir := ExpandConstant('{src}') + '\unit-fake-game';
  OtherDir := ExpandConstant('{src}') + '\unit-other-game';
  DelTree(FakeDir, True, True, True);
  ForceDirectories(FakeDir);
  FakeExe := FakeDir + '\' + LoaderExe;
  Expect(CopyFile(ExpandConstant('{sys}\ping.exe'), FakeExe, False), 'process: stand-in copied');

  Known := IsLoaderRunning(FakeDir, Running);
  Expect(Known and (not Running), 'process: before the start, D2RLoader.exe is not running');
  Exec(FakeExe, '-n 30 127.0.0.1', '', SW_HIDE, ewNoWait, ResultCode);
  Sleep(1000);
  Known := IsLoaderRunning(FakeDir, Running);
  Expect(Known and Running, 'process: D2RLoader.exe is found in its own folder');
  Known := IsLoaderRunning(OtherDir, Running);
  Expect(Known and (not Running), 'process: D2RLoader.exe in another folder does not count');

  KillProcessAtPath(LoaderExe, FakeExe);
  Sleep(1000);
  Known := IsLoaderRunning(FakeDir, Running);
  Expect(Known and (not Running), 'process: after it ends, D2RLoader.exe is not running');
  DelTree(FakeDir, True, True, True);
end;

// ---- This computer ----

// Reports what the real lookup finds on this computer.
procedure TestRealMachine;
var
  Dir, Root: String;
  Libraries, Dirs: TArrayOfString;
  I: Integer;
  Running, Known: Boolean;
begin
  if FindBattleNetFolder(Dir) then
  begin
    Report.Add('real: Battle.net folder = ' + Dir);
    Known := IsLoaderRunning(Dir, Running);
    Report.Add('real: D2RLoader.exe check known=' + IntToStr(Ord(Known)) + ' running=' + IntToStr(Ord(Running)));
  end
  else
    Report.Add('real: Battle.net folder = (none)');

  if not FindSteamRoot(Root) then
  begin
    Report.Add('real: Steam folder = (none)');
    Exit;
  end;

  Report.Add('real: Steam folder = ' + Root);
  SteamLibraries(Root, Libraries);
  for I := 0 to GetArrayLength(Libraries) - 1 do
    Report.Add('real: Steam library ' + IntToStr(I) + ' = ' + Libraries[I]);

  FindSteamFolders(Root, Dirs);
  Report.Add('real: Steam game folders found = ' + IntToStr(GetArrayLength(Dirs)));
  for I := 0 to GetArrayLength(Dirs) - 1 do
    Report.Add('real: Steam game folder = ' + Dirs[I]);
end;

function InitializeSetup(): Boolean;
begin
  Result := False; // This is a test. Exit after it runs.
  Report := TStringList.Create;
  try
    Report.Add('Installer unit tests');
    TestRules;
    TestManifestFixtures;
    TestManifestValues;
    TestManifestEdges;
    TestInstallList;
    TestVdfParser;
    TestFakeSteam;
    TestProcessCheck;
    TestRealMachine;
    Report.Add('DONE');
  finally
    Report.SaveToFile(ExpandConstant('{src}') + '\unit-report.txt');
    Report.Free;
  end;
end;
