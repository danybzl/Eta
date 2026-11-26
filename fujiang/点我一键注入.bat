@echo off
chcp 65001 >nul
setlocal
echo ==============================================
echo  富江破甲 ^| Eta 一键注入
echo ==============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
if errorlevel 1 (
  echo.
  echo [X] 注入失败，看上面报错。常见原因：没装 Python 3，或者这层目录不是 Eta 仓库根。
) else (
  echo.
  echo [OK] 注入完成。按上面的提示去打包 APK。
)
echo.
pause
