"""
快速生成初始数据文件（离线模式）
用于首次部署时提供初始数据，GitHub Actions 后续会用实时数据覆盖。
"""
import sys, os, json
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

from scripts.recommendation import recommendation_engine, QUALITY_STOCK_POOL, filter_hs300

# 1. 指数数据（占位，GH Actions 会覆盖）
index_data = {
    "updated_at": datetime.now().isoformat(),
    "indices": {
        "sh000001": {"name": "上证指数", "latest": {"close": 3300, "date": datetime.now().strftime("%Y-%m-%d")}, "returns": {"1m": 0, "3m": 0, "1y": 0}},
        "sz399001": {"name": "深证成指", "latest": {"close": 10800, "date": datetime.now().strftime("%Y-%m-%d")}, "returns": {"1m": 0, "3m": 0, "1y": 0}},
    }
}
with open(os.path.join(DATA_DIR, "index_data.json"), "w", encoding="utf-8") as f:
    json.dump(index_data, f, ensure_ascii=False, indent=2)

# 2. 推荐数据（用股票池元数据构建评分输入）
def build_seed_stock_data(info: dict) -> dict:
    """构建离线评分所需数据（精简版，不依赖api模块）"""
    s = info.get("sector", "")
    d = info.get("dividend_yield", 0)
    st = info.get("state_ownership", 0)
    pl = "moderate" if any(k in s for k in ["半导体","芯片","新能源","AI","中药","水电","军工","银行","创新药","通信","核电","高端制造"]) else "none"
    pl = "strong" if any(k in s for k in ["半导体","芯片","AI","军工","新能源"]) else pl
    hd = d >= 3.0 or any(k in s for k in ["银行","煤炭","石油","电力","水电","通信"])
    m = {"白酒":85,"中药":80,"水电":75,"调味品":80,"银行":70}.get(next((k for k in ["白酒","中药","水电","调味品","银行"] if k in s), ""), 50)
    g = {"家电":60,"新能源":55,"半导体":40}.get(next((k for k in ["家电","新能源","半导体"] if k in s), ""), 10)
    return {
        "industry": {"order_growth":60,"capacity_utilization":65,"price_trend":55,"policy_level":pl,"revenue_growth":12,"profit_growth":10,"roe_trend":8,"etf_flow":40,"sector_flow":45,"rank_pct":50,"pe_percentile":40,"pb_percentile":35},
        "company": {"pe_percentile":30,"pb_percentile":35,"ps_ratio":3,"peg_ratio":1,"ev_ebitda":10,"roe_5y":18 if hd else 22,"roic":12 if hd else 16,"gross_margin":55 if hd else 65,"net_margin":20 if hd else 30,"op_cashflow":12 if hd else 15,"market_share":55,"cost_advantage":50,"brand_power":m,"channel":55,"patents":40,"barrier":m,"overseas_revenue_pct":g//2,"overseas_orders":g//3,"global_clients":g//2,"overseas_capacity":g//4},
        "capital": {"day20_inflow":0.05,"ema_trend":0.03,"shareholder_change":-0.02,"avg_holding_increase":0.01,"lhb_net_buy":0.1,"lhb_retail_excluded":st>5,"block_premium_pct":1,"block_institution_buy":st>10,"fund_increase_ratio":0.02,"fund_count_change":0.05},
        "momentum": {"ret_20d":0.02,"ret_60d":0.04,"ret_120d":0.06,"sector_rank_pct":55,"ma20":100,"ma60":95,"ma120":90,"ma250":85,"price":100,"vol_up_ratio":0.45,"vol_down_ratio":0.35,"atr_pct":2.5,"beta":0.9,"annual_vol":28},
        "event": {"major_order":0,"policy_support":2 if pl in ("strong","moderate") else 0,"buyback":0,"executive_buy":0,"reduction":0,"financial_risk":0,"regulatory_investigation":0},
        "timing": {"current_pe":15,"pe_percentile":30,"industry_avg_pe":20,"price":100,"ma60":95,"ma120":90,"ma250":85,"fcf":500,"market_cap":8000},
        "meta": {"symbol":info["symbol"],"name":info["name"],"sector":s,"dividend_yield":d,"state_ownership":st,"reason":info.get("reason",""),"data_source":"seed"},
    }

recs = []
# 过滤沪深300
hs300_codes = set()
hs300_path = os.path.join(DATA_DIR, "hs300_constituents.json")
if os.path.exists(hs300_path):
    try:
        with open(hs300_path, "r", encoding="utf-8") as f:
            hs300_codes = {s["symbol"] for s in json.load(f).get("stocks", [])}
    except Exception:
        pass
pool = filter_hs300(QUALITY_STOCK_POOL, hs300_codes)
for info in pool:
    sd = build_seed_stock_data(info)
    r = recommendation_engine.recommend(sd)
    d = r.to_dict()
    d["reason"] = info.get("reason", "")
    d["source"] = "seed"
    recs.append(d)

recs.sort(key=lambda r: r["final_score"], reverse=True)
rec_data = {"updated_at": datetime.now().isoformat(), "total": len(recs), "success_count": len(recs), "recommendations": recs, "errors": []}
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
