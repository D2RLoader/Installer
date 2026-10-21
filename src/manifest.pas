// The manifest: reads the JSON and checks every rule in docs/manifest.md.
// Needs third_party\JsonParser.pas and gamefolder.pas (for AddString) before it.

type
  TManifestFile = record
    Path: String;
    Url: String;
    Size: Int64;
    Sha256: String;
    OnlyIfMissing: Boolean;
  end;
  TManifestFiles = array of TManifestFile;
  TManifest = record
    Version: String;
    Files: TManifestFiles;
    Folders: TArrayOfString;
  end;

const
  ManifestSchema = 1;
  ManifestMaxChars = 262144;
  ManifestMaxDepth = 8;
  ManifestMaxFiles = 200;
  ManifestMaxFolders = 100;
  ManifestMaxFileSize = 4294967296;

// ---- Rules ----

// The path rules from docs/manifest.md. A path is relative to the game folder and uses /.
function IsSafePath(const Path: String): Boolean;
var
  Rest, Name: String;
  Slash: Integer;
begin
  Result := False;
  if Path = '' then
    Exit;

  if (Pos('\', Path) > 0) or (Pos(':', Path) > 0) then
    Exit;

  Rest := Path;
  while True do
  begin
    Slash := Pos('/', Rest);
    if Slash > 0 then
      Name := Copy(Rest, 1, Slash - 1)
    else
      Name := Rest;

    if (Name = '') or (Name = '.') or (Name = '..') then
      Exit;

    if (Name[Length(Name)] = '.') or (Name[Length(Name)] = ' ') then
      Exit;

    if Slash = 0 then
      Break;

    Rest := Copy(Rest, Slash + 1, Length(Rest));
  end;
  Result := True;
end;

// The full Windows path of a manifest path inside the game folder.
function TargetPath(const Dir, RelPath: String): String;
var
  P: String;
begin
  P := RelPath;
  StringChangeEx(P, '/', '\', True);
  Result := AddBackslash(Dir) + P;
end;

// The file name at the end of a manifest path.
function LeafName(const RelPath: String): String;
var
  I: Integer;
begin
  Result := RelPath;
  for I := Length(RelPath) downto 1 do
  begin
    if RelPath[I] = '/' then
    begin
      Result := Copy(RelPath, I + 1, Length(RelPath));
      Exit;
    end;
  end;
end;

// Downloads must use https. A test build may also allow http on the local computer.
function IsAllowedUrl(const Url: String): Boolean;
begin
  Result := Pos('https://', Lowercase(Url)) = 1;
#ifdef TEST_LOOPBACK
  if Pos('http://127.0.0.1:', Url) = 1 then
    Result := True;
#endif
end;

// 64 lowercase hexadecimal digits.
function IsSha256Text(const S: String): Boolean;
var
  I: Integer;
  C: Char;
begin
  Result := False;
  if Length(S) <> 64 then
    Exit;

  for I := 1 to 64 do
  begin
    C := S[I];
    if not (((C >= '0') and (C <= '9')) or ((C >= 'a') and (C <= 'f'))) then
      Exit;
  end;
  Result := True;
end;

// The deepest nesting of { and [ outside strings. Brackets inside a string do not count.
function JsonDepth(const Text: String): Integer;
var
  I, Depth: Integer;
  C: Char;
  InString: Boolean;
begin
  Result := 0;
  Depth := 0;
  InString := False;
  I := 1;
  while I <= Length(Text) do
  begin
    C := Text[I];
    if InString then
    begin
      if C = '\' then
        I := I + 1
      else if C = '"' then
        InString := False;
    end
    else if C = '"' then
      InString := True
    else if (C = '{') or (C = '[') then
    begin
      Depth := Depth + 1;
      if Depth > Result then
        Result := Depth;
    end
    else if (C = '}') or (C = ']') then
      Depth := Depth - 1;
    I := I + 1;
  end;
end;

// ---- Reading values from the parser output ----

function JsonFindKey(const Output: TJsonParserOutput; ObjectIndex: Integer; const Key: String; var Found: TJsonValue): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 0 to GetArrayLength(Output.Objects[ObjectIndex]) - 1 do
  begin
    if Output.Objects[ObjectIndex][I].Key = Key then
    begin
      Found := Output.Objects[ObjectIndex][I].Value;
      Result := True;
      Exit;
    end;
  end;
end;

function JsonGetString(const Output: TJsonParserOutput; ObjectIndex: Integer; const Key: String; var S: String): Boolean;
var
  V: TJsonValue;
begin
  Result := False;
  if not JsonFindKey(Output, ObjectIndex, Key, V) then
    Exit;

  if V.Kind <> JVKString then
    Exit;

  S := Output.Strings[V.Index];
  Result := True;
end;

function JsonGetNumber(const Output: TJsonParserOutput; ObjectIndex: Integer; const Key: String; var N: Double): Boolean;
var
  V: TJsonValue;
begin
  Result := False;
  if not JsonFindKey(Output, ObjectIndex, Key, V) then
    Exit;

  if V.Kind <> JVKNumber then
    Exit;

  N := Output.Numbers[V.Index];
  Result := True;
end;

// A missing key gives Default. A key with another type than true or false is an error: Valid is False.
function JsonGetBool(const Output: TJsonParserOutput; ObjectIndex: Integer; const Key: String; Default: Boolean; var Valid: Boolean): Boolean;
var
  V: TJsonValue;
begin
  Result := Default;
  Valid := True;
  if not JsonFindKey(Output, ObjectIndex, Key, V) then
    Exit;

  if V.Kind <> JVKWord then
  begin
    Valid := False;
    Exit;
  end;

  if Output.Words[V.Index] = JWTrue then
    Result := True
  else if Output.Words[V.Index] = JWFalse then
    Result := False
  else
    Valid := False;
end;

// ---- Parsing ----

function ManifestHasPath(const M: TManifest; const Path: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 0 to GetArrayLength(M.Files) - 1 do
  begin
    if CompareText(M.Files[I].Path, Path) = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

// Reads one entry of "files". Returns '' or the first problem.
function ParseManifestFile(const Output: TJsonParserOutput; Entry: TJsonValue; Position: Integer; var F: TManifestFile): String;
var
  Name: String;
  Size, Remainder: Double;
  Valid: Boolean;
begin
  Result := '';
  Name := 'files[' + IntToStr(Position) + ']';
  if Entry.Kind <> JVKObject then
  begin
    Result := Name + ' is not an object.';
    Exit;
  end;

  if not JsonGetString(Output, Entry.Index, 'path', F.Path) then
  begin
    Result := Name + '.path is missing or is not text.';
    Exit;
  end;

  if not IsSafePath(F.Path) then
  begin
    Result := Name + '.path is not a safe path: ' + F.Path;
    Exit;
  end;

  if not JsonGetString(Output, Entry.Index, 'url', F.Url) then
  begin
    Result := Name + '.url is missing or is not text.';
    Exit;
  end;

  if not IsAllowedUrl(F.Url) then
  begin
    Result := Name + '.url must start with https://';
    Exit;
  end;

  if not JsonGetNumber(Output, Entry.Index, 'size', Size) then
  begin
    Result := Name + '.size is missing or is not a number.';
    Exit;
  end;

  if (Size < 1) or (Size > ManifestMaxFileSize) then
  begin
    Result := Name + '.size must be a whole number from 1 to 4294967296.';
    Exit;
  end;

  // Size is in range here, so Trunc is safe. A fraction is a different number after Trunc.
  F.Size := Trunc(Size);
  Remainder := Size - F.Size;
  if Remainder <> 0 then
  begin
    Result := Name + '.size must be a whole number from 1 to 4294967296.';
    Exit;
  end;

  if not JsonGetString(Output, Entry.Index, 'sha256', F.Sha256) then
  begin
    Result := Name + '.sha256 is missing or is not text.';
    Exit;
  end;

  if not IsSha256Text(F.Sha256) then
  begin
    Result := Name + '.sha256 must be 64 lowercase hexadecimal digits.';
    Exit;
  end;

  F.OnlyIfMissing := JsonGetBool(Output, Entry.Index, 'onlyIfMissing', False, Valid);
  if not Valid then
    Result := Name + '.onlyIfMissing must be true or false.';
end;

function ParseManifestFolders(const Output: TJsonParserOutput; FoldersValue: TJsonValue; var M: TManifest): String;
var
  I, Count: Integer;
  Item: TJsonValue;
  Path: String;
begin
  Result := '';
  if FoldersValue.Kind <> JVKArray then
  begin
    Result := '"folders" is not a list.';
    Exit;
  end;

  Count := GetArrayLength(Output.Arrays[FoldersValue.Index]);
  if Count > ManifestMaxFolders then
  begin
    Result := '"folders" has too many entries.';
    Exit;
  end;

  for I := 0 to Count - 1 do
  begin
    Item := Output.Arrays[FoldersValue.Index][I];
    if Item.Kind <> JVKString then
    begin
      Result := 'folders[' + IntToStr(I) + '] is not text.';
      Exit;
    end;

    Path := Output.Strings[Item.Index];
    if not IsSafePath(Path) then
    begin
      Result := 'folders[' + IntToStr(I) + '] is not a safe path: ' + Path;
      Exit;
    end;
    AddString(M.Folders, Path);
  end;
end;

// Reads and checks the manifest text. Returns '' if it is good, or a short message for the first problem.
function ParseManifest(const Text: String; var M: TManifest): String;
var
  Json: TJsonParser;
  Schema: Double;
  FilesValue, FoldersValue, Entry: TJsonValue;
  I, Count, N: Integer;
  F: TManifestFile;
begin
  Result := '';
  M.Version := '';
  SetArrayLength(M.Files, 0);
  SetArrayLength(M.Folders, 0);

  if Length(Text) > ManifestMaxChars then
  begin
    Result := 'The manifest is too large.';
    Exit;
  end;

  if Copy(Trim(Text), 1, 1) <> '{' then
  begin
    Result := 'The manifest must be a JSON object.';
    Exit;
  end;

  if JsonDepth(Text) > ManifestMaxDepth then
  begin
    Result := 'The manifest is nested too deeply.';
    Exit;
  end;

  ClearJsonParser(Json);
  ParseJson(Json, Text);
  if GetArrayLength(Json.Output.Errors) > 0 then
  begin
    Result := 'The manifest is not valid JSON.';
    Exit;
  end;

  if not JsonGetNumber(Json.Output, 0, 'schema', Schema) then
  begin
    Result := '"schema" is missing or is not a number.';
    Exit;
  end;

  if Schema <> ManifestSchema then
  begin
    Result := 'This installer reads manifest schema ' + IntToStr(ManifestSchema) + ' only.';
    Exit;
  end;

  if not JsonGetString(Json.Output, 0, 'version', M.Version) then
  begin
    Result := '"version" is missing or is not text.';
    Exit;
  end;

  if (M.Version = '') or (Length(M.Version) > 64) then
  begin
    Result := '"version" must have 1 to 64 characters.';
    Exit;
  end;

  if not JsonFindKey(Json.Output, 0, 'files', FilesValue) then
  begin
    Result := '"files" is missing.';
    Exit;
  end;

  if FilesValue.Kind <> JVKArray then
  begin
    Result := '"files" is not a list.';
    Exit;
  end;

  Count := GetArrayLength(Json.Output.Arrays[FilesValue.Index]);
  if (Count < 1) or (Count > ManifestMaxFiles) then
  begin
    Result := '"files" must have 1 to ' + IntToStr(ManifestMaxFiles) + ' entries.';
    Exit;
  end;

  for I := 0 to Count - 1 do
  begin
    Entry := Json.Output.Arrays[FilesValue.Index][I];
    Result := ParseManifestFile(Json.Output, Entry, I, F);
    if Result <> '' then
      Exit;

    if ManifestHasPath(M, F.Path) then
    begin
      Result := 'files[' + IntToStr(I) + '].path is listed twice: ' + F.Path;
      Exit;
    end;

    N := GetArrayLength(M.Files);
    SetArrayLength(M.Files, N + 1);
    M.Files[N] := F;
  end;

  if JsonFindKey(Json.Output, 0, 'folders', FoldersValue) then
    Result := ParseManifestFolders(Json.Output, FoldersValue, M);
end;
