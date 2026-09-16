@echo off
chcp 65001 > nul
cd /d %~dp0
python audio-size-merger.py
pause