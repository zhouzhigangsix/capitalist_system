#!/bin/bash

# ============================================
# TDX Stock System - Server Deployment Script
# ============================================
# 用途: 一键部署到生产服务器
# 使用: bash deploy/server-deploy.sh
# ============================================

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 服务器配置
SERVER_IP="139.155.158.47"
SERVER_USER="root"
SERVER_PORT="22"
DEPLOY_DIR="/opt/tdx-stock"
PROJECT_NAME="tdx-api"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  TDX Stock System - 服务器部署工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查必要的工具
check_tools() {
    echo -e "${YELLOW}[1/7] 检查本地工具...${NC}"

    if ! command -v git &> /dev/null; then
        echo -e "${RED}错误: 未安装 git${NC}"
        exit 1
    fi

    if ! command -v ssh &> /dev/null; then
        echo -e "${RED}错误: 未安装 ssh${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ 本地工具检查完成${NC}\n"
}

# 测试服务器连接
test_connection() {
    echo -e "${YELLOW}[2/7] 测试服务器连接...${NC}"

    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${SERVER_USER}@${SERVER_IP} "echo 'SSH连接成功'" &> /dev/null; then
        echo -e "${GREEN}✓ 服务器连接正常${NC}\n"
    else
        echo -e "${RED}错误: 无法连接到服务器 ${SERVER_IP}${NC}"
        echo -e "${YELLOW}请确保:${NC}"
        echo -e "  1. 服务器IP地址正确"
        echo -e "  2. SSH服务已启动"
        echo -e "  3. 已配置SSH密钥或输入密码"
        exit 1
    fi
}

# 在服务器上安装必要的软件
install_dependencies() {
    echo -e "${YELLOW}[3/7] 在服务器上安装必要软件...${NC}"

    ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
        # 更新包管理器
        if command -v apt-get &> /dev/null; then
            echo "检测到 Ubuntu/Debian 系统"
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -qq

            # 安装 Docker
            if ! command -v docker &> /dev/null; then
                echo "安装 Docker..."
                apt-get install -y -qq docker.io docker-compose
                systemctl enable docker
                systemctl start docker
            else
                echo "Docker 已安装"
            fi

            # 安装 Nginx
            if ! command -v nginx &> /dev/null; then
                echo "安装 Nginx..."
                apt-get install -y -qq nginx
                systemctl enable nginx
            else
                echo "Nginx 已安装"
            fi

            # 安装 Certbot (用于SSL证书)
            if ! command -v certbot &> /dev/null; then
                echo "安装 Certbot..."
                apt-get install -y -qq certbot python3-certbot-nginx
            else
                echo "Certbot 已安装"
            fi

        elif command -v yum &> /dev/null; then
            echo "检测到 CentOS/RHEL 系统"
            yum update -y -q

            # 安装 Docker
            if ! command -v docker &> /dev/null; then
                echo "安装 Docker..."
                yum install -y -q docker docker-compose
                systemctl enable docker
                systemctl start docker
            else
                echo "Docker 已安装"
            fi

            # 安装 Nginx
            if ! command -v nginx &> /dev/null; then
                echo "安装 Nginx..."
                yum install -y -q nginx
                systemctl enable nginx
            else
                echo "Nginx 已安装"
            fi

            # 安装 Certbot
            if ! command -v certbot &> /dev/null; then
                echo "安装 Certbot..."
                yum install -y -q certbot python3-certbot-nginx
            else
                echo "Certbot 已安装"
            fi
        else
            echo "不支持的操作系统"
            exit 1
        fi

        # 安装 Git
        if ! command -v git &> /dev/null; then
            echo "安装 Git..."
            if command -v apt-get &> /dev/null; then
                apt-get install -y -qq git
            else
                yum install -y -q git
            fi
        fi

        echo "所有依赖已安装完成"
ENDSSH

    echo -e "${GREEN}✓ 服务器软件安装完成${NC}\n"
}

# 创建部署目录
create_deploy_dir() {
    echo -e "${YELLOW}[4/7] 创建部署目录...${NC}"

    ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH
        mkdir -p ${DEPLOY_DIR}
        cd ${DEPLOY_DIR}
        echo "部署目录: ${DEPLOY_DIR}"
ENDSSH

    echo -e "${GREEN}✓ 部署目录创建完成${NC}\n"
}

