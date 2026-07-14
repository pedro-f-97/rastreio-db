@echo off
setlocal
set RAIZ=%~dp0
set BACKEND=%RAIZ%backend
set FRONTEND=%RAIZ%frontend
set DIST=%RAIZ%dist_executavel

echo Início do build — rastreio-db

:: 1. Build do frontend
echo.
echo A compilar frontend...
cd "%FRONTEND%"
call npm run build
if errorlevel 1 goto erro

:: 2. Copiar frontend compilado para dentro do backend
echo.
echo A copiar frontend_dist para o backend...
if not exist "%FRONTEND%\dist" (
    echo ERRO: %FRONTEND%\dist nao existe!
    goto erro
)
if exist "%BACKEND%\frontend_dist" rmdir /s /q "%BACKEND%\frontend_dist"
xcopy /e /i /q "%FRONTEND%\dist" "%BACKEND%\frontend_dist"
if errorlevel 1 goto erro

:: 3. Criar venv se não existir
cd "%BACKEND%"
if not exist "venv" (
    echo.
    echo Venv nao encontrado. A criar ambiente virtual...
    python -m venv venv
    if errorlevel 1 goto erro
    echo Venv criado com sucesso.
)

:: 4. Instalar dependências e PyInstaller
echo.
echo A instalar dependencias...
call venv\Scripts\activate.bat
venv\Scripts\pip install -r requirements.txt --quiet
if errorlevel 1 goto erro
venv\Scripts\pip install pyinstaller --quiet
if errorlevel 1 goto erro

:: 5. Executar PyInstaller
echo.
echo A empacotar com PyInstaller...
venv\Scripts\pyinstaller ^
  --noconfirm ^
  --onedir ^
  --name rastreio-db ^
  --add-data "frontend_dist;frontend_dist" ^
  --add-data "routers;routers" ^
  --add-data "assets;assets" ^
  --hidden-import tkinter ^
  --icon "%FRONTEND%\public\favicon.ico" ^
  --windowed ^
  main.py
if errorlevel 1 goto erro

:: 6. Organizar output final
echo.
echo A organizar pasta de distribuição...
if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"
xcopy /e /i /q "%BACKEND%\dist\rastreio-db" "%DIST%"
if errorlevel 1 goto erro
mkdir "%DIST%\dados"

:: 7. Limpeza
if exist "%BACKEND%\build" rmdir /s /q "%BACKEND%\build"
if exist "%BACKEND%\dist" rmdir /s /q "%BACKEND%\dist"
if exist "%BACKEND%\rastreio-db.spec" del "%BACKEND%\rastreio-db.spec"
if exist "%BACKEND%\frontend_dist" rmdir /s /q "%BACKEND%\frontend_dist"

echo.
echo Build concluído!
echo    Pasta: %DIST%
echo    Para executar: %DIST%\rastreio-db.exe
goto fim

:erro
echo.
echo Erro durante o build.
exit /b 1

:fim
endlocal