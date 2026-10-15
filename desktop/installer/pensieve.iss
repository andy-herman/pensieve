; Inno Setup script for the Pensieve installer. Built by build-installer.ps1,
; which passes the paths and version below as /D defines.
;
; Per-user install (no admin prompt) into %LOCALAPPDATA%\Programs\Pensieve.
; The backend is an x64 build, so one installer serves x64 PCs natively and
; ARM64 PCs through Windows' x64 emulation.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef StageDir
  #error StageDir must point at the staged app folder
#endif
#ifndef OutputDir
  #define OutputDir "Output"
#endif

[Setup]
AppId={{6E2E8B9C-5A0B-4E8A-9C1D-2F4A7B3C9D10}
AppName=Pensieve
AppVersion={#AppVersion}
AppVerName=Pensieve {#AppVersion}
AppPublisher=Andy Herman
AppPublisherURL=https://github.com/andy-herman/pensieve
AppSupportURL=https://github.com/andy-herman/pensieve
AppCopyright=Copyright (c) 2026 Andy Herman. MIT License.
DefaultDirName={localappdata}\Programs\Pensieve
DisableDirPage=auto
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir={#OutputDir}
OutputBaseFilename=PensieveSetup-{#AppVersion}
SetupIconFile={#StageDir}\pensieve.ico
UninstallDisplayIcon={app}\pensieve.ico
UninstallDisplayName=Pensieve
WizardStyle=modern
WizardImageFile={#StageDir}\installer-art\wizard-large.bmp
WizardSmallImageFile={#StageDir}\installer-art\wizard-small.bmp
LicenseFile={#StageDir}\LICENSE-AND-PRIVACY.txt
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
AppMutex=Local\PensieveDesktopLauncher
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Pensieve setup

[Messages]
WelcomeLabel2=This installs Pensieve {#AppVersion}, a personal memory layer for your Microsoft To Do tasks.%n%nAfter setup, Pensieve opens a short "Connect your accounts" screen to sign in to Microsoft To Do and GitHub Copilot. Your tasks and sign-ins stay on this PC.

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "copilotcli"; Description: "Install the GitHub Copilot CLI with winget (needed for the AI features; skipped if already installed)"; GroupDescription: "GitHub Copilot:"; Check: CopilotCliMissing

[Files]
Source: "{#StageDir}\Pensieve.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\pensieve.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\pensieve.env"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\LICENSE-AND-PRIVACY.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\THIRD-PARTY-NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\server\*"; DestDir: "{app}\server"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Clear the previous backend build so no stale modules linger after an upgrade.
Type: filesandordirs; Name: "{app}\server"

[Icons]
Name: "{autoprograms}\Pensieve"; Filename: "{app}\Pensieve.exe"; IconFilename: "{app}\pensieve.ico"; Comment: "Pensieve, your work memories in a bowl"
Name: "{autodesktop}\Pensieve"; Filename: "{app}\Pensieve.exe"; IconFilename: "{app}\pensieve.ico"; Tasks: desktopicon

[Run]
Filename: "{code:WingetPath}"; Parameters: "install --id GitHub.Copilot --exact --scope user --silent --accept-package-agreements --accept-source-agreements"; StatusMsg: "Installing the GitHub Copilot CLI (this can take a minute)..."; Flags: runhidden waituntilterminated; Tasks: copilotcli; Check: WingetAvailable
Filename: "{app}\Pensieve.exe"; Description: "Open Pensieve now"; Flags: postinstall nowait skipifsilent

[Code]
function LocalAppData(): String;
begin
  Result := GetEnv('LOCALAPPDATA');
end;

function WingetPath(Param: String): String;
begin
  Result := LocalAppData() + '\Microsoft\WindowsApps\winget.exe';
end;

function WingetAvailable(): Boolean;
begin
  Result := FileExists(WingetPath(''));
end;

function CopilotCliMissing(): Boolean;
begin
  Result := not (FileExists(LocalAppData() + '\Microsoft\WinGet\Links\copilot.exe')
    or FileExists(GetEnv('APPDATA') + '\npm\node_modules\@github\copilot\node_modules\@github\copilot-win32-x64\copilot.exe')
    or FileExists(GetEnv('APPDATA') + '\npm\node_modules\@github\copilot\node_modules\@github\copilot-win32-arm64\copilot.exe'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := LocalAppData() + '\Pensieve';
    if DirExists(DataDir) then
      if SuppressibleMsgBox('Also delete your Pensieve data on this PC?' + #13#10 + #13#10 +
         'This removes your memories, settings, saved sign-ins and logs in ' + DataDir + '.' + #13#10 +
         'Your Microsoft To Do tasks are not affected.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
