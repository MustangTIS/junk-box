@echo off
chcp 65001 > nul
cd /d %~dp0
python flac-mp3-cleaner.py
pause