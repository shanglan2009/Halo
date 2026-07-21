"""
Halo - 中国股市投资分析系统 API
基于FastAPI的后端服务，部署于Vercel Serverless Functions

核心功能：
- /api/stocks/recommend - 获取股票推荐列表
- /api/stocks/{symbol} - 单只股票分析
- /api/index - 指数数据
- /api/cron/refresh - 定时刷新数据
"""
import sys
import os
import json
import secrets
import copy
from datetime import datetime, timedelta
from typing import Optional

# 确保项目根目录在Python路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 延迟导入重型模块（避免 Vercel 冷启动崩溃）
ias_engine = None
timing_evaluator = None
data_collector = None
recommendation_engine = None
QUALITY_STOCK_POOL = []
filter_hs300 = None
sim_engine = None

def _lazy_import():
    """延迟导入重型模块"""
    global ias_engine, timing_evaluator, data_collector
    global recommendation_engine, QUALITY_STOCK_POOL, filter_hs300, sim_engine
    if ias_engine is not None:
        return True
    try:
        from scripts.ias_engine import ias_engine as _ias
        from scripts.timing_eval import timing_evaluator as _te
        from scripts.recommendation import recommendation_engine as _re, QUALITY_STOCK_POOL as _qp, filter_hs300 as _fh
        ias_engine = _ias
        timing_evaluator = _te
        recommendation_engine = _re
        QUALITY_STOCK_POOL = _qp
        filter_hs300 = _fh
    except Exception as e:
        print(f"[WARN] 核心引擎导入失败: {e}", flush=True)
        return False
    try:
        from scripts.data_collector import data_collector as _dc
        data_collector = _dc
    except Exception:
        pass
    try:
        from scripts.sim_engine import sim_engine as _se
        sim_engine = _se
    except Exception:
        pass
    return True

