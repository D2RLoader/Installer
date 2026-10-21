// Finds running programs by file name. It asks WMI, so it starts no other program
// and does not depend on the bit size of the installer.
// If WMI is not available, the functions return False. The caller then does not know the answer.

const
  LoaderExe = 'D2RLoader.exe';

// The full path of every running program with this file name. A path is '' if Windows hides it.
function FindProcessPaths(const ExeName: String; var Paths: TArrayOfString): Boolean;
var
  Locator, Wmi, Items, Item, ExePath: Variant;
  I: Integer;
  S: String;
begin
  Result := False;
  SetArrayLength(Paths, 0);
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Wmi := Locator.ConnectServer('.', 'root\CIMV2');
    Items := Wmi.ExecQuery('SELECT ProcessId, ExecutablePath FROM Win32_Process WHERE Name = ''' + ExeName + '''');
    for I := 0 to Items.Count - 1 do
    begin
      Item := Items.ItemIndex(I);
      ExePath := Item.ExecutablePath;
      S := '';
      if not VarIsNull(ExePath) then
        S := ExePath;
      AddString(Paths, S);
    end;
    Result := True;
  except
    SetArrayLength(Paths, 0);
  end;
end;

function SameFilePath(const A, B: String): Boolean;
var
  X, Y: String;
begin
  X := A;
  Y := B;
  StringChangeEx(X, '/', '\', True);
  StringChangeEx(Y, '/', '\', True);
  Result := CompareText(X, Y) = 0;
end;

// Is D2RLoader.exe running from this game folder? A copy in another folder does not matter,
// because it does not lock the files in this folder. If Windows hides the path of a copy, we count it.
// Result is False if the answer is unknown (WMI failed).
function IsLoaderRunning(const GameDir: String; var Running: Boolean): Boolean;
var
  Paths: TArrayOfString;
  I: Integer;
  Target: String;
begin
  Running := False;
  Result := FindProcessPaths(LoaderExe, Paths);
  if not Result then
    Exit;

  Target := AddBackslash(GameDir) + LoaderExe;
  for I := 0 to GetArrayLength(Paths) - 1 do
  begin
    if Paths[I] = '' then
      Running := True
    else if SameFilePath(Paths[I], Target) then
      Running := True;
  end;
end;
