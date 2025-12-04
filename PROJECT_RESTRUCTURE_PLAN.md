# 项目结构规范化方案

## 当前问题
- 根目录有51个文件，过于混乱
- 多个文档散落在根目录
- 缺少清晰的文件组织结构

## 新目录结构设计

```
tdx-api/
├── README.md                   # 项目主文档
├── .gitignore                  # Git忽略规则
├── Dockerfile                  # Docker镜像构建
├── docker-compose.yml          # Docker编排
├── go.mod / go.sum            # Go依赖
├──
├── cmd/                        # 命令行工具
│   └── web/                    # Web服务入口
│
├── internal/                   # 内部代码（Go）
│   ├── client/                 # TDX客户端
│   ├── protocol/               # 通达信协议
│   └── extend/                 # 扩展功能
│
├── web/                        # Web服务
│   ├── server.go               # Web服务器
│   ├── server_api_extended.go  # 扩展API
│   └── static/                 # 前端静态文件
│       ├── index.html
│       ├── strategy.html
│       ├── app.js
│       └── style.css
│
├── strategies/                 # 策略脚本
│   ├── strategy_b1.py          # B1选股策略
│   ├── backtest_b1.py          # B1回测脚本
│   ├── run_strategy_for_date.py
│   └── run_backtest_only.py
│
├── scripts/                    # 运维脚本
│   ├── run_strategy_cron.sh    # 定时任务脚本
│   ├── run_api_checks.py       # API测试
│   └── backtest_prepare.sh
│
├── deploy/                     # 部署脚本
│   ├── README.md
│   ├── quick-deploy.sh
│   ├── server-deploy.sh
│   └── setup-ssl.sh
│
├── docs/                       # 项目文档
│   ├── api/                    # API文档
│   │   ├── API_接口文档.md
│   │   ├── API_集成指南.md
│   │   └── API_使用示例.py
│   ├── deployment/             # 部署文档
│   │   ├── 服务器部署指南.md
│   │   ├── DOCKER_DEPLOY.md
│   │   └── 定时任务配置指南.md
│   ├── strategies/             # 策略文档
│   │   ├── B1策略评分模型.md
│   │   ├── b1战法.md
│   │   └── n型战法.md
│   └── development/            # 开发记录
│       ├── 已经完成记录.md
│       ├── 更新说明.md
│       └── update-2025-11-10.md
│
├── examples/                   # 示例代码
│   └── (保留原有示例)
│
└── tmp/                        # 临时文件（不提交）
    └── .gitkeep
```

## 文件移动计划

### 1. 策略脚本 → strategies/
- strategy_b1.py
- backtest_b1.py
- run_strategy_for_date.py
- run_backtest_only.py

### 2. 运维脚本 → scripts/
- backtest_prepare.sh
- test_api.py

### 3. API文档 → docs/api/
- API_接口文档.md
- API_集成指南.md
- API_使用示例.py
- API_完成总结.md

### 4. 部署文档 → docs/deployment/
- 服务器部署指南.md (docs/)
- 部署成功记录.md (docs/)
- DOCKER_DEPLOY.md
- DOCKER_快速参考.md
- DOCKER_部署完成.md
- 定时任务配置指南.md (docs/)

### 5. 策略文档 → docs/strategies/
- B1策略评分模型.md (docs/)
- b1.md (docs/选股战法/)
- n型战法.md (docs/选股战法/)

### 6. 开发记录 → docs/development/
- 已经完成记录.md (docs/)
- update-2025-11-10.md (docs/)
- 更新说明.md
- 前复权更新说明.md
- 环境配置指南.md
- 代码修改完成总结.md
- 编码完成最终总结.md
- 跳空检测功能实现验证.md
- 跳空检测功能修改说明.md
- 顶部放量检测功能分析.md
- 顶部放量滞涨检测功能编码完成.md

### 7. 项目总结文档 → docs/
- PROJECT_SUMMARY.md
- FINAL_DELIVERY_SUMMARY.md
- DEPLOYMENT_COMPLETE.md
- DEPLOY_INSTRUCTIONS.md
- CRON_FAILURE_ANALYSIS.md
- Cron时间修复记录.md
- 自动化流程说明.md
- 时序图和流程详解.md

### 8. 删除的文件（临时/重复）
- push_to_github.sh
- push_to_github_final.sh
- GITHUB_PUSH_GUIDE.md
- docker-start.sh (功能已被docker-compose替代)
- docker-start.bat
- b1_results.csv (临时数据)
- stocks.db (本地数据库)

### 9. Go代码 → internal/
- client.go → internal/client/
- protocol/* → internal/protocol/
- extend/* → internal/extend/

## 执行顺序
1. 创建新目录结构
2. 移动文件到对应位置
3. 更新文件中的引用路径
4. 删除临时文件
5. 测试功能完整性
6. 提交到Git
7. 推送到GitHub
8. 重新部署到服务器
