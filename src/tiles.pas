// The tiles of the game folder page and of the uninstaller window.
// A tile is a big button with a name ("Battle.net", "Steam", "Other folder") and a short grey text under it.

const
  TileHeight = 84;       // Unscaled sizes. Use ScaleX and ScaleY.
  TileStatusHeight = 18;

// Puts one tile on Parent. Button and Text are the two controls, so that the caller can change them later.
// Number goes into the Tag of the button. Handler runs when the player clicks an enabled tile.
// BackColor is the colour behind the status text: the colour of the page or of the window.
// Folder (can be empty) shows in a tip when the mouse stays over the tile. A path on the tile itself looks crowded.
procedure MakeTile(Parent: TWinControl; Number: Integer; const Name, Status, Folder: String; Enabled: Boolean;
  Left, Top, Width: Integer; BackColor: TColor; Handler: TNotifyEvent; var Button: TNewButton; var Text: TNewStaticText);
begin
  Button := TNewButton.Create(Parent);
  Button.Parent := Parent;
  if Folder <> '' then
  begin
    Button.Hint := Folder;
    Button.ShowHint := True;
  end;
  Button.Left := Left;
  Button.Top := Top;
  Button.Width := Width;
  Button.Height := ScaleY(TileHeight);
  Button.Font.Size := 12;
  Button.Caption := Name;
  Button.Tag := Number;
  Button.Enabled := Enabled;
  Button.OnClick := Handler;

  Text := TNewStaticText.Create(Parent);
  Text.Parent := Parent;
  Text.AutoSize := False;
  Text.Alignment := taCenter;
  Text.Left := Left;
  Text.Top := Top + Button.Height + ScaleY(6);
  Text.Width := Width;
  Text.Height := ScaleY(TileStatusHeight);
  Text.Font.Color := clGrayText;
  Text.Color := BackColor;
  Text.Caption := Status;
end;
