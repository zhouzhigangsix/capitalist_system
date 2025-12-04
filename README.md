# 📈 TDX智能量化选股系统 (Alpha Hunter)

> 基于通达信协议的高性能股票数据API + Python量化选股策略 + Web可视化界面

**感谢源作者 injoyai，原项目地址: https://github.com/injoyai/tdx**

[![Go Version](https://img.shields.io/badge/Go-1.22+-00ADD8?style=flat&logo=go)](https://golang.org)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat&logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-支持-2496ED?style=flat&logo=docker)](https://www.docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## ✨ 核心功能

### 📊 数据服务层
- ✅ **实时行情** - 五档买卖盘口、最新价、涨跌幅
- ✅ **K线数据** - 支持10种周期（1分钟~年K）
- ✅ **分时数据** - 当日分时走势、逐笔成交
- ✅ **股票搜索** - 代码/名称模糊搜索
- ✅ **26个REST API** - 完整的HTTP接口

### 🤖 量化策略层
- ✅ **B1选股策略** - 7个条件筛选体系
- ✅ **100分制评分** - 5维度量化评估
- ✅ **自动回测** - 次日收益自动计算
- ✅ **定时任务** - 每日自动选股（22:08）
- ✅ **星级评价** - ⭐⭐⭐⭐⭐ 直观展示

### 🌐 可视化界面
- 📱 **现代化UI** - 深色极光主题、响应式布局
- 📊 **ECharts图表** - 专业K线图和分时图
- 🔍 **智能搜索** - 股票代码/名称快速搜索
- 📈 **实时刷新** - 策略结果实时更新

---

## 🚀 快速开始

### 方式一：Docker部署（推荐）⭐

```bash
# 1. 克隆项目
git clone https://github.com/yourusername/tdx-api.git
cd tdx-api

# 2. 启动服务
docker-compose up -d

# 3. 访问Web界面
浏览器打开: http://localhost:8080
```

### 方式二：本地开发

**后端服务（Go）**:
```bash
cd web
go run server.go
```

**策略脚本（Python）**:
```bash
pip install requests pandas numpy
python strategies/strategy_b1.py
```

---

## 📁 项目结构

```
tdx-api/
├── README.md                   # 项目主文档
├── docker-compose.yml          # Docker编排配置
├── Dockerfile                  # Docker镜像构建
│
├── web/                        # Web服务（Go）
│   ├── server.go               # Web服务器主程序
│   ├── server_api_extended.go  # 扩展API接口
│   └── static/                 # 前端静态文件
│       ├── index.html          # 行情查询页面
│       ├── strategy.html       # 策略中心页面
│       ├── app.js
│       └── style.css
│
├── strategies/                 # 量化策略（Python）
│   ├── strategy_b1.py          # B1选股策略（核心）
│   ├── backtest_b1.py          # B1策略回测
│   ├── run_strategy_for_date.py  # 指定日期选股
│   └── run_backtest_only.py    # 独立回测脚本
│
├── scripts/                    # 运维脚本
│   ├── run_strategy_cron.sh    # 定时任务脚本
│   ├── run_api_checks.py       # API接口测试
│   └── backtest_prepare.sh     # 回测准备脚本
│
├── deploy/                     # 部署工具
│   ├── quick-deploy.sh         # 快速部署
│   ├── server-deploy.sh        # 服务器部署
│   └── setup-ssl.sh            # SSL证书配置
│
├── docs/                       # 项目文档
│   ├── api/                    # API文档
│   ├── deployment/             # 部署文档
│   ├── strategies/             # 策略文档
│   └── development/            # 开发记录
│
├── protocol/                   # 通达信协议实现（Go）
├── extend/                     # 扩展功能（Go）
└── example/                    # 示例代码
```

---

## 🎯 B1选股策略

### 7个选股条件

| # | 条件 | 说明 | 阈值 |
|---|------|------|------|
| 1 | 价格突破 | close > 知行多空线 | - |
| 2 | KDJ超卖 | J值 < 13 | J < 13 |
| 3 | 趋势突破 | 短期趋势线 > 多空线 | - |
| 4 | 低振幅 | 日振幅收敛 | < 4% |
| 5 | 低成交量 | 成交量萎缩 | < 52% |
| 6 | 无缺口 | 40天内无跳空缺口 | 40天 |
| 7 | 无顶部滞涨 | 无高位放量滞涨 | 40天 |

### 100分制评分模型

- **超卖程度（30分）**: J值越低，反弹空间越大
- **趋势强度（25分）**: 偏离多空线越多，趋势越强
- **缩量程度（20分）**: 缩量越明显，洗盘越充分
- **短期动能（15分）**: 短期趋势线向上角度
- **振幅收敛（10分）**: 振幅越小，变盘概率越大

详细文档: [B1策略评分模型](docs/strategies/B1策略评分模型.md)

---

## 📡 API接口

### 核心接口

| 接口 | 方法 | 说明 |
|-----|------|------|
| `/api/quote` | GET | 五档行情 |
| `/api/kline` | GET | K线数据 |
| `/api/minute` | GET | 分时数据 |
| `/api/search` | GET | 搜索股票 |
| `/api/strategy/results` | GET | 选股结果 |
| `/api/backtest/results` | GET | 回测结果 |

完整文档: [API接口文档](docs/api/API_接口文档.md)

---

## 🐳 生产部署

### 服务器部署

```bash
# 使用快速部署脚本
cd deploy
bash server-deploy.sh
```

### 定时任务配置

系统已配置**每日22:08自动选股**:

```bash
# Crontab配置
8 22 * * 1-5 /opt/tdx-stock/scripts/run_strategy_cron.sh
```

详细文档: [服务器部署指南](docs/deployment/服务器部署指南.md)

---

## 📊 数据示例

### 选股结果

```json
{
  "code": "000001",
  "name": "平安银行",
  "price": 12.35,
  "score": 85.4,
  "j_value": 8.5,
  "amplitude": 2.3,
  "volume_ratio": 0.35,
  "rating": "⭐⭐⭐⭐"
}
```

### 回测结果

```json
{
  "date": "2025-12-03",
  "total_stocks": 10,
  "win_count": 7,
  "lose_count": 3,
  "avg_return": 2.15,
  "win_rate": 70.0
}
```

---

## 📚 完整文档

| 文档 | 说明 |
|-----|------|
| [API接口文档](docs/api/API_接口文档.md) | 完整API说明 |
| [API集成指南](docs/api/API_集成指南.md) | API使用指南 |
| [服务器部署指南](docs/deployment/服务器部署指南.md) | 部署操作手册 |
| [Docker部署指南](docs/deployment/DOCKER_DEPLOY.md) | Docker部署说明 |
| [B1策略评分模型](docs/strategies/B1策略评分模型.md) | 评分规则详解 |
| [定时任务配置](docs/deployment/定时任务配置指南.md) | Cron配置说明 |

---

## 💡 应用场景

### 🤖 量化交易
- 每日自动选股，提供高质量交易标的
- 100分制评分，快速识别优质机会
- 自动回测，持续优化策略参数

### 📊 数据分析
- 获取全市场历史K线数据
- 技术指标批量计算
- 策略回测验证

### 📱 实时监控
- 自选股实时行情监控
- 价格突破提醒
- 策略信号推送

---

## 🔧 技术栈

**后端**:
- Go 1.22+ (Web服务、通达信协议)
- Python 3.8+ (策略计算、数据处理)
- SQLite (数据持久化)

**前端**:
- HTML5 + CSS3 + JavaScript
- ECharts (图表可视化)

**部署**:
- Docker + Docker Compose
- Nginx (反向代理)
- Cron (定时任务)

---

## ⚠️ 免责声明

1. 本项目仅供学习和研究使用
2. 数据来源于通达信公共服务器，可能存在延迟
3. 策略结果不构成任何投资建议
4. 请勿用于商业用途
5. 投资有风险，入市需谨慎

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

### 贡献指南
1. Fork本项目
2. 创建新分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 📞 联系方式

- 💬 提交Issue: [GitHub Issues](https://github.com/yourusername/tdx-api/issues)

---

## ⭐ Star History

如果这个项目对您有帮助，请点个Star⭐️支持一下！

---

**最后更新**: 2025-12-04
**项目状态**: 🟢 生产就绪
