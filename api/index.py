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
from datetime import datetime, timedelta
from typing import Optional

# 确保项目根目录在Python路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel

from scripts.ias_engine import ias_engine
from scripts.timing_eval import timing_evaluator
from scripts.data_collector import data_collector
from scripts.recommendation import recommendation_engine, QUALITY_STOCK_POOL

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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== 安全配置 ==========
CRON_SECRET = os.environ.get("CRON_SECRET", "")
# 若未配置CRON_SECRET，允许本地开发环境无鉴权访问
DEV_MODE = os.environ.get("VERCEL_ENV", "development") == "development" and not os.environ.get("VERCEL")

def verify_cron_secret(request_secret: str = "") -> bool:
    """验证定时任务密钥"""
    if DEV_MODE and not CRON_SECRET:
        return True  # 本地开发允许
    if not CRON_SECRET:
        return False  # 生产环境未配置则拒绝
    return request_secret == CRON_SECRET


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
    return JSONResponse({
        "status": "healthy",
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
    
    data = data_collector.get_index_data(index_code)
    if "error" in data:
        return JSONResponse({"success": False, "message": data["error"], "timestamp": datetime.now().isoformat()})
    
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
    
    results = []
    errors = []
    
    # 遍历优质股票池
    pool = QUALITY_STOCK_POOL
    if sector:
        pool = [s for s in pool if sector in s.get("sector", "")]
    
    for stock_info in pool[:limit]:
        symbol = stock_info["symbol"]
        name = stock_info["name"]
        
        try:
            # 尝试采集数据
            stock_data = data_collector.collect_stock_data(symbol, name)
            
            # 添加元数据
            stock_data["meta"]["sector"] = stock_info.get("sector", "")
            stock_data["meta"]["dividend_yield"] = stock_info.get("dividend_yield", 0)
            stock_data["meta"]["state_ownership"] = stock_info.get("state_ownership", 0)
            stock_data["meta"]["reason"] = stock_info.get("reason", "")
            
            # 生成推荐
            rec = recommendation_engine.recommend(stock_data)
            rec_dict = rec.to_dict()
            rec_dict["reason"] = stock_info.get("reason", "")
            
            if rec_dict["final_score"] >= min_score:
                results.append(rec_dict)
                
        except Exception as e:
            errors.append({"symbol": symbol, "name": name, "error": str(e)})
    
    # 按最终评分降序
    results.sort(key=lambda r: r["final_score"], reverse=True)
    
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
    
    try:
        stock_data = data_collector.collect_stock_data(symbol, name)
        
        # 查找股票池中的元数据
        for s in QUALITY_STOCK_POOL:
            if s["symbol"] == symbol:
                stock_data["meta"]["sector"] = s.get("sector", "")
                stock_data["meta"]["dividend_yield"] = s.get("dividend_yield", 0)
                stock_data["meta"]["state_ownership"] = s.get("state_ownership", 0)
                stock_data["meta"]["reason"] = s.get("reason", "")
                break
        
        rec = recommendation_engine.recommend(stock_data)
        result = rec.to_dict()
        
        cache_set(cache_key, result)
        return JSONResponse({"success": True, "data": result, "timestamp": datetime.now().isoformat()})
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": f"分析失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


@app.post("/api/stocks/batch")
async def batch_analysis(request: StockRecommendRequest):
    """
    批量股票分析
    
    支持自定义股票列表
    """
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
        
        try:
            stock_data = data_collector.collect_stock_data(symbol, name)
            if meta:
                stock_data["meta"]["sector"] = meta.get("sector", "")
                stock_data["meta"]["dividend_yield"] = meta.get("dividend_yield", 0)
                stock_data["meta"]["state_ownership"] = meta.get("state_ownership", 0)
                stock_data["meta"]["reason"] = meta.get("reason", "")
            
            rec = recommendation_engine.recommend(stock_data)
            rec_dict = rec.to_dict()
            if meta:
                rec_dict["reason"] = meta.get("reason", "")
            results.append(rec_dict)
            
        except Exception as e:
            errors.append({"symbol": symbol, "error": str(e)})
    
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
    cache_key = "market_overview"
    cached = cache_get(cache_key)
    if cached:
        return JSONResponse({"success": True, "data": cached, "timestamp": datetime.now().isoformat()})
    
    overview = {
        "indices": {},
        "sectors": [],
        "timestamp": datetime.now().isoformat(),
    }
    
    # 获取上证指数
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
    time: str = Query("0925", description="刷新时间标识"),
    secret: str = Query("", description="CRON_SECRET密钥"),
):
    """
    定时刷新端点（由Vercel Cron Jobs触发）
    
    定时：
    - 9:25 (UTC 1:25) - 开盘集合竞价后
    - 13:05 (UTC 5:05) - 午盘开盘后
    - 14:50 (UTC 6:50) - 收盘前
    
    需要 CRON_SECRET 环境变量鉴权（本地开发环境自动放行）
    """
    if not verify_cron_secret(secret):
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
        return JSONResponse({
            "success": False,
            "message": f"刷新失败: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }, status_code=500)


@app.get("/api/stocks/quality-pool")
async def get_quality_pool():
    """获取优质股票池列表"""
    return JSONResponse({
        "success": True,
        "data": {
            "pool": QUALITY_STOCK_POOL,
            "total": len(QUALITY_STOCK_POOL),
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


# ========== Vercel Serverless 入口 ==========

# 为Vercel Python Runtime提供ASGI应用
# Vercel自动检测app变量
