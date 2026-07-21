# ☀️ Halo - 中国股市投资分析系统

基于 **IAS评分模型 + 买入时机评估** 的智能选股系统，专为中国A股市场设计。

## 📊 核心功能

### 股票选择 (50%权重) — IAS评分模型
- **行业Alpha (25%)**：景气指数、盈利趋势、资金流、估值
- **公司Alpha (30%)**：估值、盈利能力、护城河、全球化能力
- **资金Alpha (25%)**：连续资金流、筹码集中度、机构行为
- **趋势Alpha (20%)**：截面动量、均线结构、成交量、波动率
- **事件驱动修正 (±10分)**：订单、政策、回购、增减持等

### 买入时机 (50%权重) — 五维估值锚定连续赋分模型（总分120分）
- **历史PE分位 (40分)**：`(1 - pe_percentile) × 40` — 纵向对比，越低越便宜
- **行业PE偏离 (30分)**：`[1 - (偏离+30%)/80%] × 30` — 横向对比，折价越多分越高
- **行业景气度 (30分)**：`(增速+10%)/40% × 30` — 成长性调整，GDP≈5%为基准
- **PB分位 (10分)**：`(1 - pb_percentile) × 10` — 低PB加分，价值发现
- **股息率 (10分)**：`min(10, 股息率×200)` — 高分红加分，现金回报

> **核心原则**：越便宜→分越高，线性连续赋分，避免分数扎堆

### 7大选股特征
1. ✅ 资产随时间增值，越久越值钱
2. ✅ 产品无论朝代更替都恒久需求
3. ✅ 内生性增长，不需再投入
4. ✅ 高分红率
5. ✅ 中国国有资本投资加仓
6. ✅ 未来社会发展趋势中受益
7. ✅ 符合中国政府政策方向

## 🏗️ 技术架构

```
AkShare / Tushare / 东方财富
        ↓
   数据采集层 (Python)
        ↓
   因子计算层
        ↓
   AI评分层 (LLM)
        ↓
   IAS评分引擎
        ↓
   综合推荐引擎 (IAS 50% + 时机 50%)
        ↓
   FastAPI后端 + Web前端
```

## 📁 项目结构

```
halo/
├── api/
│   ├── __init__.py
│   └── index.py              # FastAPI 后端入口
├── frontend/
│   ├── index.html            # 主页面
│   ├── css/
│   │   └── style.css         # 样式表
│   └── js/
│       └── app.js            # 前端逻辑
├── scripts/
│   ├── __init__.py
│   ├── ias_engine.py         # IAS评分引擎
│   ├── timing_eval.py        # 买入时机评估
│   ├── data_collector.py     # 数据采集模块
│   └── recommendation.py     # 综合推荐引擎
├── data/                     # 数据缓存
├── requirements.txt
├── vercel.json               # Vercel部署配置
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量（可选）
```bash
# Tushare Pro token（用于获取精确财务数据）
export TUSHARE_TOKEN=your_token_here

# OpenAI API key（用于AI增强分析，可选）
export OPENAI_API_KEY=your_key_here
```

### 3. 本地运行
```bash
uvicorn api.index:app --host 0.0.0.0 --port 3000 --reload
```

访问 `http://localhost:3000` 查看前端Dashboard。

### 4. API文档
访问 `http://localhost:3000/docs` 查看Swagger文档。

## 📡 API端点

| 端点 | 说明 |
|------|------|
| `GET /api/stocks/recommend` | 获取股票推荐列表 |
| `GET /api/stocks/{symbol}` | 单只股票完整分析 |
| `POST /api/stocks/batch` | 批量股票分析 |
| `GET /api/index` | 指数数据 |
| `GET /api/market/overview` | 市场概览 |
| `GET /api/stocks/quality-pool` | 优质股票池 |
| `GET /api/cron/refresh` | 定时数据刷新 |

## ⏰ 定时刷新

每个交易日自动刷新（通过Vercel Cron Jobs）：
- **9:25** — 开盘集合竞价后
- **13:05** — 午盘开盘后
- **14:50** — 收盘前10分钟

## 🌐 部署

### Vercel部署
1. Fork本仓库到你的GitHub
2. 在Vercel中导入项目
3. 设置Framework Preset为Other
4. 部署即可

### 环境变量（Vercel）
在Vercel项目设置中添加：
- `TUSHARE_TOKEN`：Tushare Pro token

## 🔬 选股逻辑

### 双重过滤规则
- 行业评分 < 60 → 直接淘汰
- 公司评分 < 60 → 直接淘汰

### 机构一致性评分 (ICS)
- ICS ≥ 80 → 进入核心股票池
- 组成：公募增仓 + 保险/社保 + 龙虎榜 + 大宗交易 + 资金流入 + 股东人数

### 最终推荐公式
```
Final Score = IAS_Score × 50% + Timing_Score × 50%
```

## 📈 投资方向分析

基于中国未来趋势的核心投资方向：

| 方向 | 驱动因素 | 代表标的 |
|------|---------|---------|
| 🏥 老龄化+健康中国 | 人口结构变化 | 中药、医疗器械、创新药 |
| 💡 科技自主可控 | 中美博弈+政策 | 半导体、AI、信创 |
| 🌱 碳中和+新能源 | 全球能源转型 | 水电、核电、新能源车 |
| 🏭 高股息+国企改革 | 低利率+政策 | 银行、能源、运营商 |
| 🍶 消费升级+国货 | 内需+品牌 | 白酒、调味品、家电 |
| 🌏 全球化+出海 | 产能输出 | 家电出海、新能源出海 |

## ⚠️ 免责声明

本系统仅供学习和研究参考，**不构成任何投资建议**。

股市有风险，投资需谨慎。请独立做出投资决策，盈亏自负。

## 📄 许可证

MIT License
