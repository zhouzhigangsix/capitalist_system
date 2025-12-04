#!/bin/bash

# ============================================
# Quick Deploy Script - 快速部署脚本
# ============================================
# 用途: 快速更新服务器上的代码并重启服务
# 使用: bash deploy/quick-deploy.sh
# ============================================

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 服务器配置
SERVER_IP="139.155.158.47"
SERVER_USER="root"
DEPLOY_DIR="/opt/tdx-stock"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  快速部署工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 获取项目根目录
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)

echo -e "${YELLOW}[1/3] 上传项目文件...${NC}"
rsync -avz --delete \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='data' \
    --exclude='*.db' \
    --exclude='*.csv' \
    --exclude='.DS_Store' \
    --exclude='__pycache__' \
    "${PROJECT_ROOT}/" \
    "${SERVER_USER}@${SERVER_IP}:${DEPLOY_DIR}/"

echo -e "${GREEN}✓ 文件上传完成${NC}\n"

echo -e "${YELLOW}[2/3] 重新构建并启动服务...${NC}"
ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH
    cd ${DEPLOY_DIR}
    docker-compose down
    docker-compose build
    docker-compose up -d
    sleep 5
    docker-compose ps
ENDSSH

echo -e "${GREEN}✓ 服务重启完成${NC}\n"

echo -e "${YELLOW}[3/3] 检查服务状态...${NC}"
if curl -s http://${SERVER_IP}:8080/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 服务运行正常${NC}"
else
    echo -e "${YELLOW}警告: 服务可能未正常启动${NC}"
fi

echo ""
echo -e "${GREEN}部署完成！${NC}"
echo -e "服务地址: ${BLUE}http://${SERVER_IP}${NC}"
echo ""
