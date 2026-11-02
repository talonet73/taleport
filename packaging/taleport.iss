; Inno Setup 6 script: per-user installer for TALeport (no administrator rights).
; Built by packaging/build.ps1, which passes /DAppVersion=x.y.z.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppURL
  #define AppURL "https://github.com/"
#endif
#define AppName "TALeport"
#define AppExe "TALeport.exe"
#define Root ".."

[Setup]
AppId={{6F2C9E8A-3B71-4D2E-9C55-7A1E0B4D8F21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Root}\packaging\output
OutputBaseFilename=Setup-{#AppName}
SetupIconFile={#Root}\assets\brand\taleport.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; The running app holds this mutex: setup and uninstall ask to close it first.
AppMutex=Local\TALeport.SingleInstance
CloseApplications=yes
ShowLanguageDialog=auto
; Code signing hook: build.ps1 adds /DSignTool when a certificate is configured.
#ifdef SignTool
SignTool={#SignTool}
SignedUninstaller=yes
#endif

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
it.RemoveData=Vuoi eliminare anche i tuoi dati di TALeport (argomenti, notizie raccolte, bozze, report e impostazioni)?%n%nScegli «No» per conservarli e ritrovarli se reinstalli l'app. Le chiavi API restano nel Gestore credenziali di Windows.
en.RemoveData=Do you also want to delete your TALeport data (topics, collected news, drafts, reports and settings)?%n%nChoose "No" to keep it and find it again if you reinstall the app. API keys stay in Windows Credential Manager.
es.RemoveData=¿Quieres eliminar también tus datos de TALeport (temas, noticias recogidas, borradores, informes y ajustes)?%n%nElige «No» para conservarlos y recuperarlos si reinstalas la app. Las claves API se quedan en el Administrador de credenciales de Windows.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Root}\dist\TALeport\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    { "Start with Windows" entry written by the app itself }
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
  end;
  if CurUninstallStep = usPostUninstall then
  begin
    if (not UninstallSilent) and
       (MsgBox(CustomMessage('RemoveData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      DelTree(ExpandConstant('{localappdata}\{#AppName}'), True, True, True);
  end;
end;
