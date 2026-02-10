; Inno Setup script for LaConcorde (Windows installer)
; Build with: iscc /DAppVersion=0.1.0 installer\windows\laconcorde.iss

#define AppName "LaConcorde"
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppExeName "laconcorde_gui.exe"
#define AppPublisher "LaConcorde"

[Setup]
AppId={{0E5A7C2E-0C33-4D49-9F7E-5F3C1D0F9E8A}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
OutputDir={#SourcePath}\..\..\dist\installer
OutputBaseFilename=LaConcordeSetup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; Flags: unchecked

[Files]
Source: "{#SourcePath}\..\..\dist\laconcorde_gui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
