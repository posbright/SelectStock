@echo off
REM InStock Docker 构建脚本 (Windows版) v2.2
REM 使用方法: build.bat
REM
REM 新功能支持:
REM - 多数据源自动切换（新浪/腾讯/东方财富）
REM - 历史数据增量缓存
REM - 环境变量配置
REM - 兼容 Debian 11/12 apt源配置

set VERSION=2.2

echo ==============================================
echo InStock Docker 构建脚本 v%VERSION%
echo ==============================================
echo.

REM 清理旧文件
echo [1/5] 清理旧文件...
if exist stock rmdir /s /q stock
if exist cron rmdir /s /q cron

REM 复制项目文件
echo [2/5] 复制项目文件...
mkdir stock
xcopy /E /I /Y ..\..\* stock\ /EXCLUDE:exclude.txt

REM 复制cron配置
echo [3/5] 复制cron配置...
xcopy /E /I /Y ..\..\cron cron\

REM 创建config目录
if not exist config mkdir config
if not exist config\proxy.txt echo. > config\proxy.txt

REM 构建Docker镜像
set DOCKER_NAME=instock
for /f "tokens=1-3 delims=/" %%a in ('date /t') do set TAG1=%%c%%a%%b
set TAG2=latest

echo [4/5] 构建Docker镜像...
echo 镜像名称: %DOCKER_NAME%:%TAG1%, %DOCKER_NAME%:%TAG2%
docker build -f Dockerfile -t %DOCKER_NAME%:%TAG1% -t %DOCKER_NAME%:%TAG2% .

echo.
echo ==============================================
echo 构建完成!
echo ==============================================
echo.
echo 镜像信息:
docker images | findstr %DOCKER_NAME%
echo.
echo 运行方式:
echo   1. 使用docker-compose (推荐):
echo      copy .env.example .env
echo      docker-compose up -d
echo.
echo   2. 单独运行容器:
echo      docker run -d -p 9988:9988 --name instock %DOCKER_NAME%:%TAG2%
echo.

pause
