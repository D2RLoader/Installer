; The texts of D2RLoader Setup in English. This is the master file. Each other language has a file next to this one,
; with the same names. Inno Setup has its own file for the standard texts (the buttons, "Welcome", and so on).
; A name that is missing in a language shows the English text.
;
; Rules for a translation:
; - Keep the names (the part before "="). Translate only the text after "=".
; - Keep %1 and the other % codes. %1 is replaced by Setup (a version number or a file name).
; - The "&" before a letter in StartMenuIcon marks the key to press. Use a letter that no other text on the same page uses,
;   or leave the "&" out.
; - Use short sentences and common words. Many players do not read English or their own language well.
; - Use the same words as the standard Inno Setup file of the language for "Setup", "Uninstall", "shortcut", and "folder".
; - "Battle.net" and "Steam" are names. Do not translate them.

[Messages]
; The page "Select Additional Tasks" and the question before an uninstall. They replace the standard texts.
SelectTasksLabel2=Select the shortcuts that you want, then click Next.
ConfirmUninstall=Are you sure you want to remove %1? Your own files stay.

[CustomMessages]
; The first pages
WelcomeBody1=This will install D2RLoader on your computer. If D2RLoader is already installed, Setup updates it.
WelcomeBody2=Setup needs an internet connection. Please close the game before you continue.
MaintenanceTitle=Update or Uninstall
MaintenanceDescription=D2RLoader is already installed. What do you want to do?
UpdateName=Update
UpdateLine=Get the newest files. This also fixes files that are damaged or missing.
UninstallName=Uninstall
UninstallLine=Remove D2RLoader from this computer.

; The page "Select Destination Location": three tiles
TilesTitle=Select Destination Location
TilesDescription=Where should D2RLoader be installed?
TilesIntro=Click the place where you want to install D2RLoader.
OtherFolder=Other folder
TileFound=Found
TileInstalled=Installed
TileNotFound=Not found on this PC
TileYouChoose=You choose the folder
SelectDirNote=Setup will install D2RLoader into the folder of Diablo II: Resurrected. This is the folder with the file %1.

; The shortcuts
StartMenuIcon=Create a &Start menu shortcut

; The download page
DownloadTitle=Downloading Files
DownloadDescription=Please wait while Setup downloads D2RLoader.

; The last page
ResultInstalled=Setup has finished installing D2RLoader %1 on your computer.
ResultUpdated=Setup has finished updating D2RLoader to version %1.
ResultAlreadyInstalled=D2RLoader %1 is already installed. No file had to be changed.
SettingsKept=Your settings were not changed.

; The window of the uninstaller
UninstallWindowTitle=Uninstall D2RLoader
UninstallSeveral=D2RLoader is installed in more than one place. Click the one to remove.
UninstallOne=Click Uninstall to remove D2RLoader.
TileWillBeRemoved=Will be removed
TileNotInstalled=Not installed
DeleteSettings=Delete settings and configuration files
DeleteSettingsNote=Your settings are in the folder d2rloader\config. Leave the box empty to keep them. Your mods, plugins, and saved data are never removed.

; Messages and errors. "Details:" is followed by a technical text for a bug report.
Details=Details:
DownloadStopped=The download was stopped.
DownloadFailed=Setup could not download a file. Check your internet connection, then run Setup again.
ManifestUnreadable=Setup could not read the list of files from the website.
ManifestInvalid=The list of files on the website is not correct. Please try again later.
FileNotCorrect=A downloaded file is not correct. Please try again later.
PrepareFailed=Setup could not prepare a file for the installation:
GameNotFound=Setup did not find the game in this folder:
ChooseGameFolder=Choose the folder that has the file %1 in it.
GameOpenRetry=D2RLoader is open. Please close the game. Then click Retry.
GameStillOpen=D2RLoader is still open. Close the game, then run Setup again.
GameCheckFailedAsk=Setup cannot see if the game is open. Is the game closed?
CloseGameThenRun=Close the game, then run Setup again.
UninstallerNotStarted=Setup could not start the uninstaller.
