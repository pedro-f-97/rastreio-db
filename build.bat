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
if exist "%BACKEND%\frontend_dist" rmdir /s /q "%BACKEND%\frontend_dist"
xcopy /e /i /q "%FRONTEND%\dist" "%BACKEND%\frontend_dist"

:: 3. Instalar PyInstaller no venv
cd "%BACKEND%"
call venv\Scripts\activate.bat
pip install pyinstaller --quiet

:: 4. Executar PyInstaller
echo.
echo  A empacotar com PyInstaller...
pyinstaller ^
  --noconfirm ^
  --onedir ^
  --name rastreio-db ^
  --add-data "frontend_dist;frontend_dist" ^
  --add-data "routers;routers" ^
  main.py
if errorlevel 1 goto erro

:: 5. Organizar output final
echo.
echo A organizar pasta de distribuição...
if exist "%DIST%" rmdir /s /q "%DIST%"
mkdir "%DIST%"
xcopy /e /i /q "%BACKEND%\dist\rastreio-db" "%DIST%"
mkdir "%DIST%\dados"

:: 6. Limpeza
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