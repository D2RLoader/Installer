// Finds the Diablo II: Resurrected folders on this computer.
// Battle.net: the Windows uninstall entry. Steam: libraryfolders.vdf and appmanifest_<id>.acf.
// A folder counts only if D2R.exe is inside it.

const
  SteamAppId = '2536520';
  GameExe = 'D2R.exe';

procedure AddString(var List: TArrayOfString; const S: String);
var
  N: Integer;
begin
  N := GetArrayLength(List);
  SetArrayLength(List, N + 1);
  List[N] := S;
end;

function ListHasText(const List: TArrayOfString; const S: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 0 to GetArrayLength(List) - 1 do
  begin
    if CompareText(List[I], S) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

// The character at position I, or #0 outside the text. Avoids reading past the end.
function CharAt(const S: String; I: Integer): Char;
begin
  Result := #0;
  if I < 1 then
    Exit;

  if I > Length(S) then
    Exit;

  Result := S[I];
end;

// A short name for a game folder, for the folder that keeps the uninstaller of that game folder.
// The letter case of the path does not matter. 12 hex digits of the SHA-256 hash of the path.
function FolderKey(const Dir: String): String;
begin
  Result := Copy(GetSHA256OfUnicodeString(Lowercase(RemoveBackslashUnlessRoot(Dir))), 1, 12);
end;

function IsGameFolder(const Dir: String): Boolean;
begin
  Result := False;
  if Dir = '' then
    Exit;

  Result := FileExists(AddBackslash(Dir) + GameExe);
end;

// ---- Valve Data Format (VDF) ----

// Splits VDF text into tokens. A quoted string becomes 'S' + text. A brace becomes 'B{' or 'B}'.
// Inside a string, \\ \" \n \t are decoded. Lines that start with // are comments.
procedure VdfTokens(const Text: String; var Tokens: TArrayOfString);
var
  I: Integer;
  S: String;
  C: Char;
begin
  SetArrayLength(Tokens, 0);
  I := 1;
  while I <= Length(Text) do
  begin
    C := Text[I];
    if C = '"' then
    begin
      S := '';
      I := I + 1;
      while (CharAt(Text, I) <> '"') and (CharAt(Text, I) <> #0) do
      begin
        C := Text[I];
        if C = '\' then
        begin
          I := I + 1;
          C := CharAt(Text, I);
          if C = 'n' then
            C := #10
          else if C = 't' then
            C := #9;
        end;
        if C <> #0 then
          S := S + C;
        I := I + 1;
      end;
      I := I + 1;
      AddString(Tokens, 'S' + S);
    end
    else if (C = '{') or (C = '}') then
    begin
      AddString(Tokens, 'B' + C);
      I := I + 1;
    end
    else if (C = '/') and (CharAt(Text, I + 1) = '/') then
    begin
      while (CharAt(Text, I) <> #10) and (CharAt(Text, I) <> #0) do
        I := I + 1;
    end
    else
      I := I + 1;
  end;
end;

// Collects every "key" "value" pair, at any depth. A key followed by a brace opens a section and is not a pair.
procedure VdfPairs(const Tokens: TArrayOfString; var Keys, Values: TArrayOfString);
var
  I, N: Integer;
begin
  SetArrayLength(Keys, 0);
  SetArrayLength(Values, 0);
  N := GetArrayLength(Tokens);
  I := 0;
  while I < N do
  begin
    if (Copy(Tokens[I], 1, 1) = 'S') and (I + 1 < N) then
    begin
      if Copy(Tokens[I + 1], 1, 1) = 'S' then
      begin
        AddString(Keys, Copy(Tokens[I], 2, Length(Tokens[I])));
        AddString(Values, Copy(Tokens[I + 1], 2, Length(Tokens[I + 1])));
        I := I + 2;
      end
      else
        I := I + 1;
    end
    else
      I := I + 1;
  end;
end;

// Reads a UTF-8 text file. A byte order mark at the start is removed.
function ReadUtf8File(const FileName: String; var Text: String): Boolean;
var
  Source: AnsiString;
begin
  Result := False;
  Text := '';
  if not LoadStringFromFile(FileName, Source) then
    Exit;

  Text := UTF8Decode(Source);
  if CharAt(Text, 1) = Chr($FEFF) then
    Delete(Text, 1, 1);
  Result := True;
end;

// Steam writes VDF files as UTF-8.
function VdfReadFile(const FileName: String; var Keys, Values: TArrayOfString): Boolean;
var
  Text: String;
  Tokens: TArrayOfString;
begin
  Result := False;
  if not ReadUtf8File(FileName, Text) then
    Exit;

  VdfTokens(Text, Tokens);
  VdfPairs(Tokens, Keys, Values);
  Result := True;
end;

// ---- Battle.net ----

// The uninstall entry is in the 32-bit registry view. HKLM32 reaches it from a 32-bit or 64-bit installer.
function FindBattleNetFolder(var Dir: String): Boolean;
begin
  Result := False;
  Dir := '';
  if not RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Diablo II Resurrected', 'InstallLocation', Dir) then
    Exit;

  Dir := RemoveBackslashUnlessRoot(Dir);
  Result := IsGameFolder(Dir);
end;

// ---- Steam ----

function FindSteamRoot(var Root: String): Boolean;
begin
  Result := False;
  Root := '';
  if not RegQueryStringValue(HKCU, 'Software\Valve\Steam', 'SteamPath', Root) then
  begin
    if not RegQueryStringValue(HKLM32, 'SOFTWARE\Valve\Steam', 'InstallPath', Root) then
      Exit;
  end;

  StringChangeEx(Root, '/', '\', True);
  Root := RemoveBackslashUnlessRoot(Root);
  Result := DirExists(Root);
end;

// The Steam folder plus every "path" in steamapps\libraryfolders.vdf.
procedure SteamLibraries(const SteamRoot: String; var Libraries: TArrayOfString);
var
  Keys, Values: TArrayOfString;
  I: Integer;
  Path: String;
begin
  SetArrayLength(Libraries, 0);
  AddString(Libraries, SteamRoot);
  if not VdfReadFile(AddBackslash(SteamRoot) + 'steamapps\libraryfolders.vdf', Keys, Values) then
    Exit;

  for I := 0 to GetArrayLength(Keys) - 1 do
  begin
    if Keys[I] = 'path' then
    begin
      Path := RemoveBackslashUnlessRoot(Values[I]);
      if not ListHasText(Libraries, Path) then
        AddString(Libraries, Path);
    end;
  end;
end;

// installdir must be one folder name. It must not climb out of steamapps\common.
function IsSingleFolderName(const Name: String): Boolean;
begin
  Result := False;
  if Name = '' then
    Exit;

  if (Pos('\', Name) > 0) or (Pos('/', Name) > 0) or (Pos(':', Name) > 0) then
    Exit;

  if (Name = '.') or (Name = '..') then
    Exit;

  Result := True;
end;

// Looks in one Steam library for the game. Returns the game folder, or '' if it is not there.
function SteamGameInLibrary(const Library_: String): String;
var
  Keys, Values: TArrayOfString;
  I: Integer;
  Dir: String;
begin
  Result := '';
  if not VdfReadFile(AddBackslash(Library_) + 'steamapps\appmanifest_' + SteamAppId + '.acf', Keys, Values) then
    Exit;

  for I := 0 to GetArrayLength(Keys) - 1 do
  begin
    if Keys[I] = 'installdir' then
    begin
      if not IsSingleFolderName(Values[I]) then
        Exit;

      Dir := AddBackslash(Library_) + 'steamapps\common\' + Values[I];
      if IsGameFolder(Dir) then
        Result := Dir;
      Exit;
    end;
  end;
end;

// All Steam game folders under one Steam folder.
procedure FindSteamFolders(const SteamRoot: String; var Dirs: TArrayOfString);
var
  Libraries: TArrayOfString;
  I: Integer;
  Dir: String;
begin
  SetArrayLength(Dirs, 0);
  SteamLibraries(SteamRoot, Libraries);
  for I := 0 to GetArrayLength(Libraries) - 1 do
  begin
    Dir := SteamGameInLibrary(Libraries[I]);
    if Dir <> '' then
    begin
      if not ListHasText(Dirs, Dir) then
        AddString(Dirs, Dir);
    end;
  end;
end;
