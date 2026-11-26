@echo off
chcp 65001 >nul
setlocal
echo ==============================================
echo  富江破甲 ^| Eta 一键卸载
echo ==============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1" %*
if errorlevel 1 (
  echo.
  echo [X] 卸载失败，看上面报错。
) else (
  echo.
  echo [OK] 卸载完成，重新打包即回到原版 Eta。
)
echo.
pause
