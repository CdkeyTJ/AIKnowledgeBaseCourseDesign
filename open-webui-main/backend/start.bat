:: CDK edited
@echo off
setlocal enabledelayedexpansion

:: 设置脚本目录为当前目录
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Playwright 浏览器安装（需要管理员权限）
if /i "%WEB_LOADER_ENGINE%"=="playwright" (
    if "%PLAYWRIGHT_WS_URL%"=="" (
        echo Installing Playwright browsers...
        call playwright install chromium
        call playwright install-deps chromium
    )
    python -c "import nltk; nltk.download('punkt_tab')"
)

:: 密钥文件配置
if defined WEBUI_SECRET_KEY_FILE (
    set "KEY_FILE=%WEBUI_SECRET_KEY_FILE%"
) else (
    set "KEY_FILE=.webui_secret_key"
)

:: 端口和主机默认值
if "%PORT%"=="" set PORT=8080
if "%HOST%"=="" set HOST=0.0.0.0

:: 密钥生成逻辑
if "%WEBUI_SECRET_KEY% %WEBUI_JWT_SECRET_KEY%"==" " (
    echo Loading WEBUI_SECRET_KEY from file...
    if not exist "%KEY_FILE%" (
        echo Generating WEBUI_SECRET_KEY
        <NUL set /p= > "%KEY_FILE%"
        for /f "delims=" %%a in ('powershell -Command "$rand=[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(12)); Write-Output $rand"') do (
            set "key=%%a"
        )
        echo !key! > "%KEY_FILE%"
    )
    set /p WEBUI_SECRET_KEY=<"%KEY_FILE%"
)

:: 启动 Ollama 服务
if /i "%USE_OLLAMA_DOCKER%"=="true" (
    echo Starting ollama serve...
    start /B ollama serve
)

:: HuggingFace Space 配置
if defined SPACE_ID (
    echo Configuring for HuggingFace Space...
    if defined ADMIN_USER_EMAIL if defined ADMIN_USER_PASSWORD (
        echo Creating admin user...
        set "WEBUI_SECRET_KEY=%WEBUI_SECRET_KEY%" && start /B uvicorn open_webui.main:app --host %HOST% --port %PORT% --forwarded-allow-ips "*"
        timeout /t 10 >nul
        curl -X POST "http://localhost:8080/api/v1/auths/signup" ^
          -H "accept: application/json" ^
          -H "Content-Type: application/json" ^
          -d "{\"email\": \"%ADMIN_USER_EMAIL%\", \"password\": \"%ADMIN_USER_PASSWORD%\", \"name\": \"Admin\"}"
        taskkill /f /im uvicorn.exe >nul
    )
    set WEBUI_URL=%SPACE_HOST%
)

:: 主服务启动
set PYTHON_CMD=python
where python3 >nul 2>&1 && set PYTHON_CMD=python3

echo Starting main service...
set "WEBUI_SECRET_KEY=%WEBUI_SECRET_KEY%"
%PYTHON_CMD% -m uvicorn open_webui.main:app --host %HOST% --port %PORT% --forwarded-allow-ips "*" --workers %UVICORN_WORKERS%