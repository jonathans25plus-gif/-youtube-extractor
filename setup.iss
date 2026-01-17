; Script d'installation pour YouTube Extractor
; Nécessite Inno Setup pour compiler : https://jrsoftware.org/isdl.php

[Setup]
AppName=YouTube Extractor
AppVersion=1.0.2
AppPublisher=Antigravity & Jonathan
; Installation dans AppData pour permettre les mises à jour sans droits admin
DefaultDirName={localappdata}\YouTube Extractor
DefaultGroupName=YouTube Extractor
OutputDir=dist
OutputBaseFilename=YouTubeExtractor_Setup_v1.0.2
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; L'exécutable principal
Source: "dist\YouTubeExtractor.exe"; DestDir: "{app}"; Flags: ignoreversion
; Dossier bin avec FFmpeg (copié récursivement)
Source: "bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YouTube Extractor"; Filename: "{app}\YouTubeExtractor.exe"
Name: "{autodesktop}\YouTube Extractor"; Filename: "{app}\YouTubeExtractor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\YouTubeExtractor.exe"; Description: "{cm:LaunchProgram,YouTube Extractor}"; Flags: nowait postinstall skipifsilent