# 上传项目文件
upload_project() {
    echo -e "${YELLOW}[5/7] 上传项目文件到服务器...${NC}"

    # 获取项目根目录
    PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)

    echo "项目根目录: ${PROJECT_ROOT}"
    echo "目标服务器: ${SERVER_USER}@${SERVER_IP}:${DEPLOY_DIR}"

    # 使用 rsync 上传项目（排除不必要的文件）
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

    echo -e "${GREEN}✓ 项目文件上传完成${NC}\n"
}

# 在服务器上启动服务
start_service() {
    echo -e "${YELLOW}[6/7] 在服务器上启动 Docker 服务...${NC}"

    ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH
        cd ${DEPLOY_DIR}

        # 停止旧容器
        if [ -f docker-compose.yml ]; then
            docker-compose down 2>/dev/null || true
        fi

        # 构建并启动新容器
        echo "构建 Docker 镜像..."
        docker-compose build

        echo "启动服务..."
        docker-compose up -d

        # 等待服务启动
        echo "等待服务启动..."
        sleep 5

        # 检查容器状态
        echo "容器状态:"
        docker-compose ps

        # 检查服务健康
        echo "检查服务健康状态..."
        for i in {1..10}; do
            if curl -s http://localhost:8080/api/health > /dev/null 2>&1; then
                echo "✓ 服务已成功启动"
                break
            fi
            if [ \$i -eq 10 ]; then
                echo "警告: 服务可能未正常启动"
            fi
            sleep 2
        done
ENDSSH

    echo -e "${GREEN}✓ 服务启动完成${NC}\n"
}

# 配置 Nginx 反向代理
configure_nginx() {
    echo -e "${YELLOW}[7/7] 配置 Nginx 反向代理...${NC}"

    # 上传 Nginx 配置文件
    scp deploy/nginx.conf ${SERVER_USER}@${SERVER_IP}:/tmp/tdx-stock.conf

    ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
        # 移动配置文件到 Nginx 配置目录
        mv /tmp/tdx-stock.conf /etc/nginx/sites-available/tdx-stock.conf

        # 创建软链接
        ln -sf /etc/nginx/sites-available/tdx-stock.conf /etc/nginx/sites-enabled/tdx-stock.conf

        # 删除默认站点（如果存在）
        rm -f /etc/nginx/sites-enabled/default

        # 测试 Nginx 配置
        echo "测试 Nginx 配置..."
        nginx -t

        # 重启 Nginx
        echo "重启 Nginx..."
        systemctl restart nginx

        echo "✓ Nginx 配置完成"
ENDSSH

    echo -e "${GREEN}✓ Nginx 反向代理配置完成${NC}\n"
}

# 显示部署结果
show_result() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${GREEN}  部署完成！${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "服务器地址: ${GREEN}http://${SERVER_IP}${NC}"
    echo ""
    echo -e "${YELLOW}下一步操作:${NC}"
    echo -e "1. 绑定域名到服务器 IP: ${SERVER_IP}"
    echo -e "2. 等待域名 DNS 解析生效（通常需要 10 分钟到 24 小时）"
    echo -e "3. 运行以下命令配置 SSL 证书:"
    echo -e "   ${BLUE}bash deploy/setup-ssl.sh your-domain.com${NC}"
    echo ""
    echo -e "${YELLOW}常用命令:${NC}"
    echo -e "  查看日志: ssh ${SERVER_USER}@${SERVER_IP} 'cd ${DEPLOY_DIR} && docker-compose logs -f'"
    echo -e "  重启服务: ssh ${SERVER_USER}@${SERVER_IP} 'cd ${DEPLOY_DIR} && docker-compose restart'"
    echo -e "  停止服务: ssh ${SERVER_USER}@${SERVER_IP} 'cd ${DEPLOY_DIR} && docker-compose down'"
    echo ""
}

# 主流程
main() {
    check_tools
    test_connection
    install_dependencies
    create_deploy_dir
    upload_project
    start_service
    configure_nginx
    show_result
}

# 执行主流程
main
