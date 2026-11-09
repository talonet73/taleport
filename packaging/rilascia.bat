@echo off
rem TALeport: test, installer, push e Release in un doppio clic (registro in packaging\output).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0rilascia.ps1"
