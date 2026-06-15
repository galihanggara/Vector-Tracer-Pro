; Inno Setup Script for Vector Tracer Pro
; ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
; This script generates the installer package for Windows.

[Setup]
AppName=Vector Tracer Pro
AppVersion=1.0.0
AppPublisher=Vector Tracer Pro Team
AppPublisherURL=https://github.com/your-org/vector-tracer-pro
MinVersion=10.0
DefaultDirName={autopf}\VectorTracerPro
DefaultGroupName=Vector Tracer Pro
OutputDir=output
OutputBaseFilename=VectorTracerPro-Setup-1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest    ; Install in user folders without requiring local administrator rights

[Files]
Source: "..\dist\VectorTracerPro\*"; \
  DestDir: "{app}"; \
  Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Vector Tracer Pro"; \
  Filename: "{app}\VectorTracerPro.exe"
Name: "{commondesktop}\Vector Tracer Pro"; \
  Filename: "{app}\VectorTracerPro.exe"; \
  Tasks: desktopicon

[Tasks]
Name: "desktopicon"; \
  Description: "Create desktop shortcut"; \
  Flags: unchecked

[Run]
Filename: "{app}\VectorTracerPro.exe"; \
  Description: "Launch Vector Tracer Pro now"; \
  Flags: postinstall skipifsilent

[UninstallDelete]
; Hapus preset dan config user saat uninstall — optional, tanya user dulu
Type: dirifempty; Name: "{userappdata}\VectorTracerPro"