# 创建FastAPI应用
app = FastAPI(
    title="Halo - 中国股市投资分析系统",
    description="基于IAS评分模型 + 买入时机评估的智能选股系统",
    version="1.0.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 安全配置 ==========
CRON_SECRET = os.environ.get("CRON_SECRET", "")

def verify_cron_secret(request) -> bool:
    """验证定时任务密钥
    Vercel Cron Jobs 通过 Authorization: Bearer <CRON_SECRET> header 发送密钥。
    本地开发时设置环境变量 CRON_SECRET=dev 即可。
    """
    if not CRON_SECRET:
        return False  # 未配置密钥，拒绝所有请求
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {CRON_SECRET}"
    return secrets.compare_digest(auth_header, expected)


# ========== 数据缓存 ==========
# 简单内存缓存（Vercel Serverless环境下每次冷启动会重置）
_cache = {}
CACHE_TTL = timedelta(hours=4)


def cache_get(key: str):
    """获取缓存"""
    if key in _cache:
        data, timestamp = _cache[key]
        if datetime.now() - timestamp < CACHE_TTL:
            return data
    return None


def cache_set(key: str, data):
    """设置缓存"""
    _cache[key] = (data, datetime.now())


# ========== 内联回退数据（后端模块不可用时的保底） ==========

INLINE_STOCK_POOL = [
    {"symbol": "600519", "name": "贵州茅台", "sector": "白酒/消费", "dividend_yield": 2.5, "state_ownership": 4.5, "reason": "品牌护城河极深，越陈越香"},
    {"symbol": "000858", "name": "五粮液", "sector": "白酒/消费", "dividend_yield": 2.2, "state_ownership": 3.0, "reason": "浓香龙头，品牌价值随时间增值"},
    {"symbol": "600809", "name": "山西汾酒", "sector": "白酒/消费", "dividend_yield": 1.8, "state_ownership": 2.5, "reason": "清香型龙头，品牌复兴"},
    {"symbol": "600436", "name": "片仔癀", "sector": "中药/消费", "dividend_yield": 2.0, "state_ownership": 5.0, "reason": "国家保密配方，越久越值钱"},
    {"symbol": "000538", "name": "云南白药", "sector": "中药/消费", "dividend_yield": 3.5, "state_ownership": 10.0, "reason": "国家保密配方，百年品牌"},
    {"symbol": "600085", "name": "同仁堂", "sector": "中药/消费", "dividend_yield": 2.5, "state_ownership": 8.0, "reason": "350年老字号，品牌随时间增值"},
    {"symbol": "600900", "name": "长江电力", "sector": "水电/清洁能源", "dividend_yield": 3.8, "state_ownership": 55.0, "reason": "水电资产永续经营，现金流稳定"},
    {"symbol": "600886", "name": "国投电力", "sector": "水电/清洁能源", "dividend_yield": 3.2, "state_ownership": 45.0, "reason": "清洁能源龙头，国有资本控股"},
    {"symbol": "601088", "name": "中国神华", "sector": "煤炭/能源", "dividend_yield": 6.5, "state_ownership": 60.0, "reason": "煤炭电力铁路一体化，超高分红"},
    {"symbol": "601857", "name": "中国石油", "sector": "石油/能源", "dividend_yield": 4.5, "state_ownership": 80.0, "reason": "国家能源安全核心资产"},
    {"symbol": "600028", "name": "中国石化", "sector": "石油/能源", "dividend_yield": 5.5, "state_ownership": 70.0, "reason": "炼化加油站网络，稳定高分红"},
    {"symbol": "601939", "name": "建设银行", "sector": "银行/金融", "dividend_yield": 5.8, "state_ownership": 60.0, "reason": "国有大行，分红率高"},
    {"symbol": "601398", "name": "工商银行", "sector": "银行/金融", "dividend_yield": 5.5, "state_ownership": 65.0, "reason": "全球最大银行，国有控股"},
    {"symbol": "601288", "name": "农业银行", "sector": "银行/金融", "dividend_yield": 5.6, "state_ownership": 70.0, "reason": "国有大行，三农金融服务"},
    {"symbol": "600036", "name": "招商银行", "sector": "银行/金融", "dividend_yield": 4.5, "state_ownership": 25.0, "reason": "零售银行之王，ROE行业领先"},
    {"symbol": "601318", "name": "中国平安", "sector": "保险/金融", "dividend_yield": 4.2, "state_ownership": 5.0, "reason": "综合金融巨头，保险银行科技"},
    {"symbol": "600690", "name": "海尔智家", "sector": "家电/消费", "dividend_yield": 3.0, "state_ownership": 10.0, "reason": "全球化家电龙头，海外收入超50%"},
    {"symbol": "000333", "name": "美的集团", "sector": "家电/消费", "dividend_yield": 3.5, "state_ownership": 8.0, "reason": "家电综合龙头，全球布局"},
    {"symbol": "000651", "name": "格力电器", "sector": "家电/消费", "dividend_yield": 4.5, "state_ownership": 15.0, "reason": "空调霸主，品牌护城河"},
    {"symbol": "603288", "name": "海天味业", "sector": "调味品/消费", "dividend_yield": 1.8, "state_ownership": 2.0, "reason": "调味品绝对龙头，渠道壁垒深厚"},
    {"symbol": "600887", "name": "伊利股份", "sector": "食品饮料/消费", "dividend_yield": 3.2, "state_ownership": 5.0, "reason": "乳业龙头，消费升级受益"},
    {"symbol": "002415", "name": "海康威视", "sector": "AI/安防/科技", "dividend_yield": 2.8, "state_ownership": 8.0, "reason": "AI视觉龙头，全球第一"},
    {"symbol": "300750", "name": "宁德时代", "sector": "新能源/电池", "dividend_yield": 0.8, "state_ownership": 3.0, "reason": "动力电池全球龙头，技术壁垒深厚"},
    {"symbol": "002594", "name": "比亚迪", "sector": "新能源/汽车", "dividend_yield": 0.5, "state_ownership": 2.0, "reason": "新能源车全球龙头，垂直整合"},
    {"symbol": "600276", "name": "恒瑞医药", "sector": "医药/创新药", "dividend_yield": 1.2, "state_ownership": 3.0, "reason": "创新药龙头，研发壁垒"},
    {"symbol": "300760", "name": "迈瑞医疗", "sector": "医疗器械/医药", "dividend_yield": 1.5, "state_ownership": 2.0, "reason": "医疗器械龙头，全球化布局"},
    {"symbol": "600941", "name": "中国移动", "sector": "通信/运营商", "dividend_yield": 4.5, "state_ownership": 70.0, "reason": "通信基础设施，数字经济底座"},
    {"symbol": "601728", "name": "中国电信", "sector": "通信/运营商", "dividend_yield": 2.5, "state_ownership": 65.0, "reason": "云计算IDC增长，数字化转型受益"},
    {"symbol": "688981", "name": "中芯国际", "sector": "半导体/芯片", "dividend_yield": 0.3, "state_ownership": 10.0, "reason": "芯片制造龙头，国产替代核心"},
    {"symbol": "002371", "name": "北方华创", "sector": "半导体/设备", "dividend_yield": 0.4, "state_ownership": 8.0, "reason": "半导体设备龙头，国产替代"},
]

FALLBACK_INDEX = {
    "latest": {"date": datetime.now().strftime("%Y-%m-%d"), "close": 3300, "open": 3280, "high": 3320, "low": 3270},
    "returns": {"1m": 2.5, "3m": 5.0, "6m": 8.0, "1y": 12.0},
    "history": [],
}

FALLBACK_RECOMMENDATIONS = {
    "recommendations": [
        {"symbol":"600519","name":"贵州茅台","final_score":78.5,"ias_score":75.0,"timing_score":82.0,"recommendation":"⭐⭐⭐⭐ 推荐","is_recommended":True,"reason":"品牌护城河极深，越陈越香，产品恒久需求"},
        {"symbol":"600900","name":"长江电力","final_score":82.3,"ias_score":80.0,"timing_score":84.6,"recommendation":"⭐⭐⭐⭐ 推荐","is_recommended":True,"reason":"水电资产永续经营，现金流稳定，高分红"},
        {"symbol":"601939","name":"建设银行","final_score":76.8,"ias_score":72.0,"timing_score":81.6,"recommendation":"⭐⭐⭐⭐ 推荐","is_recommended":True,"reason":"国有大行，分红率高，国家金融安全基石"},
        {"symbol":"600436","name":"片仔癀","final_score":74.2,"ias_score":78.0,"timing_score":70.4,"recommendation":"⭐⭐⭐⭐ 推荐","is_recommended":True,"reason":"国家保密配方，越久越值钱，老龄化受益"},
        {"symbol":"601088","name":"中国神华","final_score":80.1,"ias_score":76.0,"timing_score":84.2,"recommendation":"⭐⭐⭐⭐ 推荐","is_recommended":True,"reason":"煤炭电力铁路一体化，超高分红，国有控股"},
    ],
    "total": 5,
    "errors": [],
    "note": "离线回退数据（核心引擎未加载）",
}


# ========== 离线数据构建（无需akshare） ==========

# 数据文件目录（GitHub Actions 定时刷新的 JSON 缓存）
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def load_cached_json(filename: str) -> dict | None:
    """加载 GitHub Actions 预计算的数据缓存"""
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def build_offline_stock_data(stock_info: dict) -> dict:
    """
    基于预定义股票池元数据构建评分所需数据，无需实时数据源。
    用于Vercel Serverless环境下akshare不可用时的快速回退。
    """
    sector = stock_info.get("sector", "")
    div_yield = stock_info.get("dividend_yield", 0)
    state_pct = stock_info.get("state_ownership", 0)
    
    # 根据行业判断政策支持级别
    policy_sectors_strong = ["半导体", "芯片", "新能源", "AI", "人工智能", "军工", "种业"]
    policy_sectors_moderate = ["中药", "水电", "核电", "通信", "创新药", "高端制造", "银行"]
    
    policy_level = "none"
    for kw in policy_sectors_strong:
        if kw in sector:
            policy_level = "strong"
            break
    if policy_level == "none":
        for kw in policy_sectors_moderate:
            if kw in sector:
                policy_level = "moderate"
                break
    
    # 高分红行业判断
    high_div_sectors = ["银行", "煤炭", "石油", "电力", "水电", "通信", "高速公路"]
    is_high_div = div_yield >= 3.0 or any(kw in sector for kw in high_div_sectors)
    
    # 护城河评估（基于行业）
    moat_sectors = {"白酒": 85, "中药": 80, "水电": 75, "调味品": 80, "银行": 70, "保险": 65}
    moat_base = 50
    for kw, score in moat_sectors.items():
        if kw in sector:
            moat_base = score
            break
    
    # 全球化评估
    global_sectors = {"家电": 60, "新能源": 55, "半导体": 40, "医疗器械": 50}
    global_base = 10
    for kw, score in global_sectors.items():
        if kw in sector:
            global_base = score
            break
    
    return {
        "industry": {
            "order_growth": 60, "capacity_utilization": 65,
            "price_trend": 55, "policy_level": policy_level,
            "revenue_growth": 12, "profit_growth": 10, "roe_trend": 8,
            "etf_flow": 40, "sector_flow": 45, "rank_pct": 50,
            "pe_percentile": 40, "pb_percentile": 35,
        },
        "company": {
            "pe_percentile": 30, "pb_percentile": 35,
            "ps_ratio": 3, "peg_ratio": 1.0, "ev_ebitda": 10,
            "roe_5y": 18 if is_high_div else 22, "roic": 12 if is_high_div else 16,
            "gross_margin": 55 if is_high_div else 65,
            "net_margin": 20 if is_high_div else 30,
            "op_cashflow": 12 if is_high_div else 15,
            "market_share": 55, "cost_advantage": 50,
            "brand_power": moat_base, "channel": 55,
            "patents": 40, "barrier": moat_base,
            "overseas_revenue_pct": global_base // 2,
            "overseas_orders": global_base // 3,
            "global_clients": global_base // 2,
            "overseas_capacity": global_base // 4,
        },
        "capital": {
            "day20_inflow": 0.05, "ema_trend": 0.03,
            "shareholder_change": -0.02, "avg_holding_increase": 0.01,
            "lhb_net_buy": 0.1, "lhb_retail_excluded": state_pct > 5,
            "block_premium_pct": 1.0, "block_institution_buy": state_pct > 10,
            "fund_increase_ratio": 0.02, "fund_count_change": 0.05,
        },
        "momentum": {
            "ret_20d": 0.02, "ret_60d": 0.04, "ret_120d": 0.06,
            "sector_rank_pct": 55,
            "ma20": 100, "ma60": 95, "ma120": 90, "ma250": 85,
            "price": 100,
            "vol_up_ratio": 0.45, "vol_down_ratio": 0.35,
            "atr_pct": 2.5, "beta": 0.9, "annual_vol": 28,
        },
        "event": {
            "major_order": 0, "policy_support": 2 if policy_level in ("strong", "moderate") else 0,
            "buyback": 0, "executive_buy": 0,
            "reduction": 0, "financial_risk": 0, "regulatory_investigation": 0,
        },
        "timing": {
            "current_pe": 15, "pe_percentile": 30,
            "industry_avg_pe": 20,
            "price": 100, "ma60": 95, "ma120": 90, "ma250": 85,
            "fcf": 500, "market_cap": 8000,
        },
        "meta": {
            "symbol": stock_info["symbol"],
            "name": stock_info["name"],
            "sector": sector,
            "dividend_yield": div_yield,
            "state_ownership": state_pct,
            "reason": stock_info.get("reason", ""),
            "data_source": "offline",
            "collected_at": datetime.now().isoformat(),
        }
    }


# ========== 响应模型 ==========

class StockRecommendRequest(BaseModel):
    symbols: Optional[list] = None


class APIResponse(BaseModel):
    model_config = {"json_schema_extra": {}}
    success: bool = True
    data: Optional[dict | list] = None
    message: str = ""
    timestamp: str = ""


# ========== API端点 ==========

@app.get("/")
async def root():
    """API根路径"""
    return JSONResponse({
        "name": "Halo - 中国股市投资分析系统",
        "version": "1.0.0",
        "description": "基于IAS评分模型 + 买入时机评估的智能选股系统",
        "endpoints": {
            "/api/stocks/recommend": "获取股票推荐列表",
            "/api/stocks/{symbol}": "单只股票分析",
            "/api/stocks/batch": "批量股票分析",
            "/api/index": "指数数据",
            "/api/market/overview": "市场概览",
            "/api/cron/refresh": "定时刷新数据",
            "/api/health": "健康检查",
        }
    })


@app.get("/api/health")
async def health_check():
    """健康检查"""
    engine_ok = _lazy_import()
    return JSONResponse({
        "status": "healthy",
        "engine_loaded": engine_ok,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    })


@app.get("/api/index")
async def get_index_data(index_code: str = Query("sh000001", description="指数代码")):
    """
    获取指数数据
    
    - sh000001: 上证指数
    - sz399001: 深证成指
    """
    cache_key = f"index_{index_code}"
    cached = cache_get(cache_key)
    if cached:
        return JSONResponse({"success": True, "data": cached, "timestamp": datetime.now().isoformat()})
    
    # 优先使用 GitHub Actions 预计算的指数数据
    index_cache = load_cached_json("index_data.json")
    if index_cache:
        idx = index_cache.get("indices", {}).get(index_code)
        if idx and "error" not in idx:
            cache_set(cache_key, idx)
            return JSONResponse({"success": True, "data": idx, "timestamp": datetime.now().isoformat()})
    
    # 内联回退
    _lazy_import()
    if data_collector is None:
        data = copy.deepcopy(FALLBACK_INDEX)
        if index_code == "sz399001":
            data["latest"]["close"] = 10800
        cache_set(cache_key, data)
        return JSONResponse({"success": True, "data": data, "timestamp": datetime.now().isoformat()})
    
    data = data_collector.get_index_data(index_code)
    if "error" in data:
        data = copy.deepcopy(FALLBACK_INDEX)
        if index_code == "sz399001":
            data["latest"]["close"] = 10800
        print(f"[WARN] 指数数据获取失败，使用回退数据", flush=True)
    
    cache_set(cache_key, data)
    return JSONResponse({"success": True, "data": data, "timestamp": datetime.now().isoformat()})


@app.get("/api/stocks/recommend")
async def get_recommendations(
    limit: int = Query(20, description="返回数量", ge=1, le=50),
    min_score: float = Query(0, description="最低评分", ge=0, le=100),
    sector: Optional[str] = Query(None, description="行业筛选"),
    refresh: bool = Query(False, description="强制刷新"),
):
    """
    获取股票推荐列表
    
    按照 IAS(50%) + 买入时机(50%) 综合评分排名
    """
    cache_key = f"recommendations_{limit}_{min_score}_{sector}"
    if not refresh:
        cached = cache_get(cache_key)
        if cached:
            return JSONResponse({"success": True, "data": cached, "timestamp": datetime.now().isoformat()})
    
    # 优先使用 GitHub Actions 预计算的数据
    cached_data = load_cached_json("recommendations.json")
    if cached_data and not refresh:
        recs = cached_data.get("recommendations", [])
        if sector:
            recs = [r for r in recs if sector in r.get("reason", "") or sector in r.get("name", "")]
        recs = [r for r in recs if r["final_score"] >= min_score][:limit]
        response_data = {
            "recommendations": recs,
            "total": len(recs),
            "errors": cached_data.get("errors", []),
            "timestamp": cached_data.get("updated_at", datetime.now().isoformat()),
            "note": f"数据来自 GitHub Actions 定时刷新 ({cached_data.get('updated_at', '未知')})",
        }
        cache_set(cache_key, response_data)
        return JSONResponse({"success": True, "data": response_data, "timestamp": datetime.now().isoformat()})
    
    # 引擎不可用时使用内联回退数据
    if not _lazy_import():
        fb = copy.deepcopy(FALLBACK_RECOMMENDATIONS)
        fb["timestamp"] = datetime.now().isoformat()
        cache_set(cache_key, fb)
        return JSONResponse({"success": True, "data": fb, "timestamp": datetime.now().isoformat()})
    
    results = []
    errors = []
    
    # 遍历优质股票池（全部评分，再按limit截断输出）
    # 优先过滤沪深300成分股
    base_pool = QUALITY_STOCK_POOL if QUALITY_STOCK_POOL else INLINE_STOCK_POOL
    hs300_data = load_cached_json("hs300_constituents.json")
    hs300_codes = {s["symbol"] for s in hs300_data.get("stocks", [])} if hs300_data else set()
    if filter_hs300 and hs300_codes:
        pool = filter_hs300(base_pool, hs300_codes)
    else:
        pool = base_pool
    if sector:
        pool = [s for s in pool if sector in s.get("sector", "")]
    
    for stock_info in pool:
        symbol = stock_info["symbol"]
        name = stock_info["name"]
        
        # 尝试实时数据，失败则回退到离线评分
        try:
            stock_data = data_collector.collect_stock_data(symbol, name)
        except Exception:
            stock_data = build_offline_stock_data(stock_info)
        
        # 添加元数据
        stock_data["meta"]["sector"] = stock_info.get("sector", "")
        stock_data["meta"]["dividend_yield"] = stock_info.get("dividend_yield", 0)
        stock_data["meta"]["state_ownership"] = stock_info.get("state_ownership", 0)
        stock_data["meta"]["reason"] = stock_info.get("reason", "")
        
        try:
            rec = recommendation_engine.recommend(stock_data)
            rec_dict = rec.to_dict()
            rec_dict["reason"] = stock_info.get("reason", "")
            rec_dict["data_source"] = stock_data.get("meta", {}).get("data_source", "unknown")
            
            if rec_dict["final_score"] >= min_score:
                results.append(rec_dict)
                
        except Exception as e:
            print(f"[ERROR] 评分失败 {symbol}: {e}", flush=True)
            errors.append({"symbol": symbol, "name": name, "error": "评分失败"})
    
    # 按最终评分降序
    results.sort(key=lambda r: r["final_score"], reverse=True)
    
    # 截断到limit
    results = results[:limit]
    
    response_data = {
        "recommendations": results,
        "total": len(results),
        "errors": errors,
        "timestamp": datetime.now().isoformat(),
        "note": "数据可能存在缓存延迟。实际投资请以实时数据为准。"
    }
    
    cache_set(cache_key, response_data)
    return JSONResponse({"success": True, "data": response_data, "timestamp": datetime.now().isoformat()})


@app.get("/api/stocks/{symbol}")
async def get_stock_analysis(
    symbol: str,
    name: str = Query("", description="股票名称"),
    refresh: bool = Query(False, description="强制刷新"),
):
    """
    获取单只股票的完整分析

    - IAS评分详情
    - 买入时机评估
    - 7大特征检查
    - 机构一致性评分
    """
    _lazy_import()
    cache_key = f"stock_{symbol}"
    if not refresh:
        cached = cache_get(cache_key)
        if cached:
            return JSONResponse({"success": True, "data": cached, "timestamp": datetime.now().isoformat()})
    
    if not name:
        # 从股票池查找名称
        for s in QUALITY_STOCK_POOL:
            if s["symbol"] == symbol:
                name = s["name"]
                break
    
    if not name:
        name = symbol
    
    # 查找股票池中的元数据
    pool_info = None
    for s in QUALITY_STOCK_POOL:
        if s["symbol"] == symbol:
            pool_info = s
            if not name or name == symbol:
                name = s["name"]
            break
    
    # 尝试实时数据，失败则回退到离线评分
    try:
        stock_data = data_collector.collect_stock_data(symbol, name)
    except Exception:
        stock_data = build_offline_stock_data(pool_info if pool_info else {
            "symbol": symbol, "name": name,
            "sector": "", "dividend_yield": 0, "state_ownership": 0, "reason": ""
        })
    
    # 补充元数据
    if pool_info:
        stock_data["meta"]["sector"] = pool_info.get("sector", "")
        stock_data["meta"]["dividend_yield"] = pool_info.get("dividend_yield", 0)
        stock_data["meta"]["state_ownership"] = pool_info.get("state_ownership", 0)
        stock_data["meta"]["reason"] = pool_info.get("reason", "")
    
    try:
        rec = recommendation_engine.recommend(stock_data)
        result = rec.to_dict()
        cache_set(cache_key, result)
        return JSONResponse({"success": True, "data": result, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        print(f"[ERROR] 股票分析失败 {symbol}: {e}", flush=True)
        return JSONResponse({
            "success": False,
            "message": "分析失败，请稍后重试",
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


@app.post("/api/stocks/batch")
async def batch_analysis(request: StockRecommendRequest):
    """
    批量股票分析
    
    支持自定义股票列表
    """
    _lazy_import()
    symbols = request.symbols
    if not symbols:
        # 默认使用优质股票池前10只
        symbols = [s["symbol"] for s in QUALITY_STOCK_POOL[:10]]
    
    results = []
    errors = []
    
    for symbol in symbols:
        # 查找名称
        name = symbol
        meta = {}
        for s in QUALITY_STOCK_POOL:
            if s["symbol"] == symbol:
                name = s["name"]
                meta = s
                break
        
        # 尝试实时数据，失败则回退到离线评分
        try:
            stock_data = data_collector.collect_stock_data(symbol, name)
        except Exception:
            print(f"[INFO] 批量分析 {symbol} 回退到离线数据", flush=True)
            stock_data = build_offline_stock_data(meta if meta else {
                "symbol": symbol, "name": name,
                "sector": "", "dividend_yield": 0, "state_ownership": 0, "reason": ""
            })
        
        if meta:
            stock_data["meta"]["sector"] = meta.get("sector", "")
            stock_data["meta"]["dividend_yield"] = meta.get("dividend_yield", 0)
            stock_data["meta"]["state_ownership"] = meta.get("state_ownership", 0)
            stock_data["meta"]["reason"] = meta.get("reason", "")
        
        try:
            rec = recommendation_engine.recommend(stock_data)
            rec_dict = rec.to_dict()
            if meta:
                rec_dict["reason"] = meta.get("reason", "")
            results.append(rec_dict)
        except Exception as e:
            print(f"[ERROR] 批量评分失败 {symbol}: {e}", flush=True)
            errors.append({"symbol": symbol, "error": "评分失败"})
    
    results.sort(key=lambda r: r["final_score"], reverse=True)
    
    return JSONResponse({
        "success": True,
        "data": {
            "recommendations": results,
            "total": len(results),
            "errors": errors,
        },
        "timestamp": datetime.now().isoformat()
    })


@app.get("/api/market/overview")
async def market_overview():
    """
    市场概览
    
    包含上证/深成指数、行业板块表现等
    """
    _lazy_import()
    cache_key = "market_overview"
    cached = cache_get(cache_key)
    if cached:
        return JSONResponse({"success": True, "data": cached, "timestamp": datetime.now().isoformat()})
    
    # 优先使用 GitHub Actions 预计算的市场概览
    cached_overview = load_cached_json("market_overview.json")
    if cached_overview:
        cache_set(cache_key, cached_overview)
        return JSONResponse({"success": True, "data": cached_overview, "timestamp": datetime.now().isoformat()})
    
    overview = {
        "indices": {},
        "sectors": [],
        "timestamp": datetime.now().isoformat(),
    }
    
    # 获取上证指数
    if data_collector is not None:
        sh_data = data_collector.get_index_data("sh000001")
        if "error" not in sh_data:
            overview["indices"]["shanghai"] = {
                "name": "上证指数",
                "latest": sh_data.get("latest", {}),
                "returns": sh_data.get("returns", {}),
            }
        
        # 获取深成指数
        sz_data = data_collector.get_index_data("sz399001")
        if "error" not in sz_data:
            overview["indices"]["shenzhen"] = {
                "name": "深证成指",
                "latest": sz_data.get("latest", {}),
                "returns": sz_data.get("returns", {}),
            }
        
        # 获取行业板块
        sectors = data_collector.get_sector_data()
        overview["sectors"] = sectors[:10]
    
    cache_set(cache_key, overview)
    return JSONResponse({"success": True, "data": overview, "timestamp": datetime.now().isoformat()})


@app.get("/api/cron/refresh")
async def cron_refresh(
    request: Request,
    time: str = Query("0925", description="刷新时间标识"),
):
    """
    定时刷新端点（由Vercel Cron Jobs触发）
    
    定时：
    - 9:25 (UTC 1:25) - 开盘集合竞价后
    - 13:05 (UTC 5:05) - 午盘开盘后
    - 14:50 (UTC 6:50) - 收盘前
    
    需要 CRON_SECRET 环境变量鉴权
    本地开发设置 CRON_SECRET=dev 即可
    Vercel Cron Jobs 自动通过 Authorization header 发送密钥
    """
    _lazy_import()
    if not verify_cron_secret(request):
        return JSONResponse({
            "success": False,
            "message": "未授权：需要有效的 CRON_SECRET",
        }, status_code=401)
    
    # 清除所有缓存
    _cache.clear()
    
    # 重新加载数据
    try:
        # 更新指数数据
        data_collector.get_index_data("sh000001")
        data_collector.get_index_data("sz399001")
        
        # 更新前10只核心股票数据
        for stock_info in QUALITY_STOCK_POOL[:10]:
            try:
                data_collector.collect_stock_data(stock_info["symbol"], stock_info["name"])
            except Exception:
                pass
        
        return JSONResponse({
            "success": True,
            "message": f"数据刷新成功 (时间标识: {time})",
            "refreshed_at": datetime.now().isoformat(),
            "next_refresh": {
                "0925": "开盘集合竞价后",
                "1305": "午盘开盘后",
                "1450": "收盘前",
            }.get(time, "未知")
        })
        
    except Exception as e:
        print(f"[ERROR] 定时刷新失败 time={time}: {e}", flush=True)
        return JSONResponse({
            "success": False,
            "message": "数据刷新失败，请稍后重试",
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


@app.get("/api/stocks/quality-pool")
async def get_quality_pool():
    """获取优质股票池列表"""
    _lazy_import()
    pool = QUALITY_STOCK_POOL if QUALITY_STOCK_POOL else INLINE_STOCK_POOL
    return JSONResponse({
        "success": True,
        "data": {
            "pool": pool,
            "total": len(pool),
            "description": "符合7大选股特征的中国A股优质标的池",
            "features": [
                "1. 资产随时间增值（越久越值钱）",
                "2. 产品恒久需求",
                "3. 内生性增长（不需再投入）",
                "4. 高分红率",
                "5. 中国国有资本投资加仓",
                "6. 未来社会发展趋势中受益",
                "7. 符合中国政府政策方向",
            ]
        },
        "timestamp": datetime.now().isoformat()
    })


# ========== 模拟交易 API ==========

@app.get("/api/sim/positions")
async def get_sim_positions():
    """获取模拟持仓列表"""
    _lazy_import()
    try:
        positions = sim_engine.get_all_positions()
        return JSONResponse({
            "success": True,
            "data": {
                "positions": [p.to_dict() for p in positions],
                "total": len(positions),
            },
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": "获取持仓失败"}, status_code=500)


@app.get("/api/sim/trades")
async def get_sim_trades(limit: int = Query(50, description="返回记录数")):
    """获取模拟交易记录"""
    _lazy_import()
    try:
        trades = sim_engine.get_trades(limit)
        return JSONResponse({
            "success": True,
            "data": {
                "trades": [t.to_dict() for t in trades],
                "total": len(trades),
            },
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": "获取记录失败"}, status_code=500)


@app.get("/api/sim/summary")
async def get_sim_summary():
    """获取模拟交易汇总统计"""
    _lazy_import()
    try:
        summary = sim_engine.get_summary()
        return JSONResponse({
            "success": True,
            "data": summary,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": "获取统计失败"}, status_code=500)


@app.get("/api/sim/chart/{symbol}")
async def get_sim_chart(symbol: str):
    """获取单只股票的收益曲线数据"""
    _lazy_import()
    try:
        trades = sim_engine.get_trades_by_symbol(symbol)
        # 构建收益曲线：从买入日起按时间排列
        chart_data = []
        cost_basis = None
        for t in sorted(trades, key=lambda x: x.trade_date):
            if t.trade_type == "buy" and cost_basis is None:
                cost_basis = t.price
            point = {
                "date": t.trade_date,
                "type": t.trade_type,
                "price": t.price,
                "return_pct": round((t.price - cost_basis) / cost_basis * 100, 2) if cost_basis and cost_basis > 0 else 0,
            }
            chart_data.append(point)
            if t.trade_type == "sell":
                cost_basis = None  # 重置，等待下次买入
        
        return JSONResponse({
            "success": True,
            "data": {
                "symbol": symbol,
                "chart": chart_data,
            },
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        return JSONResponse({"success": False, "message": "获取曲线失败"}, status_code=500)


# ========== Vercel Serverless 入口 ==========

# 为Vercel Python Runtime提供ASGI应用
# Vercel自动检测app变量
