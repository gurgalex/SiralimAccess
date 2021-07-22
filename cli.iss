; Script generated by the Inno Setup Script Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

#define AppIniFile SourcePath + '\setup.cfg'
#define AppIniSection "custom"
#define MyAppExeName ReadIni(AppIniFile, AppIniSection, 'exe_name')
#define MyAppName ReadIni(AppIniFile, AppIniSection, 'product_name')
#define InternalName ReadIni(AppIniFile, AppIniSection, 'internal_name')

#define PathToBinary "dist\Siralim Access\" + MyAppExeName;
#define MyVersionInfoVersion GetStringFileInfo(PathToBinary, FILE_VERSION)

; Misuse RemoveFileExt to strip the 4th patch-level version number.
#define MyAppVersion RemoveFileExt(MyVersionInfoVersion)


#define MyAppPublisher GetStringFileInfo(PathToBinary, COMPANY_NAME)
#define MyAppFilePrefix InternalName + "-windows"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{2EB082C4-54CD-49EC-B81D-14689BCA50B4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename={#MyAppFilePrefix}-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#MyVersionInfoVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: {#PathToBinary}; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Siralim Access\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{tmp}\tesseract-ocr-w64-setup-v5.0.0-alpha.20210506.exe"; DestDir: "{app}"; Flags: external skipifsourcedoesntexist

; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[code]

function IsTesseractInstalled(): Boolean;
begin;
    Result := RegKeyExists(HKA64, 'SOFTWARE\Tesseract-OCR');
 end;





[Code]
var
  DownloadPage: TDownloadWizardPage;
  OCRFontChoicePage: TInputOptionWizardPage;


function CheckOCR(): Boolean;
begin
	Result := OCRFontChoicePage.Values[0];
end;
	
function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if Progress = ProgressMax then
    Log(Format('Successfully downloaded file to {tmp}: %s', [FileName]));
  Result := True;
end;

procedure InitializeWizard;
var
// ID of page to attach next page to
    AfterID: Integer;

begin
  AfterID := wpSelectDir
  OCRFontChoicePage := CreateInputOptionPage(AfterID, 'Install OCR font', '', '', False, False);
  OCRFontChoicePage.Description := 'Arial Bold will be used to improve OCR results in Siralim Ultimate.' + #13#10 +
  'Note: This font is required for realm quest detection to work.';
  
  OCRFontChoicePage.Add('Install OCR friendly font in Siralim Ultimate?');
  OCRFontChoicePage.Values[0] := True;

  AfterID := OCRFontChoicePage.ID;

  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), @OnDownloadProgress);


end;



function NextButtonClick(CurPageID: Integer): Boolean;
begin
  if IsTesseractInstalled() then begin
  Result := True;
  DownloadPage.Hide;
  exit;
  end;

  if CurPageID = wpReady then begin
    DownloadPage.Clear;
    DownloadPage.Add('https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-v5.0.0-alpha.20210506.exe', 'tesseract-ocr-w64-setup-v5.0.0-alpha.20210506.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        Result := True;
      except
        SuppressibleMsgBox(AddPeriod(GetExceptionMessage), mbCriticalError, MB_OK, IDOK);
        Result := False;
      end;
    finally
      DownloadPage.Hide;
    end;
  end else
    Result := True;
end;


[Run]
Filename: "{app}\tesseract-ocr-w64-setup-v5.0.0-alpha.20210506.exe"; Parameters: ""; Flags: waituntilterminated; Check: not IsTesseractInstalled ; StatusMsg: "Tesseract OCR installation. Please wait..."

Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: postinstall 

; install font
Filename: "{app}\{#MyAppExeName}"; Parameters: "install"; Description: "Installer for OCR font"; Check: CheckOCR 


// uninstall code

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;

begin
  if CurUninstallStep = usAppMutexCheck then
  begin
    if MsgBox('Do you want to restore the original game font?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      Exec(ExpandConstant('{app}\{#MyAppExeName}'), 'restore', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
			begin
				Case ResultCode of
					0: Log('Restore original font succeeeded.');
					2: Log('Missing backup font file. Failed to restore original font file.');
				else
					Log('Restoring original game font failed. ErrCode: ' + IntToStr(ResultCode));
			end;
    end;
end;
  end;
end;