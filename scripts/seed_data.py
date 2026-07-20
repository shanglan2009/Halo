"""
快速生成初始数据文件（离线模式）
用于首次部署时提供初始数据，GitHub Actions 后续会用实时数据覆盖。
"""
import sys, os, json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 直接使用内置函数构建数据
# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 1. 指数数据（占位）
index_data = {
    "updated_at": datetime.now().isoformat(),
    "indices": {
        "sh000001": {"name": "上证指数", "latest": {"close": 3300, "date": datetime.now().strftime("%Y-%m-%d")}, "returns": {"1m": 0, "3m": 0, "1y": 0}},
        "sz399001": {"name": "深证成指", "latest": {"close": 10800, "date": datetime.now().strftime("%Y-%m-%d")}, "returns": {"1m": 0, "3m": 0, "1y": 0}},
    }
}
with open(os.path.join(DATA_DIR, "index_data.json"), "w", encoding="utf-8") as f:
    json.dump(index_data, f, ensure_ascii=False, indent=2)

# 2. 推荐数据（离线评分，GitHub Actions 会覆盖）
from api.index import build_offline_stock_data
from scripts.recommendation import recommendation_engine, QUALITY_STOCK_POOL

recs = []
for stock_info in QUALITY_STOCK_POOL:
    sd = build_offline_stock_data(stock_info)
    rec = recommendation_engine.recommend(sd)
    d = rec.to_dict()
    d["reason"] = stock_info.get("reason", "")
    d["source"] = "offline"
    recs.append(d)

recs.sort(key=lambda r: r["final_score"], reverse=True)
rec_data = {
    "updated_at": datetime.now().isoformat(),
    "total": len(recs),
    "success_count": len(recs),
    "recommendations": recs,
    "errors": [],
}
with open(os.path.join(DATA_DIR, "recommendations.json"), "w", encoding="utf-8") as f:
    json.dump(rec_data, f, ensure_ascii=False, indent=2)

# 3. 市场概览
overview = {"updated_at": datetime.now().isoformat(), "timestamp": datetime.now().isoformat()}
with open(os.path.join(DATA_DIR, "market_overview.json"), "w", encoding="utf-8") as f:
    json.dump(overview, f, ensure_ascii=False, indent=2)

# 4. 状态
with open(os.path.join(DATA_DIR, "refresh_status.json"), "w", encoding="utf-8") as f:
    json.dump({"last_refresh": datetime.now().isoformat(), "success": True, "stock_count": len(recs)}, f, ensure_ascii=False, indent=2)

print(f"[DONE] 初始数据已生成: {len(recs)} 只股票")
