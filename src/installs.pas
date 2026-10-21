// The list of installs. Each install keeps its uninstaller in its own folder, and next to it a small text file
// (install.txt) that says which game it belongs to. The uninstaller reads these files to let the user choose.
//
// install.txt has two lines, in UTF-8:
//   line 1: the kind: Battle.net, Steam, or Custom
//   line 2: the game folder
// Needs gamefolder.pas (AddString, ReadUtf8File) before it.

const
  InstallInfoFile = 'install.txt';
  UninstallerFile = 'unins000.exe';
  KindBattleNet = 'Battle.net';
  KindSteam = 'Steam';
  KindCustom = 'Custom';

type
  TInstallInfo = record
    Kind: String;
    GameDir: String;
    UninstallDir: String;
  end;
  TInstallInfos = array of TInstallInfo;

function IsKnownKind(const Kind: String): Boolean;
begin
  Result := (Kind = KindBattleNet) or (Kind = KindSteam) or (Kind = KindCustom);
end;

procedure WriteInstallInfo(const UninstallDir, Kind, GameDir: String);
var
  Lines: TArrayOfString;
begin
  ForceDirectories(UninstallDir);
  SetArrayLength(Lines, 2);
  Lines[0] := Kind;
  Lines[1] := GameDir;
  SaveStringsToUTF8FileWithoutBOM(AddBackslash(UninstallDir) + InstallInfoFile, Lines, False);
end;

// Reads install.txt in one uninstall folder. The folder must also have the uninstaller.
function ReadInstallInfo(const UninstallDir: String; var Info: TInstallInfo): Boolean;
var
  Text, Kind, GameDir: String;
  Cut: Integer;
begin
  Result := False;
  if not FileExists(AddBackslash(UninstallDir) + UninstallerFile) then
    Exit;

  if not ReadUtf8File(AddBackslash(UninstallDir) + InstallInfoFile, Text) then
    Exit;

  StringChangeEx(Text, #13, '', True);
  Cut := Pos(#10, Text);
  if Cut = 0 then
    Exit;

  Kind := Copy(Text, 1, Cut - 1);
  GameDir := Copy(Text, Cut + 1, Length(Text));
  Cut := Pos(#10, GameDir);
  if Cut > 0 then
    GameDir := Copy(GameDir, 1, Cut - 1);

  if not IsKnownKind(Kind) then
    Exit;

  if GameDir = '' then
    Exit;

  Info.Kind := Kind;
  Info.GameDir := GameDir;
  Info.UninstallDir := RemoveBackslashUnlessRoot(UninstallDir);
  Result := True;
end;

// Every install under Base: each sub-folder that has install.txt and the uninstaller.
// The list is sorted: Battle.net first, then Steam, then Custom. Inside a kind it is sorted by game folder.
procedure FindInstalls(const Base: String; var Items: TInstallInfos);
var
  FindRec: TFindRec;
  Info, Swap: TInstallInfo;
  I, J, N: Integer;
  Before: Boolean;
begin
  SetArrayLength(Items, 0);
  if FindFirst(AddBackslash(Base) + '*', FindRec) then
  begin
    try
      repeat
        if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
        begin
          if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
          begin
            if ReadInstallInfo(AddBackslash(Base) + FindRec.Name, Info) then
            begin
              N := GetArrayLength(Items);
              SetArrayLength(Items, N + 1);
              Items[N] := Info;
            end;
          end;
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;

  // A small sort. There are a few installs at most.
  for I := 0 to GetArrayLength(Items) - 2 do
  begin
    for J := I + 1 to GetArrayLength(Items) - 1 do
    begin
      if Items[I].Kind = Items[J].Kind then
        Before := CompareText(Items[J].GameDir, Items[I].GameDir) < 0
      else if Items[I].Kind = KindBattleNet then
        Before := False
      else if Items[J].Kind = KindBattleNet then
        Before := True
      else
        Before := Items[J].Kind = KindSteam;

      if Before then
      begin
        Swap := Items[I];
        Items[I] := Items[J];
        Items[J] := Swap;
      end;
    end;
  end;
end;

// The name that the user sees for an install.
function InstallKindText(const Kind: String): String;
begin
  if Kind = KindCustom then
    Result := CustomMessage('OtherFolder')
  else
    Result := Kind;
end;
