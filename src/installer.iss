; D2RLoader installer.
; It finds the Diablo II: Resurrected folder, downloads the files named in the manifest,
; checks each file, and copies the files into the game folder. Run it again to update.
; See docs\manifest.md for the manifest. Build: ISCC src\installer.iss

#define InstallerVersion "0.1.0"

#ifndef OutputName
  #define OutputName "D2RLoader-Installer"
#endif

#ifndef ManifestUrl
  #define ManifestUrl "https://d2rloader.net/download/manifest.json"
#endif

; A test build has its own AppId, so a test never changes the uninstall entry of a real install.
#ifdef TEST_LOOPBACK
  #define AppGuid "{{7A3C0D52-5E2B-4B4C-9E7A-3F7B1B9C0001}"
#else
  #define AppGuid "{{FADB1B46-0498-4B31-8199-0FCFED3E19FC}"
#endif

[Setup]
AppId={#AppGuid}
AppName=D2RLoader
AppVersion={#InstallerVersion}
AppPublisher=D2RLoader
AppPublisherURL=https://d2rloader.net
DefaultDirName={code:DefaultGameDir}
AppendDefaultDirName=no
DirExistsWarning=no
UsePreviousAppDir=no
DisableWelcomePage=no
DisableProgramGroupPage=yes
; Setup copies the files with the [Files] section, so its uninstall record lists every file that it installs.
; The record and the uninstaller are kept outside the game folder, in one folder for each game folder.
#ifdef TEST_LOOPBACK
; A test never changes the list of installed programs.
CreateUninstallRegKey=no
#endif
UninstallDisplayName=D2RLoader
UninstallDisplayIcon={app}\D2RLoader.exe
UninstallFilesDir={code:UninstallDir}
; We ask the user to close the game ourselves (CheckGameClosed).
CloseApplications=no
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline
; "classic" has a white header and a grey page, with a line between them, like most installers.
; "modern" makes the whole page white.
ShowLanguageDialog=auto
WizardStyle=classic
; The pictures come from assets\make-art.py. They are the D2RLoader logo and are not under the GPL
; (see assets\NOTICE.md). A fork can build without them: delete the folder assets\generated, or give /DNO_ART.
; Then Setup uses the standard Inno Setup pictures. Each list goes from 100% to 250% screen scale.
#ifndef NO_ART
#if FileExists(SourcePath + "..\assets\generated\wizard-164x314.png")
SetupIconFile=..\assets\generated\d2rloader.ico
WizardImageFile=..\assets\generated\wizard-164x314.png,..\assets\generated\wizard-192x386.png,..\assets\generated\wizard-246x459.png,..\assets\generated\wizard-273x556.png,..\assets\generated\wizard-328x604.png,..\assets\generated\wizard-355x700.png
WizardSmallImageFile=..\assets\generated\small-55x55.png,..\assets\generated\small-64x68.png,..\assets\generated\small-83x80.png,..\assets\generated\small-92x97.png,..\assets\generated\small-110x106.png,..\assets\generated\small-138x140.png
#endif
#endif
OutputDir=..\out
OutputBaseFilename={#OutputName}
; The details that Windows shows for the file (Properties, Details). Setup and the uninstaller both have them.
VersionInfoVersion={#InstallerVersion}
VersionInfoCompany=D2RLoader
VersionInfoProductName=D2RLoader
VersionInfoDescription=D2RLoader Setup
; tools\build.py gives /DSIGN and defines the sign tool "d2rloader". Then Inno Setup signs Setup and the uninstaller.
; A signed uninstaller keeps its texts in a separate file (unins000.msg) next to it.
#ifdef SIGN
SignTool=d2rloader
#endif

; The code downloads and checks every file first. Then it puts the checked files in {tmp}\payload and {tmp}\settings.
; Setup copies them to the game folder and records each one for the uninstaller.
[Files]
Source: "{tmp}\payload\*"; DestDir: "{app}"; Flags: external recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist
; A settings file is never replaced and never removed by the uninstaller.
Source: "{tmp}\settings\*"; DestDir: "{app}"; Flags: external recursesubdirs createallsubdirs onlyifdoesntexist uninsneveruninstall skipifsourcedoesntexist
; The small logo for the window of the uninstaller. It goes next to the uninstaller, and the uninstaller removes it.
#ifndef NO_ART
#if FileExists(SourcePath + "..\assets\generated\small-110x106.png")
Source: "..\assets\generated\small-110x106.png"; DestDir: "{code:UninstallDir}"; DestName: "logo.png"; Flags: ignoreversion
#endif
#endif

; Setup asks if the user wants shortcuts. The Start menu shortcut is on by default and the desktop shortcut is off.
; A shortcut starts D2RLoader.exe in the game folder. The uninstaller removes the shortcuts.
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "{cm:StartMenuIcon}"; GroupDescription: "{cm:AdditionalIcons}"

; The languages of Diablo II: Resurrected (the list "LocaleExpectation" in D2RCore). Inno Setup has no separate Mexican
; Spanish, so Spanish serves both. Each language has two files: the one of Inno Setup for the standard texts, and ours.
; The pages use the usual Inno Setup wording. Our file changes a few texts, and has the new ones (see languages\english.isl).
; Setup picks the language of Windows. It asks only if Windows has a language that we do not have.
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl,languages\english.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl,languages\german.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl,languages\spanish.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl,languages\french.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl,languages\italian.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl,languages\japanese.isl"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl,languages\korean.isl"
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl,languages\polish.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl,languages\brazilianportuguese.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl,languages\russian.isl"
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl,languages\chinesesimplified.isl"
Name: "chinesetraditional"; MessagesFile: "compiler:Languages\ChineseTraditional.isl,languages\chinesetraditional.isl"

[Icons]
Name: "{code:ShortcutFolder|Start}\{code:ShortcutName}"; Filename: "{app}\D2RLoader.exe"; WorkingDir: "{app}"; Tasks: startmenuicon
Name: "{code:ShortcutFolder|Desktop}\{code:ShortcutName}"; Filename: "{app}\D2RLoader.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Code]
#include "third_party\JsonParser.pas"
#include "gamefolder.pas"
#include "processcheck.pas"
#include "manifest.pas"
#include "installs.pas"
#include "tiles.pas"
#include "dialog.pas"

var
  CandidatesReady: Boolean;
  CandidateDirs, CandidateKinds: TArrayOfString;
  MaintenancePage: TWizardPage;  // "Update or Uninstall". Shown only if D2RLoader is installed already.
  UpdateRadio, UninstallRadio: TNewRadioButton;
  ExistingInstalls: TInstallInfos;  // The installs that Setup found when it started.
  ClosingForUninstall: Boolean;
  TilePage: TWizardPage;
  TileChoice: Integer;  // The index of the found folder that the player chose, or -1 for "Other folder".
  DownloadPage: TDownloadWizardPage;
  ManifestData: TManifest;
  NeedFile: array of Boolean;
  TempNames: TArrayOfString;
  ResultText: String;
  CountInstalled, CountSame, CountKept: Integer;

// ---- Game folder ----

// Has Setup found an install of D2RLoader in this game folder when it started?
function IsAlreadyInstalled(const Dir: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 0 to GetArrayLength(ExistingInstalls) - 1 do
  begin
    if SameFilePath(ExistingInstalls[I].GameDir, Dir) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

procedure AddCandidate(const Kind, Dir: String);
var
  Clean: String;
begin
  // The page shows the folder. Show it the way Windows does, with backslashes.
  Clean := Dir;
  StringChangeEx(Clean, '/', '\', True);
  AddString(CandidateDirs, Clean);
  AddString(CandidateKinds, Kind);
end;

#ifdef TEST_LOOPBACK
// A test build gets its game folders from /FakeBattleNet= and /FakeSteam=. It never reads the real registry.
procedure FindFakeCandidates;
var
  Dir: String;
begin
  Dir := ExpandConstant('{param:FakeBattleNet|}');
  if IsGameFolder(Dir) then
    AddCandidate(KindBattleNet, Dir);

  Dir := ExpandConstant('{param:FakeSteam|}');
  if IsGameFolder(Dir) then
    AddCandidate(KindSteam, Dir);
end;
#endif

// The game folders that Battle.net and Steam know about. Runs once.
procedure FindCandidates;
var
  Dir, Root: String;
  SteamDirs: TArrayOfString;
  I: Integer;
begin
  if CandidatesReady then
    Exit;

  CandidatesReady := True;
#ifdef TEST_LOOPBACK
  // A test build never looks at the real registry. A mistake in a test cannot reach a real game folder.
  FindFakeCandidates;
  Exit;
#endif
  if FindBattleNetFolder(Dir) then
    AddCandidate(KindBattleNet, Dir);

  if not FindSteamRoot(Root) then
    Exit;

  FindSteamFolders(Root, SteamDirs);
  for I := 0 to GetArrayLength(SteamDirs) - 1 do
  begin
    if not ListHasText(CandidateDirs, SteamDirs[I]) then
      AddCandidate(KindSteam, SteamDirs[I]);
  end;
end;

// Is this folder a Battle.net folder, a Steam folder, or a folder that the user chose?
function KindOfFolder(const Dir: String): String;
var
  I: Integer;
begin
  Result := KindCustom;
  for I := 0 to GetArrayLength(CandidateDirs) - 1 do
  begin
    if SameFilePath(CandidateDirs[I], Dir) then
    begin
      Result := CandidateKinds[I];
      Exit;
    end;
  end;
end;

function DefaultGameDir(Param: String): String;
begin
  FindCandidates;
  if GetArrayLength(CandidateDirs) > 0 then
    Result := CandidateDirs[0]
  else
    Result := ExpandConstant('{commonpf32}') + '\Diablo II Resurrected';
#ifdef TEST_LOOPBACK
  // Without a fake folder, use a folder that does not exist. A test that forgets /DIR= stops at the D2R.exe check.
  if GetArrayLength(CandidateDirs) = 0 then
    Result := 'C:\d2rl-test-build-needs-a-DIR-option';
#endif
end;

// Did the user give the folder on the command line (/DIR=...)?
function HasDirParam: Boolean;
begin
  Result := ExpandConstant('{param:DIR|}') <> '';
end;

// Did the user pick one of the found folders (and not "Other folder")?
function CandidateChosen: Boolean;
begin
  Result := (TileChoice >= 0) and (TileChoice < GetArrayLength(CandidateDirs));
end;

// Setup clicks through the pages of a silent run too, so NextButtonClick runs there.
// A silent run, or a run with /DIR=, must keep the folder that it was given or that is the default.
function ChoiceIsHidden: Boolean;
begin
  Result := (GetArrayLength(CandidateDirs) = 0) or WizardSilent or HasDirParam;
end;

// ---- Steps before the copy ----

function ManifestUrlText: String;
begin
  Result := '{#ManifestUrl}';
#ifdef TEST_LOOPBACK
  Result := ExpandConstant('{param:Manifest|' + Result + '}');
#endif
end;

var
  DownloadRunning, DownloadCancelled: Boolean;

// Setup calls this many times while it downloads. The page has its own "Stop download" button, which other
// installers do not have. It is hidden, and the Cancel button in the corner stops the download (see CancelButtonClick).
function DownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if not WizardSilent then
    DownloadPage.AbortButton.Visible := False;
  Result := not DownloadCancelled;
end;

// The player clicked Cancel (or the close button of the window).
// During a download, ask the usual question, and stop the download if the answer is yes.
// After that, PrepareToInstall closes the window, and Setup ends without a second question.
procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if ClosingForUninstall or DownloadCancelled then
    Confirm := False
  else if DownloadRunning then
  begin
    Cancel := False;
    if ExitSetupMsgBox then
      DownloadCancelled := True;
  end;
end;

// Downloads what is in the download list. Returns '' or a message.
function RunDownloads: String;
begin
  Result := '';
  if not WizardSilent then
  begin
    DownloadPage.Show;
    DownloadPage.AbortButton.Visible := False;
    WizardForm.CancelButton.Visible := True;
    WizardForm.CancelButton.Enabled := True;
  end;
  DownloadRunning := True;
  try
    try
      DownloadPage.Download;
    except
      if DownloadCancelled or DownloadPage.AbortedByUser then
        Result := CustomMessage('DownloadStopped')
      else
        Result := CustomMessage('DownloadFailed') + #13#10 + #13#10 +
          CustomMessage('Details') + ' ' + DownloadPage.LastBaseNameOrUrl + ': ' + GetExceptionMessage;
    end;
  finally
    DownloadRunning := False;
    if not WizardSilent then
      DownloadPage.Hide;
  end;
end;

function CheckGameFolder(const Dir: String): String;
begin
  Result := '';
  if not IsGameFolder(Dir) then
    Result := CustomMessage('GameNotFound') + #13#10 + Dir + #13#10 + #13#10 +
      FmtMessage(CustomMessage('ChooseGameFolder'), [GameExe]);
end;

// D2RLoader.exe locks the files that Setup replaces. Ask the user to close it.
// A silent run cannot ask, so it stops.
function CheckGameClosed(const Dir: String): String;
var
  Running, Known: Boolean;
begin
  Result := '';
  while True do
  begin
    Known := IsLoaderRunning(Dir, Running);
    if Known and (not Running) then
      Exit;

    if Known then
    begin
      Log('D2RL: ' + LoaderExe + ' is running in ' + Dir);
      if SuppressibleMsgBox(CustomMessage('GameOpenRetry'), mbError, MB_RETRYCANCEL, IDCANCEL) <> IDRETRY then
      begin
        Result := CustomMessage('GameStillOpen');
        Exit;
      end;
    end
    else
    begin
      Log('D2RL: Setup cannot tell if ' + LoaderExe + ' is running');
      if SuppressibleMsgBox(CustomMessage('GameCheckFailedAsk'), mbConfirmation, MB_YESNO, IDNO) = IDYES then
        Exit;

      Result := CustomMessage('CloseGameThenRun');
      Exit;
    end;
  end;
end;

function LoadManifest: String;
var
  Url, Text: String;
begin
  Url := ManifestUrlText;
  if not IsAllowedUrl(Url) then
  begin
    Result := 'The website address is not safe. It must start with https://';
    Exit;
  end;

  DownloadPage.Clear;
  DownloadPage.Add(Url, 'manifest.json', '');
  Result := RunDownloads;
  if Result <> '' then
    Exit;

  if not ReadUtf8File(ExpandConstant('{tmp}\manifest.json'), Text) then
  begin
    Result := CustomMessage('ManifestUnreadable');
    Exit;
  end;

  Result := ParseManifest(Text, ManifestData);
  if Result <> '' then
    Result := CustomMessage('ManifestInvalid') + #13#10 + #13#10 + CustomMessage('Details') + ' ' + Result;
end;

// A file needs an install if it is missing or different. A file with onlyIfMissing is never replaced.
procedure PlanFiles(const Dir: String);
var
  I: Integer;
  Target, Why: String;
  Needed: Boolean;
begin
  CountInstalled := 0;
  CountSame := 0;
  CountKept := 0;
  SetArrayLength(NeedFile, GetArrayLength(ManifestData.Files));
  for I := 0 to GetArrayLength(ManifestData.Files) - 1 do
  begin
    Target := TargetPath(Dir, ManifestData.Files[I].Path);
    Needed := True;
    Why := 'missing';
    if FileExists(Target) then
    begin
      Why := 'different';
      try
        if SameText(GetSHA256OfFile(Target), ManifestData.Files[I].Sha256) then
        begin
          Needed := False;
          Why := 'up to date';
        end;
      except
        Why := 'unreadable';
      end;

      // A settings file is never replaced. If the user changed it, say so on the last page.
      if ManifestData.Files[I].OnlyIfMissing then
      begin
        Needed := False;
        if Why = 'up to date' then
          CountSame := CountSame + 1
        else
        begin
          CountKept := CountKept + 1;
          Why := 'kept (onlyIfMissing)';
        end;
      end
      else if not Needed then
        CountSame := CountSame + 1;
    end;

    if Needed then
      CountInstalled := CountInstalled + 1;
    NeedFile[I] := Needed;
    Log('D2RL: ' + ManifestData.Files[I].Path + ' is ' + Why);
  end;
end;

// Does a file before this one already use the temporary name of this file?
function TempNameTaken(Index: Integer): Boolean;
var
  J: Integer;
begin
  Result := False;
  for J := 0 to Index - 1 do
  begin
    if NeedFile[J] and SameText(TempNames[J], TempNames[Index]) then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

// Downloads the files that are needed, and checks the size of each. The hash is checked by the download.
function DownloadFiles: String;
var
  I, Count: Integer;
  Size: Int64;
  TempFile: String;
begin
  Result := '';
  SetArrayLength(TempNames, GetArrayLength(ManifestData.Files));
  DownloadPage.Clear;
  Count := 0;
  for I := 0 to GetArrayLength(ManifestData.Files) - 1 do
  begin
    if NeedFile[I] then
    begin
      // The download page shows this name. Two files in different folders can have the same name.
      // Then the second one gets an underscore in front, so the temporary files never clash.
      TempNames[I] := LeafName(ManifestData.Files[I].Path);
      while TempNameTaken(I) do
        TempNames[I] := '_' + TempNames[I];
      DownloadPage.Add(ManifestData.Files[I].Url, TempNames[I], ManifestData.Files[I].Sha256);
      Count := Count + 1;
    end;
  end;

  if Count = 0 then
    Exit;

  Result := RunDownloads;
  if Result <> '' then
    Exit;

  for I := 0 to GetArrayLength(ManifestData.Files) - 1 do
  begin
    if NeedFile[I] then
    begin
      TempFile := ExpandConstant('{tmp}\') + TempNames[I];
      if not FileSize64(TempFile, Size) then
        Size := -1;

      if Size <> ManifestData.Files[I].Size then
      begin
        Result := CustomMessage('FileNotCorrect') + #13#10 + #13#10 +
          CustomMessage('Details') + ' ' + ManifestData.Files[I].Path + ' has the wrong size. The list says ' + IntToStr(ManifestData.Files[I].Size) + ' bytes.';
        Exit;
      end;
    end;
  end;
end;

function StageFiles(const Dir: String): String; forward;
procedure MakeResultText(const Dir: String); forward;

// Runs before anything is copied. A message stops Setup. Nothing is written to the game folder here.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Dir: String;
begin
  Dir := RemoveBackslashUnlessRoot(WizardDirValue);
  Log('D2RL: game folder ' + Dir);

  Result := CheckGameFolder(Dir);
  if Result <> '' then
  begin
    Log('D2RL: ' + Result);
    Exit;
  end;

  Result := CheckGameClosed(Dir);
  if Result <> '' then
  begin
    Log('D2RL: ' + Result);
    Exit;
  end;

  Result := LoadManifest;
  if Result = '' then
  begin
    PlanFiles(Dir);
    Result := DownloadFiles;
  end;
  if (Result = '') and (not DownloadCancelled) then
    Result := StageFiles(Dir);

  if DownloadCancelled then
  begin
    // The player cancelled. Nothing was copied. Close the window the same way as the Cancel button does.
    Log('D2RL: the player cancelled the download');
    WizardForm.Close;
    Result := CustomMessage('DownloadStopped');
    Exit;
  end;

  if Result <> '' then
  begin
    Log('D2RL: ' + Result);
    Exit;
  end;

  MakeResultText(Dir);
end;

// ---- The copy ----

// Puts the checked files where the [Files] section looks: {tmp}\payload for the files that Setup installs,
// {tmp}\settings for a settings file that does not exist yet. Setup records every file that it installs for the
// uninstaller. So a file that is already up to date is copied here too. Setup installs it again with the same
// content. Without this, the uninstaller would not know a file that the user unpacked from the zip by hand.
// The folders from the manifest are made here too (Setup creates all subfolders). The uninstaller removes
// them if they are empty.
function StageFiles(const Dir: String): String;
var
  I: Integer;
  Root, Staged, Source: String;
  Wanted: Boolean;
begin
  Result := '';
  DelTree(ExpandConstant('{tmp}\payload'), True, True, True);
  DelTree(ExpandConstant('{tmp}\settings'), True, True, True);
  ForceDirectories(ExpandConstant('{tmp}\payload'));
  for I := 0 to GetArrayLength(ManifestData.Folders) - 1 do
    ForceDirectories(TargetPath(ExpandConstant('{tmp}\payload'), ManifestData.Folders[I]));

  for I := 0 to GetArrayLength(ManifestData.Files) - 1 do
  begin
    // A settings file that exists is never replaced, and the uninstaller never removes it.
    Wanted := NeedFile[I] or (not ManifestData.Files[I].OnlyIfMissing);
    if Wanted then
    begin
      Root := ExpandConstant('{tmp}\payload');
      if ManifestData.Files[I].OnlyIfMissing then
        Root := ExpandConstant('{tmp}\settings');

      if NeedFile[I] then
        Source := ExpandConstant('{tmp}\') + TempNames[I]
      else
        Source := TargetPath(Dir, ManifestData.Files[I].Path);

      Staged := TargetPath(Root, ManifestData.Files[I].Path);
      ForceDirectories(ExtractFilePath(Staged));
      if not CopyFile(Source, Staged, False) then
      begin
        Result := CustomMessage('PrepareFailed') + #13#10 + ManifestData.Files[I].Path;
        Exit;
      end;
    end;
  end;
end;

// The text on the last page, and in the log.
procedure MakeResultText(const Dir: String);
begin
  // The counts go to the log only. The page says what the user needs to know, in the usual words of an installer.
  // The folder is not on this page. The page "Ready to Install" showed it before the install.
  if CountInstalled = 0 then
    ResultText := FmtMessage(CustomMessage('ResultAlreadyInstalled'), [ManifestData.Version])
  else if IsAlreadyInstalled(Dir) then
    ResultText := FmtMessage(CustomMessage('ResultUpdated'), [ManifestData.Version])
  else
    ResultText := FmtMessage(CustomMessage('ResultInstalled'), [ManifestData.Version]);
  if CountKept > 0 then
    ResultText := ResultText + #13#10 + #13#10 + CustomMessage('SettingsKept');
  ResultText := ResultText + #13#10 + #13#10 + SetupMessage(msgClickFinish);
  Log('D2RL: Files installed or updated: ' + IntToStr(CountInstalled) + '; already up to date: ' + IntToStr(CountSame) +
    '; settings kept: ' + IntToStr(CountKept));
end;

// ---- Where the uninstaller lives ----

// The folder that has one folder for each install (see UninstallDir). Setup looks here for installs that exist.
function InstallsBase: String;
begin
  Result := ExpandConstant('{autopf}') + '\D2RLoader\Installer';
#ifdef TEST_LOOPBACK
  // A test build keeps this away from a real install. /UninstBase= is the folder (the wizard demo uses it).
  // /UninstDir= is the exact folder of one install, so its parent is the base.
  if ExpandConstant('{param:UninstBase|}') <> '' then
    Result := ExpandConstant('{param:UninstBase|}')
  else if ExpandConstant('{param:UninstDir|}') <> '' then
    Result := ExtractFileDir(ExpandConstant('{param:UninstDir|}'))
  else
    Result := ExpandConstant('{localappdata}') + '\D2RLoader-InstallerTests\Installer';
#endif
end;

// The folder for the uninstaller and its record of the installed files. It is outside the game folder.
// It is under Program Files. Only an administrator can write there, so a standard user cannot put a program
// there that the uninstaller of an administrator would offer to start.
function UninstallDir(Param: String): String;
#ifdef TEST_LOOPBACK
var
  Given: String;
#endif
begin
  Result := InstallsBase + '\' + FolderKey(ExpandConstant('{app}'));
#ifdef TEST_LOOPBACK
  // /UninstDir= is the exact folder. See InstallsBase for the other test options.
  Given := ExpandConstant('{param:UninstDir|}');
  if Given <> '' then
    Result := Given;
#endif
end;

// ---- Shortcuts ----

// The name of the shortcut. It has the kind of the game folder, so two installs never share a name.
function ShortcutName(Param: String): String;
begin
  Result := 'D2RLoader (' + InstallKindText(KindOfFolder(RemoveBackslashUnlessRoot(ExpandConstant('{app}')))) + ')';
#ifdef TEST_LOOPBACK
  Result := 'Test ' + Result;
#endif
end;

// The folder of a shortcut for the [Icons] section. Param is Desktop or Start.
function ShortcutFolder(Param: String): String;
begin
  if Param = 'Desktop' then
    Result := ExpandConstant('{autodesktop}')
  else
    Result := ExpandConstant('{autoprograms}');
#ifdef TEST_LOOPBACK
  // A test build never writes to the real desktop or Start menu.
  Result := ExpandConstant('{param:IconDir|}');
  if Result = '' then
    Result := ExpandConstant('{localappdata}') + '\D2RLoader-InstallerTests\Icons';
  Result := Result + '\' + Param;
  ForceDirectories(Result);
#endif
end;

// Writes install.txt next to the uninstaller, so the uninstaller of any install can list all installs.
procedure CurStepChanged(CurStep: TSetupStep);
var
  Dir: String;
begin
  if CurStep <> ssPostInstall then
    Exit;

  Dir := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
  WriteInstallInfo(RemoveBackslashUnlessRoot(UninstallDir('')), KindOfFolder(Dir), Dir);
end;

// ---- Uninstall ----

var
  SettingsFolder: String;
  KeepSettings: Boolean;

var
  UnSlotItem: array of Integer;  // The install of each tile, or -1 if D2RLoader is not installed there.
  UnButtons: array of TNewButton;
  UnTexts: array of TNewStaticText;
  UnSelected: Integer;           // The number of the marked tile.

// The index of the first install of this kind, or -1.
function FirstInstallOfKind(const Items: TInstallInfos; const Kind: String): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to GetArrayLength(Items) - 1 do
  begin
    if Items[I].Kind = Kind then
    begin
      Result := I;
      Exit;
    end;
  end;
end;

// The marked tile is bold and says "Will be removed". The other tiles say if D2RLoader is installed there.
procedure RefreshUninstallTiles;
var
  I: Integer;
begin
  for I := 0 to GetArrayLength(UnButtons) - 1 do
  begin
    if I = UnSelected then
    begin
      UnButtons[I].Font.Style := [fsBold];
      UnTexts[I].Font.Style := [fsBold];
      UnTexts[I].Font.Color := clWindowText;
      UnTexts[I].Caption := CustomMessage('TileWillBeRemoved');
    end
    else
    begin
      UnButtons[I].Font.Style := [];
      UnTexts[I].Font.Style := [];
      UnTexts[I].Font.Color := clGrayText;
      if UnSlotItem[I] >= 0 then
        UnTexts[I].Caption := CustomMessage('TileInstalled')
      else
        UnTexts[I].Caption := CustomMessage('TileNotInstalled');
    end;
  end;
end;

procedure UninstallTileClick(Sender: TObject);
begin
  UnSelected := TNewButton(Sender).Tag;
  RefreshUninstallTiles;
end;

// The window of the uninstaller. It looks like the pages of Setup (see dialog.pas). The tiles show where
// D2RLoader is installed, and the player marks one. A tile only marks. The button "Uninstall" removes,
// because this deletes files. One box is for the settings.
// Returns False if the user cancels. Chosen is the index of the install to remove.
function ShowUninstallForm(const Items: TInstallInfos; Selected: Integer; var Chosen: Integer; var RemoveSettings: Boolean): Boolean;
var
  Form: TSetupForm;
  Note, Text: TNewStaticText;
  Button: TNewButton;
  Box: TNewCheckListBox;
  OkButton, CancelButton: TNewButton;
  I, Slots, Rows, Top, BodyTop, FooterTop, Gap, TileWidth, RowHeight, ButtonWidth, TextWidth: Integer;
  Name, Folder, Description: String;
begin
  Result := False;
  Gap := ScaleX(12);
  RowHeight := ScaleY(TileHeight + 6 + TileStatusHeight + 14);

  // The first tile is for Battle.net, and the second is for Steam. Every other install has a tile after them.
  // If there is no other install, the third tile is grey.
  SetArrayLength(UnSlotItem, 2);
  UnSlotItem[0] := FirstInstallOfKind(Items, KindBattleNet);
  UnSlotItem[1] := FirstInstallOfKind(Items, KindSteam);
  Slots := 2;
  for I := 0 to GetArrayLength(Items) - 1 do
  begin
    if (I <> UnSlotItem[0]) and (I <> UnSlotItem[1]) then
    begin
      Slots := Slots + 1;
      SetArrayLength(UnSlotItem, Slots);
      UnSlotItem[Slots - 1] := I;
    end;
  end;
  if Slots = 2 then
  begin
    Slots := 3;
    SetArrayLength(UnSlotItem, Slots);
    UnSlotItem[2] := -1;
  end;

  UnSelected := 0;
  for I := 0 to Slots - 1 do
  begin
    if UnSlotItem[I] = Selected then
      UnSelected := I;
  end;
  SetArrayLength(UnButtons, Slots);
  SetArrayLength(UnTexts, Slots);
  Rows := (Slots + 2) div 3;

  Form := CreateCustomForm(ScaleX(560), ScaleY(DialogHeaderHeight + 18 + 10 + 24 + 44 + 14 + DialogFooterHeight) + Rows * RowHeight, False, True);
  try
    Form.Caption := FmtMessage(SetupMessage(msgUninstallAppFullTitle), ['D2RLoader']);
    if GetArrayLength(Items) > 1 then
      Description := CustomMessage('UninstallSeveral')
    else
      Description := CustomMessage('UninstallOne');
    MakeDialogFrame(Form, CustomMessage('UninstallWindowTitle'), Description, AddBackslash(ExtractFileDir(ExpandConstant('{uninstallexe}'))) + DialogLogoFile,
      BodyTop, FooterTop);

    // The window can be wider than the number that was asked for (the screen scale). Use the real width.
    TextWidth := Form.ClientWidth - ScaleX(2 * 20);
    TileWidth := (TextWidth - 2 * Gap) div 3;
    Top := BodyTop;

    for I := 0 to Slots - 1 do
    begin
      if I = 0 then
        Name := 'Battle.net'
      else if I = 1 then
        Name := 'Steam'
      else if UnSlotItem[I] >= 0 then
        Name := InstallKindText(Items[UnSlotItem[I]].Kind)
      else
        Name := InstallKindText(KindCustom);

      Folder := '';
      if UnSlotItem[I] >= 0 then
        Folder := Items[UnSlotItem[I]].GameDir;
      MakeTile(Form, I, Name, '', Folder, UnSlotItem[I] >= 0, ScaleX(20) + (I mod 3) * (TileWidth + Gap), Top + (I div 3) * RowHeight,
        TileWidth, clBtnFace, @UninstallTileClick, Button, Text);
      UnButtons[I] := Button;
      UnTexts[I] := Text;
    end;
    RefreshUninstallTiles;
    Top := Top + Rows * RowHeight;

    // One box. It is a list with one item, because a plain check box is painted white by the theme,
    // and the body of the window is grey.
    Box := TNewCheckListBox.Create(Form);
    Box.Parent := Form;
    Box.BorderStyle := bsNone;
    Box.Color := clBtnFace;
    Box.Left := ScaleX(20);
    Box.Top := Top;
    Box.Width := TextWidth;
    Box.Height := ScaleY(22);
    Box.AddCheckBox(CustomMessage('DeleteSettings'), '', 0, False, True, False, False, nil);
    Top := Top + ScaleY(24);

    Note := TNewStaticText.Create(Form);
    Note.Parent := Form;
    Note.Left := ScaleX(40);
    Note.Top := Top;
    Note.Width := TextWidth - ScaleX(20);
    Note.AutoSize := False;
    Note.Color := clBtnFace;
    Note.WordWrap := True;
    Note.Height := ScaleY(44);
    Note.Caption := CustomMessage('DeleteSettingsNote');

    OkButton := TNewButton.Create(Form);
    OkButton.Parent := Form;
    OkButton.Caption := CustomMessage('UninstallName');
    OkButton.Left := Form.ClientWidth - ScaleX(90 + 8 + 90 + 14);
    OkButton.Top := FooterTop + ScaleY(12);
    OkButton.Height := ScaleY(23);
    OkButton.ModalResult := mrOk;
    OkButton.Default := True;

    CancelButton := TNewButton.Create(Form);
    CancelButton.Parent := Form;
    CancelButton.Caption := SetupMessage(msgButtonCancel);
    CancelButton.Left := Form.ClientWidth - ScaleX(90 + 14);
    CancelButton.Top := FooterTop + ScaleY(12);
    CancelButton.Height := ScaleY(23);
    CancelButton.ModalResult := mrCancel;
    CancelButton.Cancel := True;

    ButtonWidth := Form.CalculateButtonWidth([OkButton.Caption, CancelButton.Caption]);
    if ButtonWidth < ScaleX(90) then
      ButtonWidth := ScaleX(90);
    OkButton.Width := ButtonWidth;
    CancelButton.Width := ButtonWidth;
    Form.ActiveControl := OkButton;

    if Form.ShowModal() <> mrOk then
      Exit;

    Chosen := UnSlotItem[UnSelected];
    RemoveSettings := Box.Checked[0];
    Result := True;
  finally
    Form.Free();
  end;
end;

// Starts the uninstaller of another install. It must not ask again, so it gets /Picked=1 and the settings choice.
procedure StartOtherUninstaller(const Info: TInstallInfo; RemoveSettings: Boolean);
var
  Params: String;
  ResultCode: Integer;
begin
  Params := '/Picked=1';
  if RemoveSettings then
    Params := Params + ' /RemoveSettings=1';
  if UninstallSilent then
    Params := Params + ' /VERYSILENT /SUPPRESSMSGBOXES';
  Log('D2RL: handing over to ' + Info.UninstallDir);
  Exec(AddBackslash(Info.UninstallDir) + UninstallerFile, Params, '', SW_SHOWNORMAL, ewNoWait, ResultCode);
end;

// Which install to remove, and the question about the settings. Returns False to stop this uninstaller:
// the user cancelled, or the uninstaller of another install was started.
// A silent run removes the install of this uninstaller. It keeps the settings, unless it has /RemoveSettings=1.
function ChooseInstall: Boolean;
var
  Items: TInstallInfos;
  OwnDir, Pick: String;
  Own, Chosen, I: Integer;
  RemoveSettings: Boolean;
begin
  Result := False;
  OwnDir := RemoveBackslashUnlessRoot(ExtractFileDir(ExpandConstant('{uninstallexe}')));
  FindInstalls(ExtractFileDir(OwnDir), Items);
  Own := -1;
  for I := 0 to GetArrayLength(Items) - 1 do
  begin
    if SameFilePath(Items[I].UninstallDir, OwnDir) then
      Own := I;
  end;

  Log('D2RL: this uninstaller is ' + OwnDir + '; installs found: ' + IntToStr(GetArrayLength(Items)));
  SettingsFolder := RemoveBackslashUnlessRoot(ExpandConstant('{app}')) + '\d2rloader\config';
  KeepSettings := ExpandConstant('{param:RemoveSettings|}') = '';
  Chosen := Own;

  if UninstallSilent then
  begin
    // The test build lets a test pick another install, because a test cannot click in the window.
    Pick := '';
#ifdef TEST_LOOPBACK
    Pick := ExpandConstant('{param:Pick|}');
#endif
    if (Pick <> '') and (ExpandConstant('{param:Picked|}') = '') then
    begin
      Chosen := -1;
      for I := 0 to GetArrayLength(Items) - 1 do
      begin
        if SameFilePath(Items[I].GameDir, Pick) then
          Chosen := I;
      end;

      // A pick that matches no install acts like Cancel.
      if Chosen < 0 then
      begin
        Log('D2RL: no install has the game folder ' + Pick);
        Exit;
      end;

      if Chosen <> Own then
      begin
        StartOtherUninstaller(Items[Chosen], not KeepSettings);
        Exit;
      end;
    end;
    Result := True;
    Exit;
  end;

  // A window with a choice. It is not shown again when another uninstaller handed over to this one.
  if ExpandConstant('{param:Picked|}') <> '' then
  begin
    Result := True;
    Exit;
  end;

  if Own < 0 then
  begin
    SetArrayLength(Items, 1);
    Items[0].Kind := KindCustom;
    Items[0].GameDir := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
    Items[0].UninstallDir := OwnDir;
    Own := 0;
  end;

  RemoveSettings := False;
  if not ShowUninstallForm(Items, Own, Chosen, RemoveSettings) then
  begin
    Log('D2RL: the user cancelled');
    Exit;
  end;

  KeepSettings := not RemoveSettings;
  if Chosen <> Own then
  begin
    StartOtherUninstaller(Items[Chosen], RemoveSettings);
    Exit;
  end;
  Result := True;
end;

// Steps before the uninstall starts. A False stops the uninstaller.
// 1. Choose the install and answer the question about the settings. 2. The game must be closed.
function InitializeUninstall: Boolean;
var
  Message: String;
begin
  Result := False;
  Log('D2RL: uninstall starts');
  if not ChooseInstall then
    Exit;

  Message := CheckGameClosed(RemoveBackslashUnlessRoot(ExpandConstant('{app}')));
  if Message <> '' then
  begin
    Log('D2RL: ' + Message);
    Exit;
  end;

  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  // The files are gone. Remove the settings too if the user said so. Then remove the folder d2rloader if it is empty.
  if (not KeepSettings) and DirExists(SettingsFolder) then
  begin
    DelTree(SettingsFolder, True, True, True);
    RemoveDir(ExtractFileDir(SettingsFolder));
    Log('D2RL: removed the settings folder ' + SettingsFolder);
  end;

  // This file tells the other uninstallers about this install. It is not needed any more.
  DeleteFile(AddBackslash(ExtractFileDir(ExpandConstant('{uninstallexe}'))) + InstallInfoFile);
end;

// ---- The game folder page: one big button (a tile) for each place ----

const
  TileBattleNet = 0;
  TileSteam = 1;
  TileOther = 2;

var
  TileFirst: TNewButton;  // The first tile that can be clicked. It gets the keyboard focus.
  TilesHideNext: Boolean;

// The index of the first found folder of this kind, or -1.
function FirstCandidateOfKind(const Kind: String): Integer;
var
  I: Integer;
begin
  Result := -1;
  for I := 0 to GetArrayLength(CandidateKinds) - 1 do
  begin
    if CandidateKinds[I] = Kind then
    begin
      Result := I;
      Exit;
    end;
  end;
end;

// A click on a tile chooses the place and goes on to the next page. The Next button is hidden on this page.
procedure TileClick(Sender: TObject);
begin
  case TNewButton(Sender).Tag of
    TileBattleNet: TileChoice := FirstCandidateOfKind(KindBattleNet);
    TileSteam: TileChoice := FirstCandidateOfKind(KindSteam);
  else
    TileChoice := -1;
  end;
  WizardForm.NextButton.OnClick(WizardForm.NextButton);
end;

// One tile on the game folder page. The folder shows in a tip when the mouse stays over the tile.
procedure AddTile(Number: Integer; const Name, Status, Folder: String; Enabled: Boolean; Left, Width: Integer);
var
  Button: TNewButton;
  Text: TNewStaticText;
begin
  MakeTile(TilePage.Surface, Number, Name, Status, Folder, Enabled, Left, ScaleY(36), Width, clBtnFace, @TileClick, Button, Text);
  if Enabled and (TileFirst = nil) then
    TileFirst := Button;
end;

function FoundText(Index: Integer): String;
begin
  if Index < 0 then
    Result := CustomMessage('TileNotFound')
  else if IsAlreadyInstalled(CandidateDirs[Index]) then
    Result := CustomMessage('TileInstalled')
  else
    Result := CustomMessage('TileFound');
end;

// The folder of a found place, for the tip of its tile (empty if there is none).
function FoundFolder(Index: Integer): String;
begin
  Result := '';
  if Index >= 0 then
    Result := CandidateDirs[Index];
end;

// The page has three tiles. The folders are not on the page: a path looks crowded. They are in a tip over the tile,
// and the "Ready to Install" page shows the folder that the player chose.
procedure CreateTilePage;
var
  Gap, Width: Integer;
  Intro: TNewStaticText;
  Battle, Steam: Integer;
begin
  TilePage := CreateCustomPage(wpWelcome, CustomMessage('TilesTitle'), CustomMessage('TilesDescription'));
  Gap := ScaleX(12);
  Width := (TilePage.SurfaceWidth - 2 * Gap) div 3;

  Intro := TNewStaticText.Create(TilePage);
  Intro.Parent := TilePage.Surface;
  Intro.Left := 0;
  Intro.Top := 0;
  Intro.Caption := CustomMessage('TilesIntro');

  Battle := FirstCandidateOfKind(KindBattleNet);
  Steam := FirstCandidateOfKind(KindSteam);
  AddTile(TileBattleNet, 'Battle.net', FoundText(Battle), FoundFolder(Battle), Battle >= 0, 0, Width);
  AddTile(TileSteam, 'Steam', FoundText(Steam), FoundFolder(Steam), Steam >= 0, Width + Gap, Width);
  AddTile(TileOther, CustomMessage('OtherFolder'), CustomMessage('TileYouChoose'), '', True, 2 * (Width + Gap), Width);
end;

// ---- The page "Update or Uninstall" ----

// One row: a choice with a bold name, and a short line under it.
procedure AddMaintenanceRow(var Radio: TNewRadioButton; const Name, Line: String; Top: Integer; Checked: Boolean);
var
  Text: TNewStaticText;
begin
  Radio := TNewRadioButton.Create(MaintenancePage);
  Radio.Parent := MaintenancePage.Surface;
  Radio.Left := 0;
  Radio.Top := Top;
  Radio.Width := MaintenancePage.SurfaceWidth;
  Radio.Height := ScaleY(22);
  Radio.Font.Size := 10;
  Radio.Font.Style := [fsBold];
  Radio.Caption := Name;
  Radio.Checked := Checked;

  Text := TNewStaticText.Create(MaintenancePage);
  Text.Parent := MaintenancePage.Surface;
  Text.AutoSize := False;
  Text.WordWrap := True;
  Text.Left := ScaleX(20);
  Text.Top := Top + ScaleY(24);
  Text.Width := MaintenancePage.SurfaceWidth - ScaleX(20);
  Text.Height := ScaleY(34);
  Text.Caption := Line;
end;

// There is no "Repair". An update compares every file and downloads again each file that is damaged or missing.
procedure CreateMaintenancePage;
begin
  MaintenancePage := CreateCustomPage(wpWelcome, CustomMessage('MaintenanceTitle'), CustomMessage('MaintenanceDescription'));
  AddMaintenanceRow(UpdateRadio, CustomMessage('UpdateName'), CustomMessage('UpdateLine'), ScaleY(8), True);
  AddMaintenanceRow(UninstallRadio, CustomMessage('UninstallName'), CustomMessage('UninstallLine'), ScaleY(8 + 70), False);
end;

// "Uninstall": start the uninstaller and close Setup. The uninstaller shows all installs and lets the player choose.
// Setup closes without the question "Exit Setup?" (see CancelButtonClick).
procedure OpenUninstaller;
var
  ResultCode: Integer;
begin
  Log('D2RL: the player chose Uninstall. Starting ' + ExistingInstalls[0].UninstallDir);
  if Exec(AddBackslash(ExistingInstalls[0].UninstallDir) + UninstallerFile, '', '', SW_SHOWNORMAL, ewNoWait, ResultCode) then
  begin
    ClosingForUninstall := True;
    WizardForm.Close;
  end
  else
    MsgBox(CustomMessage('UninstallerNotStarted'), mbError, MB_OK);
end;

// ---- Pages ----

// Moves the controls under the text of the folder page down by Delta pixels.
procedure MoveSelectDirControls(Delta: Integer);
begin
  WizardForm.SelectDirBrowseLabel.Top := WizardForm.SelectDirBrowseLabel.Top + Delta;
  WizardForm.DirEdit.Top := WizardForm.DirEdit.Top + Delta;
  WizardForm.DirBrowseButton.Top := WizardForm.DirBrowseButton.Top + Delta;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('DownloadTitle'), CustomMessage('DownloadDescription'), @DownloadProgress);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;

  FindCandidates;
  FindInstalls(InstallsBase, ExistingInstalls);
  WizardForm.WelcomeLabel2.Caption := CustomMessage('WelcomeBody1') + #13#10 + #13#10 + CustomMessage('WelcomeBody2');
  WizardForm.SelectDirLabel.Caption := FmtMessage(CustomMessage('SelectDirNote'), [GameExe]);
  // The label has the height of one line. This text needs two or three lines, so make the label as high as the text,
  // and move the controls under it down. Without this, the end of the sentence is cut off.
  MoveSelectDirControls(WizardForm.SelectDirLabel.AdjustHeight);

  // The page that is made last comes first after the Welcome page.
  CreateTilePage;
  CreateMaintenancePage;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if PageID = MaintenancePage.ID then
    // A silent run, and a run with /DIR=, have no one to ask. A first install has nothing to update or remove.
    Result := WizardSilent or HasDirParam or (GetArrayLength(ExistingInstalls) = 0)
  else if PageID = TilePage.ID then
    Result := ChoiceIsHidden
  else if PageID = wpSelectDir then
  begin
    // The folder page is needed when the choice page is hidden by /DIR=, or when the user picks "Another folder".
    // A silent run has no one to ask. PrepareToInstall checks the folder.
    if WizardSilent then
      Result := True
    else if not ChoiceIsHidden then
      Result := CandidateChosen;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = MaintenancePage.ID then
  begin
    if UninstallRadio.Checked then
    begin
      OpenUninstaller;
      Result := False;
    end;
  end
  else if CurPageID = TilePage.ID then
  begin
    // "Other folder" does not start with a found folder, so the player does not install into it by mistake.
    // It starts with the usual place. If that is not the game, the next page says so and the player clicks Browse.
    if CandidateChosen then
      WizardForm.DirEdit.Text := CandidateDirs[TileChoice]
    else
      WizardForm.DirEdit.Text := ExpandConstant('{commonpf32}') + '\Diablo II Resurrected';
  end
  else if CurPageID = wpSelectDir then
  begin
    if not IsGameFolder(WizardDirValue) then
    begin
      MsgBox(CheckGameFolder(WizardDirValue), mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // The tiles take the place of the Next button. Show the button again on the other pages.
  if CurPageID = TilePage.ID then
  begin
    WizardForm.NextButton.Visible := False;
    TilesHideNext := True;
    try
      WizardForm.ActiveControl := TileFirst;
    except
      // The focus is a help only.
    end;
  end
  else if TilesHideNext then
  begin
    WizardForm.NextButton.Visible := True;
    TilesHideNext := False;
  end;

  if CurPageID = wpFinished then
  begin
    WizardForm.FinishedLabel.Caption := ResultText;
    WizardForm.FinishedLabel.Height := ScaleY(150);
  end
  else if CurPageID = wpSelectDir then
    // Setup downloads the files, so the number that Setup works out for the disk space is wrong. Do not show it.
    WizardForm.DiskSpaceLabel.Visible := False;
end;
