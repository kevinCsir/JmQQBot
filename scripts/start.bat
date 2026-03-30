@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0.."
for %%I in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fI"
set "LOAD_ENV_BAT=%ROOT_DIR%\scripts\load_env.bat"
set "VENV_DIR=%ROOT_DIR%\.venv"

if exist "%LOAD_ENV_BAT%" (
  call "%LOAD_ENV_BAT%"
)

where py >nul 2>nul
if %errorlevel%==0 (
  set "SYSTEM_PYTHON=py -3"
  goto :python_found
)

where python >nul 2>nul
if %errorlevel%==0 (
  set "SYSTEM_PYTHON=python"
  goto :python_found
)

echo 未找到 Python，请先安装 Python 3
exit /b 1

:python_found
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo 未找到虚拟环境，正在自动创建 .venv
  call %SYSTEM_PYTHON% -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b %errorlevel%
)

set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "VENV_UVICORN=%VENV_DIR%\Scripts\uvicorn.exe"

if not exist "%VENV_UVICORN%" (
  echo 初始化虚拟环境工具链...
  call "%VENV_PYTHON%" -m ensurepip --upgrade
  if errorlevel 1 exit /b %errorlevel%
)

echo 检查依赖...
call "%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 exit /b %errorlevel%
call "%VENV_PIP%" install -r "%ROOT_DIR%\requirements.txt"
if errorlevel 1 exit /b %errorlevel%

if "%AUTOJM_HOST%"=="" set "AUTOJM_HOST=0.0.0.0"
if "%AUTOJM_PORT%"=="" set "AUTOJM_PORT=8080"

echo 启动 AutoJm: http://%AUTOJM_HOST%:%AUTOJM_PORT%
call "%VENV_UVICORN%" app.main:app --host "%AUTOJM_HOST%" --port "%AUTOJM_PORT%"
exit /b %errorlevel%
