@echo off
chcp 65001 > nul
cd /d %~dp0
python Automation_Sitemaps.py
pause