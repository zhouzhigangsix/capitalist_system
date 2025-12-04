#!/bin/bash

# ============================================
# TDX Stock B1 Strategy Cron Wrapper
# ============================================
# 用途: 定时任务包装脚本
# 时间: 每个交易日 15:13 执行
# ============================================

# 设置环境变量
export PATH=/usr/local/bin:/usr/bin:/bin
export PYTHONUNBUFFERED=1

# 项目目录
PROJECT_DIR="/opt/tdx-stock"
LOG_DIR="/var/log/tdx-stock"
SCRIPT="strategies/strategy_b1.py"

# 创建日志目录
mkdir -p $LOG_DIR

# 生成日志文件名（按日期）
LOG_FILE="$LOG_DIR/strategy_$(date +\%Y\%m\%d).log"

# 记录开始时间
echo "========================================" >> $LOG_FILE
echo "策略执行开始: $(date '+%Y-%m-%d %H:%M:%S')" >> $LOG_FILE
echo "========================================" >> $LOG_FILE

# 切换到项目目录
cd $PROJECT_DIR

# 执行策略脚本
python3 $SCRIPT >> $LOG_FILE 2>&1

# 记录执行结果
EXIT_CODE=$?
echo "" >> $LOG_FILE
echo "========================================" >> $LOG_FILE
echo "策略执行结束: $(date '+%Y-%m-%d %H:%M:%S')" >> $LOG_FILE
echo "退出代码: $EXIT_CODE" >> $LOG_FILE
echo "========================================" >> $LOG_FILE
echo "" >> $LOG_FILE

# 如果执行失败，发送通知（可选）
if [ $EXIT_CODE -ne 0 ]; then
    echo "警告: 策略执行失败，退出代码 $EXIT_CODE" >> $LOG_FILE
fi

# 清理超过7天的旧日志
find $LOG_DIR -name "strategy_*.log" -mtime +7 -delete

exit $EXIT_CODE
