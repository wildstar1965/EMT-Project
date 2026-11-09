@echo off
setlocal
pushd "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Create the Python environment using README.md first.
  pause
  popd
  exit /b 1
)
".venv\Scripts\python.exe" -m airdesk demo
if errorlevel 1 pause
popd
endlocal
