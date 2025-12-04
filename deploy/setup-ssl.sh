#!/bin/bash

# ============================================
# SSL Certificate Setup Script
# ============================================
# 用途: 为域名配置 Let's Encrypt SSL 证书
# 使用: bash deploy/setup-ssl.sh your-domain.com
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 服务器配置
SERVER_IP="139.155.158.47"
SERVER_USER="root"

# 检查参数
if [ -z "$1" ]; then
    echo -e "${RED}错误: 请提供域名${NC}"
    echo -e "使用方法: bash deploy/setup-ssl.sh your-domain.com"
    echo -e "示例: bash deploy/setup-ssl.sh stock.example.com"
    exit 1
fi

DOMAIN=$1
EMAIL=${2:-"admin@${DOMAIN}"}  # 可选的邮箱参数

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SSL 证书配置工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "域名: ${GREEN}${DOMAIN}${NC}"
echo -e "邮箱: ${GREEN}${EMAIL}${NC}"
echo ""

# 检查域名解析
echo -e "${YELLOW}[1/4] 检查域名解析...${NC}"

RESOLVED_IP=$(dig +short ${DOMAIN} | tail -n1)

if [ -z "$RESOLVED_IP" ]; then
    echo -e "${RED}错误: 域名 ${DOMAIN} 未解析${NC}"
    echo -e "${YELLOW}请先将域名的 A 记录指向服务器 IP: ${SERVER_IP}${NC}"
    exit 1
fi

if [ "$RESOLVED_IP" != "$SERVER_IP" ]; then
    echo -e "${RED}警告: 域名解析的 IP (${RESOLVED_IP}) 与服务器 IP (${SERVER_IP}) 不匹配${NC}"
    echo -e "${YELLOW}请检查 DNS 配置${NC}"
    read -p "是否继续? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓ 域名解析正确${NC}\n"
fi

# 更新 Nginx 配置中的域名
echo -e "${YELLOW}[2/4] 更新 Nginx 配置...${NC}"

ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH
    # 备份原配置
    cp /etc/nginx/sites-available/tdx-stock.conf /etc/nginx/sites-available/tdx-stock.conf.backup

    # 替换 server_name
    sed -i "s/server_name _;/server_name ${DOMAIN};/g" /etc/nginx/sites-available/tdx-stock.conf

    # 测试配置
    nginx -t

    # 重启 Nginx
    systemctl reload nginx

    echo "✓ Nginx 配置已更新"
ENDSSH

echo -e "${GREEN}✓ Nginx 配置更新完成${NC}\n"

# 申请 SSL 证书
echo -e "${YELLOW}[3/4] 申请 SSL 证书...${NC}"
echo -e "${BLUE}这可能需要几分钟，请耐心等待...${NC}"

ssh ${SERVER_USER}@${SERVER_IP} << ENDSSH
    # 使用 Certbot 申请证书
    certbot --nginx \
        -d ${DOMAIN} \
        --email ${EMAIL} \
        --agree-tos \
        --no-eff-email \
        --redirect \
        --quiet

    echo "✓ SSL 证书申请成功"
ENDSSH

echo -e "${GREEN}✓ SSL 证书配置完成${NC}\n"

# 设置自动续期
echo -e "${YELLOW}[4/4] 配置证书自动续期...${NC}"

ssh ${SERVER_USER}@${SERVER_IP} << 'ENDSSH'
    # 测试证书续期
    certbot renew --dry-run

    # Certbot 会自动添加续期任务到 cron/systemd timer
    echo "✓ 证书自动续期已配置"
ENDSSH

echo -e "${GREEN}✓ 证书自动续期配置完成${NC}\n"

# 显示结果
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  SSL 配置完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "网站地址: ${GREEN}https://${DOMAIN}${NC}"
echo -e "策略中心: ${GREEN}https://${DOMAIN}/strategy.html${NC}"
echo -e "API 地址: ${GREEN}https://${DOMAIN}/api/${NC}"
echo ""
echo -e "${YELLOW}证书信息:${NC}"
echo -e "  颁发机构: Let's Encrypt"
echo -e "  有效期: 90 天"
echo -e "  自动续期: 已启用"
echo ""
echo -e "${YELLOW}常用命令:${NC}"
echo -e "  查看证书: ssh ${SERVER_USER}@${SERVER_IP} 'certbot certificates'"
echo -e "  手动续期: ssh ${SERVER_USER}@${SERVER_IP} 'certbot renew'"
echo -e "  测试续期: ssh ${SERVER_USER}@${SERVER_IP} 'certbot renew --dry-run'"
echo ""
