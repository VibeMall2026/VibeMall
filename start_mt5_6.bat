@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File ".\run_mt5_multi_instance.ps1" start

