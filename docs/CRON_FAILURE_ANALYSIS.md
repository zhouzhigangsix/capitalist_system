# Cron 进程死亡原因分析及防止方案

## 🔴 根本原因

### 什么发生了？
```
Dec 3 11:15:36 - crond 进程首次死亡
  ↓
can't lock /var/run/crond.pid, otherpid may be 8459
  ↓
PID 8459 是一个已存在的 crond 进程（可能是僵尸进程）
  ↓
新的 crond 进程无法获得 PID 锁
  ↓
持续尝试启动但不断失败，持续约 12 小时
  ↓
22:08 选股任务完全无法执行
```

### 为什么会发生？

**问题链条**：
1. **孤立的 crond 进程** (PID 8459)
   - 可能是上次系统重启或服务崩溃后残留的僵尸进程
   - 进程仍然持有 `/var/run/crond.pid` 文件锁

2. **PID 文件锁冲突**
   - crond 使用 PID 文件进行单实例锁定
   - 防止多个 crond 进程同时运行
   - 但锁定机制在孤立进程存在时失效

3. **系统缺乏监控机制**
   - 没有自动清理孤立进程
   - 没有自动重启失败的 Cron 服务
   - 没有告警通知

---

## 🛠️ 防止方案

### 方案 1：定期健康检查脚本（推荐）

创建文件：`/opt/tdx-stock/scripts/cron_health_check.sh`

```bash
#!/bin/bash
# Cron 健康检查脚本

CROND_PID_FILE="/var/run/crond.pid"
LOG_FILE="/var/log/cron_health_check.log"

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# 检查 Cron 是否运行
if ! systemctl is-active --quiet crond; then
    log_message "⚠️  Cron 服务未运行，正在重启..."
    systemctl restart crond

    if systemctl is-active --quiet crond; then
        log_message "✅ Cron 服务成功重启"
    else
        log_message "❌ Cron 重启失败，需要人工介入"
        # 可选：发送告警通知
    fi
fi

# 清理孤立的 PID 文件
if [ -f "$CROND_PID_FILE" ]; then
    PID=$(cat $CROND_PID_FILE)

    # 检查 PID 对应的进程是否真实存在
    if ! ps -p $PID > /dev/null 2>&1; then
        log_message "🧹 发现孤立的 crond PID 文件 ($PID)，正在清理..."
        rm -f $CROND_PID_FILE
        systemctl restart crond
        log_message "✅ 孤立 PID 已清理，Cron 已重启"
    fi
fi

log_message "✔️  Cron 健康检查完成"
```

**使用方法**：
```bash
# 1. 创建脚本
touch /opt/tdx-stock/scripts/cron_health_check.sh
chmod +x /opt/tdx-stock/scripts/cron_health_check.sh

# 2. 添加到系统 crontab（每 5 分钟检查一次）
crontab -e

# 添加这一行：
*/5 * * * * /opt/tdx-stock/scripts/cron_health_check.sh
```

### 方案 2：Systemd 自动重启

编辑 `/etc/systemd/system/crond.service.d/restart.conf`（如果不存在则创建）：

```ini
[Service]
Restart=always
RestartSec=10s

# 失败次数限制（可选）
StartLimitBurst=5
StartLimitIntervalSec=60s
```

**应用更改**：
```bash
systemctl daemon-reload
systemctl restart crond
```

### 方案 3：监控脚本（完整版）

创建文件：`/opt/tdx-stock/scripts/comprehensive_monitor.sh`

```bash
#!/bin/bash

# 完整的系统健康监控脚本

SERVICE_NAME="crond"
LOG_DIR="/var/log/tdx-stock"
LOCK_DIR="/var/run"
ALERT_LOG="$LOG_DIR/alerts.log"

mkdir -p $LOG_DIR

# 1. 检查 Cron 服务状态
check_cron_status() {
    if systemctl is-active --quiet $SERVICE_NAME; then
        echo "✅ Cron 服务：运行中"
        return 0
    else
        echo "❌ Cron 服务：未运行"
        return 1
    fi
}

# 2. 检查 PID 文件合法性
check_pid_file() {
    PID_FILE="$LOCK_DIR/crond.pid"

    if [ ! -f "$PID_FILE" ]; then
        echo "⚠️  PID 文件不存在（正常）"
        return 0
    fi

    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -z "$PID" ]; then
        echo "⚠️  PID 文件为空，清理中..."
        rm -f "$PID_FILE"
        return 1
    fi

    # 检查 PID 对应的进程
    if ps -p $PID > /dev/null 2>&1; then
        echo "✅ PID 文件有效 (PID: $PID)"
        return 0
    else
        echo "❌ PID 文件陈旧 (PID: $PID 不存在)，清理中..."
        rm -f "$PID_FILE"
        return 1
    fi
}

# 3. 检查 crontab 配置
check_crontab() {
    if crontab -l 2>/dev/null | grep -q "run_strategy_cron.sh"; then
        echo "✅ Crontab 配置存在"
        return 0
    else
        echo "❌ Crontab 配置丢失"
        return 1
    fi
}

# 4. 修复并重启
fix_and_restart() {
    echo "🔧 开始修复..."

    # 清理孤立 PID
    rm -f "$LOCK_DIR/crond.pid"

    # 重启服务
    systemctl restart crond
    sleep 2

    if systemctl is-active --quiet crond; then
        echo "✅ 修复成功！"
        echo "[$(date)] Cron 修复成功" >> "$ALERT_LOG"
        return 0
    else
        echo "❌ 修复失败"
        echo "[$(date)] Cron 修复失败" >> "$ALERT_LOG"
        return 1
    fi
}

# 主程序
main() {
    echo "================================"
    echo "  系统健康检查 - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "================================"

    # 执行所有检查
    check_cron_status
    CRON_STATUS=$?

    check_pid_file
    PID_STATUS=$?

    check_crontab
    CRON_CONF_STATUS=$?

    # 如果有问题，尝试修复
    if [ $CRON_STATUS -ne 0 ] || [ $PID_STATUS -ne 0 ]; then
        fix_and_restart
    fi

    echo "================================"
}

main
```

