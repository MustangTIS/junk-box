@echo off
chcp 65001 > nul
cd /d %~dp0

echo 必要なライブラリの確認中...

:: 必要なライブラリ（requests, bs4, pyvis）が導入済みかチェック
python -c "import requests, bs4, pyvis" > nul 2>&1
if %errorlevel% neq 0 (
    echo ライブラリが見つかりません。初回セットアップ（インストール）を実行します...
    python -m pip install --upgrade pip
    python -m pip install requests beautifulsoup4 pyvis
    echo セットアップが完了しました。
    echo.
) else (
    echo ライブラリ確認完了（スキップします）。
)

echo スクリプトを起動します...
python link_map.py

pause