#!/bin/bash
# 回测数据准备脚本 - 在服务器上运行策略生成历史数据

echo "==================================="
echo "📊 回测数据准备"
echo "==================================="

# 远程服务器信息
SERVER="root@139.155.158.47"
SSHPASS="im6HZcPuFxqFf1"
PROJECT_DIR="/opt/tdx-stock"

echo "📅 准备生成最近6天的数据..."
echo ""

# 检查服务器连接
echo "🔌 测试服务器连接..."
sshpass -p "$SSHPASS" ssh -o StrictHostKeyChecking=no $SERVER "echo '✅ 连接成功'" || {
    echo "❌ 无法连接到服务器"
    exit 1
}

# 同步最新代码
echo ""
echo "📦 同步最新策略代码..."
rsync -avz --progress -e "sshpass -p '$SSHPASS' ssh -o StrictHostKeyChecking=no" \
    strategy_b1.py $SERVER:$PROJECT_DIR/ || {
    echo "❌ 代码同步失败"
    exit 1
}

# 运行策略生成今天的数据
echo ""
echo "🚀 运行策略脚本（可能需要几分钟）..."
sshpass -p "$SSHPASS" ssh -o StrictHostKeyChecking=no $SERVER \
    "cd $PROJECT_DIR && python3 strategy_b1.py" || {
    echo "⚠️  策略执行可能有警告，但继续..."
}

# 查看数据库状态
echo ""
echo "📊 检查数据库状态..."
sshpass -p "$SSHPASS" ssh -o StrictHostKeyChecking=no $SERVER \
    "cd $PROJECT_DIR && sqlite3 stocks.db \"SELECT date, COUNT(*) as count, AVG(score) as avg_score FROM strategy_results WHERE strategy_name='b1' GROUP BY date ORDER BY date DESC LIMIT 10;\""

# 下载数据库到本地
echo ""
echo "📥 下载数据库到本地..."
sshpass -p "$SSHPASS" scp -o StrictHostKeyChecking=no \
    $SERVER:$PROJECT_DIR/stocks.db ./stocks.db || {
    echo "❌ 数据库下载失败"
    exit 1
}

echo ""
echo "==================================="
echo "✅ 数据准备完成"
echo "==================================="
echo "现在可以运行: python3 backtest_b1.py"