---

## 📋 推荐的完整防御方案

### 第一步：立即执行
```bash
# 1. 创建监控脚本
sudo cp comprehensive_monitor.sh /opt/tdx-stock/scripts/
sudo chmod +x /opt/tdx-stock/scripts/comprehensive_monitor.sh

# 2. 测试脚本
/opt/tdx-stock/scripts/comprehensive_monitor.sh

# 3. 添加到系统定时任务（每 5 分钟运行）
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/tdx-stock/scripts/comprehensive_monitor.sh") | crontab -
```

### 第二步：添加告警通知（可选）

在 `comprehensive_monitor.sh` 中添加邮件/钉钉通知：

```bash
# 添加到 fix_and_restart 函数
send_alert() {
    local message=$1
    # 发送钉钉/企业微信/邮件通知
    curl -X POST 'https://your-webhook-url' \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"$message\"}"
}
```

### 第三步：日志监控

配置 systemd 日志轮转：

```bash
# 创建日志配置
cat > /etc/logrotate.d/tdx-stock <<EOF
/var/log/cron_health_check.log
/var/log/tdx-stock/*.log
{
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

---

## 🎯 关键指标监控

定期检查这些指标防止问题：

```bash
# 1. Cron 进程数
ps aux | grep crond | grep -v grep | wc -l
# 正常应该 = 1

# 2. PID 文件年龄
stat /var/run/crond.pid | grep Modify
# 应该接近当前时间

# 3. Cron 任务执行情况
grep "run_strategy_cron.sh" /var/log/cron | tail -5
# 应该定期出现

# 4. 系统 Cron 状态
systemctl status crond
# 应该显示 "active (running)"
```

---

## 🚨 问题预防总结表

| 问题类型 | 原因 | 预防方案 | 检测周期 |
|---------|------|---------|---------|
| 孤立 Cron 进程 | 系统重启/崩溃 | 定期清理 PID | 每 5 分钟 |
| PID 文件锁 | 多进程启动 | 自动监控 | 每 5 分钟 |
| 服务未运行 | 资源耗尽 | 自动重启 | 每 5 分钟 |
| 任务未执行 | Cron 停止 | 定期验证 | 每小时 |

---

## 📝 部署步骤

### 快速部署（5 分钟）

```bash
# 1. 立即应用 Systemd 自动重启
sudo mkdir -p /etc/systemd/system/crond.service.d
sudo tee /etc/systemd/system/crond.service.d/restart.conf > /dev/null <<EOF
[Service]
Restart=always
RestartSec=10s
StartLimitBurst=5
StartLimitIntervalSec=60s
EOF

sudo systemctl daemon-reload

# 2. 创建定期健康检查
sudo tee /opt/tdx-stock/scripts/cron_health_check.sh > /dev/null <<'EOF'
#!/bin/bash
if ! systemctl is-active --quiet crond; then
    systemctl restart crond
fi
rm -f /var/run/crond.pid 2>/dev/null
systemctl restart crond 2>/dev/null || true
EOF

sudo chmod +x /opt/tdx-stock/scripts/cron_health_check.sh

# 3. 添加定时任务
(crontab -l 2>/dev/null | grep -v cron_health_check; echo "*/5 * * * * /opt/tdx-stock/scripts/cron_health_check.sh > /dev/null 2>&1") | crontab -

# 4. 验证
sudo systemctl status crond
crontab -l | grep cron_health_check
```

---

## ✅ 验证清单

部署后检查：

- [ ] Cron 服务正在运行：`systemctl status crond`
- [ ] PID 文件存在：`ls -l /var/run/crond.pid`
- [ ] 健康检查脚本存在：`ls -l /opt/tdx-stock/scripts/cron_health_check.sh`
- [ ] 定时任务已添加：`crontab -l | grep cron_health_check`
- [ ] 选股任务正常：`crontab -l | grep run_strategy_cron`
- [ ] 日志正常输出：`tail -5 /var/log/cron`

---

## 🎓 为什么这个方案有效？

```
问题：           单一 Cron 进程 + 孤立 PID 文件 = 完全故障

防护层1：       自动重启（Systemd）
  └─ 如果 Cron 崩溃，10秒内自动重启

防护层2：       定期检查（每5分钟）
  └─ 检测并清理孤立 PID 文件
  └─ 强制重启 Cron 服务

防护层3：       日志监控
  └─ 记录所有异常
  └─ 便于调试

结果：           多层防护 → 几乎不可能再发生这种故障
```

---

**建议行动**：立即部署"快速部署"脚本，确保不会再出现类似故障。
