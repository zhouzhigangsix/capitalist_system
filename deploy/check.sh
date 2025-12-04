#!/bin/bash

# ============================================
# Pre-deployment Check Script
# ============================================
# 用途: 部署前的环境检查
# 使用: bash deploy/check.sh
# ============================================

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  部署前环境检查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

PASS=0
FAIL=0

# 检查本地工具
echo -e "${YELLOW}检查本地工具...${NC}"

if command -v git &> /dev/null; then
    echo -e "${GREEN}✓${NC} Git: $(git --version)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} Git 未安装"
    FAIL=$((FAIL + 1))
fi

if command -v ssh &> /dev/null; then
    echo -e "${GREEN}✓${NC} SSH: $(ssh -V 2>&1 | head -n1)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} SSH 未安装"
    FAIL=$((FAIL + 1))
fi

if command -v rsync &> /dev/null; then
    echo -e "${GREEN}✓${NC} Rsync: $(rsync --version | head -n1)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} Rsync 未安装"
    FAIL=$((FAIL + 1))
fi

if command -v curl &> /dev/null; then
    echo -e "${GREEN}✓${NC} Curl: $(curl --version | head -n1)"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} Curl 未安装"
    FAIL=$((FAIL + 1))
fi

echo ""

# 检查服务器连接
echo -e "${YELLOW}检查服务器连接...${NC}"

SERVER_IP="139.155.158.47"
SERVER_USER="root"

if ping -c 1 -W 2 ${SERVER_IP} &> /dev/null; then
    echo -e "${GREEN}✓${NC} 服务器网络可达"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} 无法 ping 通服务器"
    FAIL=$((FAIL + 1))
fi

if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} "echo 'test'" &> /dev/null; then
    echo -e "${GREEN}✓${NC} SSH 连接成功"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} SSH 连接失败"
    echo -e "${YELLOW}  提示: 运行 ssh-copy-id ${SERVER_USER}@${SERVER_IP} 配置密钥${NC}"
    FAIL=$((FAIL + 1))
fi

echo ""

# 检查项目文件
echo -e "${YELLOW}检查项目文件...${NC}"

if [ -f "docker-compose.yml" ]; then
    echo -e "${GREEN}✓${NC} docker-compose.yml 存在"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} docker-compose.yml 不存在"
    FAIL=$((FAIL + 1))
fi

if [ -f "Dockerfile" ]; then
    echo -e "${GREEN}✓${NC} Dockerfile 存在"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} Dockerfile 不存在"
    FAIL=$((FAIL + 1))
fi

if [ -d "web" ]; then
    echo -e "${GREEN}✓${NC} web 目录存在"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} web 目录不存在"
    FAIL=$((FAIL + 1))
fi

if [ -f "deploy/nginx.conf" ]; then
    echo -e "${GREEN}✓${NC} Nginx 配置文件存在"
    PASS=$((PASS + 1))
else
    echo -e "${RED}✗${NC} Nginx 配置文件不存在"
    FAIL=$((FAIL + 1))
fi

echo ""

# 显示结果
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  检查结果${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}通过: ${PASS}${NC}"
echo -e "${RED}失败: ${FAIL}${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过！可以开始部署${NC}"
    echo -e "运行: ${BLUE}bash deploy/server-deploy.sh${NC}"
    exit 0
else
    echo -e "${RED}✗ 部分检查失败，请先解决上述问题${NC}"
    exit 1
fi
