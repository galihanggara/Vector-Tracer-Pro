; installer/setup.iss
; Enhanced installer with prerequisite check page (Inno Setup Pascal Scripting)

#define AppName "Vector Tracer Pro"
#define AppVersion "1.0.0"
#define AppPublisher "Galih Anggara"
#define AppURL "https://github.com/galihanggara/Vector-Tracer-Pro"
#define InkscapeURL "https://inkscape.org/release/"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
MinVersion=10.0
DefaultDirName={autopf}\VectorTracerPro
DefaultGroupName={#AppName}
OutputDir=output
OutputBaseFilename=VectorTracerPro-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\VectorTracerPro.exe

[Code]
{ =========================================================
  TYPE DECLARATIONS (must come before functions)
  ========================================================= }
type
  TMemoryStatusEx = record
    dwLength: DWORD;
    dwMemoryLoad: DWORD;
    ullTotalPhys: Int64;
    ullAvailPhys: Int64;
    ullTotalPageFile: Int64;
    ullAvailPageFile: Int64;
    ullTotalVirtual: Int64;
    ullAvailVirtual: Int64;
    ullAvailExtendedVirtual: Int64;
  end;

{ =========================================================
  WINDOWS API IMPORTS
  ========================================================= }
function GlobalMemoryStatusEx(var lpBuffer: TMemoryStatusEx): BOOL;
  external 'GlobalMemoryStatusEx@kernel32.dll stdcall';

function GetDiskFreeSpaceExA(lpDirectoryName: AnsiString;
  var lpFreeBytesAvailableToCaller: Int64;
  var lpTotalNumberOfBytes: Int64;
  var lpTotalNumberOfFreeBytes: Int64): BOOL;
  external 'GetDiskFreeSpaceExA@kernel32.dll stdcall';

{ =========================================================
  HELPER FUNCTIONS
  ========================================================= }

{ Cek apakah Inkscape terinstall di system }
function IsInkscapeInstalled(): Boolean;
var
  Path: String;
begin
  Result := False;
  if RegQueryStringValue(HKLM,
    'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\inkscape.exe',
    '', Path) then
  begin
    Result := FileExists(Path);
    Exit;
  end;
  if FileExists(ExpandConstant('{pf}\Inkscape\bin\inkscape.exe')) then
  begin
    Result := True;
    Exit;
  end;
  if FileExists(ExpandConstant('{pf32}\Inkscape\bin\inkscape.exe')) then
  begin
    Result := True;
    Exit;
  end;
end;

{ Total RAM dalam MB }
function GetTotalRAMMB(): Cardinal;
var
  MemStatus: TMemoryStatusEx;
begin
  MemStatus.dwLength := SizeOf(MemStatus);
  if GlobalMemoryStatusEx(MemStatus) then
    Result := Cardinal(MemStatus.ullTotalPhys div 1048576)
  else
    Result := 4096; { Default ke 4GB jika gagal baca }
end;

{ Free disk space di drive tertentu (dalam MB) }
function GetFreeDiskSpaceMB(Drive: AnsiString): Cardinal;
var
  FreeBytes, TotalBytes, TotalFreeBytes: Int64;
begin
  Result := 0;
  if GetDiskFreeSpaceExA(Drive, FreeBytes, TotalBytes, TotalFreeBytes) then
    Result := Cardinal(FreeBytes div 1048576);
end;

{ =========================================================
  GLOBAL VARIABLES
  ========================================================= }
var
  PrereqPage: TWizardPage;
  CanProceed: Boolean;

{ =========================================================
  EVENT HANDLERS
  ========================================================= }
procedure OpenURL(URL: String);
var
  ErrorCode: Integer;
begin
  ShellExec('open', URL, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
end;

procedure InkscapeLinkClick(Sender: TObject);
begin
  OpenURL('{#InkscapeURL}');
end;

{ =========================================================
  CREATE PREREQUISITE PAGE
  ========================================================= }
procedure CreatePrereqPage();
var
  Y: Integer;
  LblTitle, LblSep: TLabel;
  LblWin, LblRAM, LblDisk, LblPotrace, LblInkscape: TLabel;
  LblInkLink, LblInkNote: TLabel;
  RAMOK, DiskOK, InkOK: Boolean;
  RAMMb, DiskMB: Cardinal;
  DriveLetter: AnsiString;
begin
  CanProceed := True;

  PrereqPage := CreateCustomPage(
    wpWelcome,
    'System Requirements Check',
    'Verifying system requirements before installation...'
  );

  Y := 8;

  { --- Section: Required --- }
  LblTitle := TLabel.Create(PrereqPage);
  LblTitle.Parent := PrereqPage.Surface;
  LblTitle.Left := 0;
  LblTitle.Top := Y;
  LblTitle.Width := PrereqPage.SurfaceWidth;
  LblTitle.Caption := 'Required Components';
  LblTitle.Font.Style := [fsBold];
  LblTitle.Font.Size := 10;
  Y := Y + 26;

  { --- Windows 10+ (enforced by MinVersion in [Setup]) --- }
  LblWin := TLabel.Create(PrereqPage);
  LblWin.Parent := PrereqPage.Surface;
  LblWin.Left := 0;
  LblWin.Top := Y;
  LblWin.Width := PrereqPage.SurfaceWidth;
  LblWin.Caption := '[OK]  Windows 10 or later';
  Y := Y + 22;

  { --- RAM check: minimum 2 GB --- }
  RAMMb := GetTotalRAMMB();
  RAMOK := RAMMb >= 2048;
  LblRAM := TLabel.Create(PrereqPage);
  LblRAM.Parent := PrereqPage.Surface;
  LblRAM.Left := 0;
  LblRAM.Top := Y;
  LblRAM.Width := PrereqPage.SurfaceWidth;
  if RAMOK then
    LblRAM.Caption := Format('[OK]  Minimum 2 GB RAM  (%d MB detected)', [RAMMb])
  else begin
    LblRAM.Caption := Format('[FAIL]  Minimum 2 GB RAM  (only %d MB found -- upgrade required)', [RAMMb]);
    LblRAM.Font.Color := clRed;
    CanProceed := False;
  end;
  Y := Y + 22;

  { --- Disk check: minimum 500 MB free --- }
  DriveLetter := Copy(ExpandConstant('{autopf}'), 1, 1) + ':\';
  DiskMB := GetFreeDiskSpaceMB(DriveLetter);
  DiskOK := DiskMB >= 500;
  LblDisk := TLabel.Create(PrereqPage);
  LblDisk.Parent := PrereqPage.Surface;
  LblDisk.Left := 0;
  LblDisk.Top := Y;
  LblDisk.Width := PrereqPage.SurfaceWidth;
  if DiskOK then
    LblDisk.Caption := Format('[OK]  Minimum 500 MB free disk space  (%d MB available)', [DiskMB])
  else begin
    LblDisk.Caption := Format('[FAIL]  Minimum 500 MB free disk space  (only %d MB free)', [DiskMB]);
    LblDisk.Font.Color := clRed;
    CanProceed := False;
  end;
  Y := Y + 30;

  { --- Section: Optional --- }
  LblSep := TLabel.Create(PrereqPage);
  LblSep.Parent := PrereqPage.Surface;
  LblSep.Left := 0;
  LblSep.Top := Y;
  LblSep.Width := PrereqPage.SurfaceWidth;
  LblSep.Caption := 'Optional Components (recommended)';
  LblSep.Font.Style := [fsBold];
  LblSep.Font.Size := 10;
  Y := Y + 26;

  { --- Potrace & VTracer: always bundled --- }
  LblPotrace := TLabel.Create(PrereqPage);
  LblPotrace.Parent := PrereqPage.Surface;
  LblPotrace.Left := 0;
  LblPotrace.Top := Y;
  LblPotrace.Width := PrereqPage.SurfaceWidth;
  LblPotrace.Caption := '[BUNDLED]  Potrace & VTracer  --  included in this installer';
  Y := Y + 22;

  { --- Inkscape: optional --- }
  InkOK := IsInkscapeInstalled();
  LblInkscape := TLabel.Create(PrereqPage);
  LblInkscape.Parent := PrereqPage.Surface;
  LblInkscape.Left := 0;
  LblInkscape.Top := Y;
  LblInkscape.Width := PrereqPage.SurfaceWidth;
  if InkOK then begin
    LblInkscape.Caption :=
      '[OK]  Inkscape  --  detected, complex colour tracing is enabled';
  end else begin
    LblInkscape.Caption :=
      '[OPTIONAL]  Inkscape  --  not found, recommended for best results';
    LblInkscape.Font.Color := $00A07800;
    Y := Y + 22;

    { Clickable download link }
    LblInkLink := TLabel.Create(PrereqPage);
    LblInkLink.Parent := PrereqPage.Surface;
    LblInkLink.Left := 18;
    LblInkLink.Top := Y;
    LblInkLink.Caption := '>> Download Inkscape free at: inkscape.org/release/';
    LblInkLink.Font.Color := clBlue;
    LblInkLink.Font.Style := [fsUnderline];
    LblInkLink.Cursor := crHand;
    LblInkLink.OnClick := @InkscapeLinkClick;
    Y := Y + 20;

    LblInkNote := TLabel.Create(PrereqPage);
    LblInkNote.Parent := PrereqPage.Surface;
    LblInkNote.Left := 18;
    LblInkNote.Top := Y;
    LblInkNote.Width := PrereqPage.SurfaceWidth - 18;
    LblInkNote.Caption :=
      'Without Inkscape, Vector Tracer Pro still works fully using ' +
      'Potrace and VTracer. Inkscape adds a third tracing engine for ' +
      'complex colour photos and illustrations.';
    LblInkNote.WordWrap := True;
    LblInkNote.Font.Color := clGray;
  end;
end;

{ Block Next if required checks failed }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = PrereqPage.ID then
  begin
    if not CanProceed then
    begin
      MsgBox(
        'Installation cannot proceed because system requirements are not met.' +
        Chr(13) + Chr(10) + Chr(13) + Chr(10) +
        'Please fix the items marked red above, then re-run the installer.',
        mbError, MB_OK
      );
      Result := False;
    end;
  end;
end;

procedure InitializeWizard();
begin
  CreatePrereqPage();
end;

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\VectorTracerPro\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\VectorTracerPro.exe"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\VectorTracerPro.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a Desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\VectorTracerPro.exe"; Description: "Launch {#AppName} now"; Flags: postinstall skipifsilent nowait

[UninstallDelete]
Type: dirifempty; Name: "{userappdata}\VectorTracerPro"
