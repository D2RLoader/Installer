// A window that looks like the pages of Setup: a white header with a title, a short text and the small logo,
// a thin line, a grey body, a thin line, and a bar at the bottom for the buttons (the same grey as the body).
// The uninstaller uses it. The uninstaller cannot use the pages of Setup, because it has no wizard.

const
  DialogHeaderHeight = 58;  // Unscaled sizes. Use ScaleX and ScaleY.
  DialogFooterHeight = 48;
  DialogLogoFile = 'logo.png';  // Setup copies it next to the uninstaller. It is not there in a build without the pictures.

// Loads the small logo into the header. A missing or broken file means no logo. The window works without it.
procedure AddDialogLogo(Form: TSetupForm; const LogoPath: String);
var
  Logo: TBitmapImage;
  Stream: TFileStream;
begin
  if not FileExists(LogoPath) then
    Exit;

  try
    Logo := TBitmapImage.Create(Form);
    Logo.Parent := Form;
    Logo.BackColor := clWindow;
    Logo.Stretch := True;
    Logo.Width := ScaleX(52);
    Logo.Height := ScaleY(50);
    Logo.Left := Form.ClientWidth - Logo.Width - ScaleX(10);
    Logo.Top := ScaleY(4);
    Stream := TFileStream.Create(LogoPath, fmOpenRead);
    try
      Logo.PngImage.LoadFromStream(Stream);
    finally
      Stream.Free;
    end;
  except
    Log('D2RL: the logo for the window did not load: ' + GetExceptionMessage);
    Logo.Visible := False;
  end;
end;

// One line of the frame. The line is a thin text block, because a flat control (a bevel) would be hidden under the body.
procedure AddDialogLine(Form: TSetupForm; Top: Integer; Color: TColor);
var
  Line: TNewStaticText;
begin
  Line := TNewStaticText.Create(Form);
  Line.Parent := Form;
  Line.AutoSize := False;
  Line.Color := Color;
  Line.Left := 0;
  Line.Top := Top;
  Line.Width := Form.ClientWidth;
  Line.Height := 1;
end;

// Makes the frame. BodyTop is where the body starts. FooterTop is where the bar for the buttons starts.
// Put the other controls on the form after this call, so that they are above the grey body.
// The form is white, and that is the header. A grey block (a window-type control) covers the body. The logo is a flat
// control, and a window-type control would hide it, so no block must cover the header.
procedure MakeDialogFrame(Form: TSetupForm; const Title, Description, LogoPath: String; var BodyTop, FooterTop: Integer);
var
  Body, TitleLabel, DescriptionLabel: TNewStaticText;
  HeaderHeight: Integer;
begin
  // The usual frame of a window has the icon of the program. The "dialog" frame of a custom form has none.
  Form.BorderStyle := bsSingle;
  Form.BorderIcons := [biSystemMenu];
  Form.Color := clWindow;
  HeaderHeight := ScaleY(DialogHeaderHeight);

  Body := TNewStaticText.Create(Form);
  Body.Parent := Form;
  Body.AutoSize := False;
  Body.Color := clBtnFace;
  Body.Left := 0;
  Body.Top := HeaderHeight;
  Body.Width := Form.ClientWidth;
  Body.Height := Form.ClientHeight - HeaderHeight;

  AddDialogLine(Form, HeaderHeight, clBtnShadow);
  AddDialogLine(Form, HeaderHeight + 1, clBtnHighlight);

  TitleLabel := TNewStaticText.Create(Form);
  TitleLabel.Parent := Form;
  TitleLabel.Color := clWindow;
  TitleLabel.Left := ScaleX(20);
  TitleLabel.Top := ScaleY(10);
  TitleLabel.Font.Style := [fsBold];
  TitleLabel.Caption := Title;

  DescriptionLabel := TNewStaticText.Create(Form);
  DescriptionLabel.Parent := Form;
  DescriptionLabel.Color := clWindow;
  DescriptionLabel.Left := ScaleX(34);
  DescriptionLabel.Top := ScaleY(28);
  DescriptionLabel.Caption := Description;

  AddDialogLogo(Form, LogoPath);

  BodyTop := HeaderHeight + ScaleY(18);
  FooterTop := Form.ClientHeight - ScaleY(DialogFooterHeight);
  AddDialogLine(Form, FooterTop, clBtnShadow);
  AddDialogLine(Form, FooterTop + 1, clBtnHighlight);
end;
