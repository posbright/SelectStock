#!/bin/bash

# InStock Docker 构建脚本 v2.1
# 使用方法: ./build.sh [push]
# 参数 push: 可选，构建后推送到Docker Hub
#
# 新功能支持:
# - 多数据源自动切换（新浪/腾讯/东方财富）
# - 历史数据增量缓存
# - 环境变量配置

set -e

VERSION="2.1"

echo "=============================================="
echo "InStock Docker 构建脚本 v${VERSION}"
echo "=============================================="
echo ""

# 清理旧文件
echo "[1/5] 清理旧文件..."
rm -rf stock
rm -rf cron

# 复制项目文件
echo "[2/5] 复制项目文件..."
mkdir -p stock
rsync -av --progress ../../ ./stock \
    --exclude .git \
    --exclude .idea \
    --exclude .vscode \
    --exclude .venv \
    --exclude __pycache__ \
    --exclude '*.pyc' \
    --exclude .gitignore \
    --exclude docker \
    --exclude img \
    --exclude '*.md' \
    --exclude '*.bat' \
    --exclude 'instock/cache/*' \
    --exclude 'instock/log/*' \
    --exclude 'instock/fontWeb/node_modules' \
    --exclude 'instock/fontWeb/dist'

# 复制cron配置
echo "[3/5] 复制cron配置..."
cp -r ../../cron .

# 创建config目录（如果不存在）
mkdir -p config
touch config/proxy.txt

# 构建Docker镜像
DOCKER_NAME=instock
TAG1=$(date "+%Y%m%d")
TAG2=latest

echo "[4/5] 构建Docker镜像..."
echo "镜像名称: ${DOCKER_NAME}:${TAG1}, ${DOCKER_NAME}:${TAG2}"
docker build -f Dockerfile -t ${DOCKER_NAME}:${TAG1} -t ${DOCKER_NAME}:${TAG2} .

echo ""
echo "=============================================="
echo "构建完成!"
echo "=============================================="
echo ""
echo "镜像信息:"
docker images | grep ${DOCKER_NAME}
echo ""
echo "运行方式:"
echo "  1. 使用docker-compose (推荐):"
echo "     cp .env.example .env"
echo "     docker-compose up -d"
echo ""
echo "  2. 单独运行容器:"
echo "     docker run -d -p 9988:9988 --name instock ${DOCKER_NAME}:${TAG2}"
echo ""

# 可选：推送到Docker Hub
if [ "$1" == "push" ]; then
    REMOTE_NAME=mayanghua/instock
    echo "[5/5] 推送到Docker Hub..."
    docker tag ${DOCKER_NAME}:${TAG1} ${REMOTE_NAME}:${TAG1}
    docker tag ${DOCKER_NAME}:${TAG2} ${REMOTE_NAME}:${TAG2}
    docker push ${REMOTE_NAME}:${TAG1}
    docker push ${REMOTE_NAME}:${TAG2}
    echo "推送完成: ${REMOTE_NAME}:${TAG1}, ${REMOTE_NAME}:${TAG2}"
fi