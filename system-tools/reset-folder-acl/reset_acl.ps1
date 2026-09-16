# 管理者権限で実行されているかチェックし、違えば昇格して再起動する
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "アクセス権をリセットしたいフォルダを選択してください。"

if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    $target = $dialog.SelectedPath
    
    $confirmation = [System.Windows.Forms.MessageBox]::Show(
        "以下のフォルダに対してアクセス権のリセットと設定を行いますか？`n`n$target", 
        "確認", 
        [System.Windows.Forms.MessageBoxButtons]::YesNo, 
        [System.Windows.Forms.MessageBoxIcon]::Question
    )

    if ($confirmation -eq [System.Windows.Forms.DialogResult]::Yes) {
        Write-Host "処理を実行中..." -ForegroundColor Cyan

        # 1. 所有者の取得とリセット
        Start-Process takeown.exe -ArgumentList "/f `"$target`" /r /d y" -Wait -NoNewWindow
        Start-Process icacls.exe -ArgumentList "`"$target`" /reset /t /c /l /q" -Wait -NoNewWindow

        # 2. Administrators と SYSTEM のフルコントロール付与
        Start-Process icacls.exe -ArgumentList "`"$target`" /grant `"Administrators:(OI)(CI)F`" /t /c /l /q" -Wait -NoNewWindow
        Start-Process icacls.exe -ArgumentList "`"$target`" /grant `"SYSTEM:(OI)(CI)F`" /t /c /l /q" -Wait -NoNewWindow

        [System.Windows.Forms.MessageBox]::Show("処理が完了しました。", "完了", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)
    }
}