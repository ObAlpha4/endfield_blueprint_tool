@echo off
REM 便捷入口：设置 PYTHONPATH 后转发给 endfield.cli。
REM 用法：tools\endfield.cmd check | build | repeat
setlocal
set "REPO_ROOT=%~dp0.."
set "PYTHONPATH=%REPO_ROOT%\src"
"%REPO_ROOT%\.venv\Scripts\python.exe" -m endfield.cli %*
exit /b %ERRORLEVEL%
