@echo off
rem Запуск GraphBuilder двойным щелчком или из консоли: run.bat [аргументы main.py]
rem Без аргументов открывается интерактивное меню, с аргументами - режим командной строки.
rem Если окружения .venv нет, оно создаётся, зависимости ставятся автоматически.
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONUTF8=1"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo Создаю виртуальное окружение .venv ...
    set "BASE_PY="
    py -3 -c "import sys" >nul 2>&1 && set "BASE_PY=py -3"
    if not defined BASE_PY (
        python -c "import sys" >nul 2>&1 && set "BASE_PY=python"
    )
    if not defined BASE_PY (
        echo Ошибка: Python не найден. Установите Python 3.10 или новее с python.org.
        pause
        exit /b 1
    )
    !BASE_PY! -m venv .venv
    if errorlevel 1 (
        echo Ошибка: не удалось создать окружение .venv.
        pause
        exit /b 1
    )
)

"%VENV_PY%" -c "import networkx, matplotlib" >nul 2>&1
if errorlevel 1 (
    echo Устанавливаю зависимости из requirements.txt ...
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Ошибка: не удалось установить зависимости.
        pause
        exit /b 1
    )
)

"%VENV_PY%" main.py %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo Программа завершилась с кодом %RC%.
    pause
)
exit /b %RC%
