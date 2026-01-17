; Script d'installation pour Media Extractor
; Nécessite Inno Setup pour compiler : https://jrsoftware.org/isdl.php

[Setup]
AppName=Media Extractor
AppVersion=1.0.2
AppPublisher=Jonathan Paul & Antigravity
; Installation dans Program Files (nécessite droits admin)
DefaultDirName={autopf}\Media Extractor
DefaultGroupName=Media Extractor
OutputDir=dist
OutputBaseFilename=MediaExtractor_Setup_v1.0.2
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
; Force les droits administrateur
PrivilegesRequired=admin
; Permettre la mise à jour par remplacement
AllowNoIcons=yes
UninstallDisplayIcon={app}\YouTubeExtractor.exe

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; L'exécutable principal
Source: "dist\YouTubeExtractor.exe"; DestDir: "{app}"; Flags: ignoreversion
; Dossier bin avec FFmpeg (copié récursivement)
Source: "bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Media Extractor"; Filename: "{app}\YouTubeExtractor.exe"
Name: "{autodesktop}\Media Extractor"; Filename: "{app}\YouTubeExtractor.exe"; Tasks: desktopicon
Name: "{group}\Désinstaller Media Extractor"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\YouTubeExtractor.exe"; Description: "{cm:LaunchProgram,Media Extractor}"; Flags: nowait postinstall skipifsilent

[Code]
// Fermer l'application avant la mise à jour
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  // Tuer le processus si en cours d'exécution
  Exec('taskkill', '/F /IM YouTubeExtractor.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
