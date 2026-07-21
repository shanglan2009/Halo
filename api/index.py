"""
Halo API — 纯内联版本（零外部依赖）
Vercel Serverless 下稳定运行，所有数据来自内联常量或 data/ JSON 文件
"""
import sys
import os
import json
import secrets
import copy
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Halo", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

# ========== 内联股票池（30只，始终可用） ==========
STOCK_POOL = [
    {"symbol":"600519","name":"贵州茅台","sector":"白酒/消费","dividend_yield":2.5,"state_ownership":4.5,"reason":"品牌护城河极深"},
    {"symbol":"000858","name":"五粮液","sector":"白酒/消费","dividend_yield":2.2,"state_ownership":3.0,"reason":"浓香龙头"},
    {"symbol":"600809","name":"山西汾酒","sector":"白酒/消费","dividend_yield":1.8,"state_ownership":2.5,"reason":"清香型龙头"},
    {"symbol":"600436","name":"片仔癀","sector":"中药/消费","dividend_yield":2.0,"state_ownership":5.0,"reason":"国家保密配方"},
    {"symbol":"000538","name":"云南白药","sector":"中药/消费","dividend_yield":3.5,"state_ownership":10.0,"reason":"百年品牌"},
    {"symbol":"600085","name":"同仁堂","sector":"中药/消费","dividend_yield":2.5,"state_ownership":8.0,"reason":"350年老字号"},
    {"symbol":"600900","name":"长江电力","sector":"水电/清洁能源","dividend_yield":3.8,"state_ownership":55.0,"reason":"永续经营"},
    {"symbol":"600886","name":"国投电力","sector":"水电/清洁能源","dividend_yield":3.2,"state_ownership":45.0,"reason":"清洁能源龙头"},
    {"symbol":"601088","name":"中国神华","sector":"煤炭/能源","dividend_yield":6.5,"state_ownership":60.0,"reason":"超高分红"},
    {"symbol":"601857","name":"中国石油","sector":"石油/能源","dividend_yield":4.5,"state_ownership":80.0,"reason":"能源安全核心"},
    {"symbol":"600028","name":"中国石化","sector":"石油/能源","dividend_yield":5.5,"state_ownership":70.0,"reason":"稳定高分红"},
    {"symbol":"601939","name":"建设银行","sector":"银行/金融","dividend_yield":5.8,"state_ownership":60.0,"reason":"国有大行"},
    {"symbol":"601398","name":"工商银行","sector":"银行/金融","dividend_yield":5.5,"state_ownership":65.0,"reason":"全球最大银行"},
    {"symbol":"601288","name":"农业银行","sector":"银行/金融","dividend_yield":5.6,"state_ownership":70.0,"reason":"三农金融"},
    {"symbol":"600036","name":"招商银行","sector":"银行/金融","dividend_yield":4.5,"state_ownership":25.0,"reason":"零售之王"},
    {"symbol":"601318","name":"中国平安","sector":"保险/金融","dividend_yield":4.2,"state_ownership":5.0,"reason":"综合金融"},
    {"symbol":"600690","name":"海尔智家","sector":"家电/消费","dividend_yield":3.0,"state_ownership":10.0,"reason":"全球化龙头"},
    {"symbol":"000333","name":"美的集团","sector":"家电/消费","dividend_yield":3.5,"state_ownership":8.0,"reason":"综合龙头"},
    {"symbol":"000651","name":"格力电器","sector":"家电/消费","dividend_yield":4.5,"state_ownership":15.0,"reason":"空调霸主"},
    {"symbol":"603288","name":"海天味业","sector":"调味品/消费","dividend_yield":1.8,"state_ownership":2.0,"reason":"调味品龙头"},
    {"symbol":"600887","name":"伊利股份","sector":"食品饮料/消费","dividend_yield":3.2,"state_ownership":5.0,"reason":"乳业龙头"},
    {"symbol":"002415","name":"海康威视","sector":"AI/安防/科技","dividend_yield":2.8,"state_ownership":8.0,"reason":"AI视觉龙头"},
    {"symbol":"300750","name":"宁德时代","sector":"新能源/电池","dividend_yield":0.8,"state_ownership":3.0,"reason":"动力电池龙头"},
    {"symbol":"002594","name":"比亚迪","sector":"新能源/汽车","dividend_yield":0.5,"state_ownership":2.0,"reason":"新能源车龙头"},
    {"symbol":"600276","name":"恒瑞医药","sector":"医药/创新药","dividend_yield":1.2,"state_ownership":3.0,"reason":"创新药龙头"},
    {"symbol":"300760","name":"迈瑞医疗","sector":"医疗器械/医药","dividend_yield":1.5,"state_ownership":2.0,"reason":"器械龙头"},
    {"symbol":"600941","name":"中国移动","sector":"通信/运营商","dividend_yield":4.5,"state_ownership":70.0,"reason":"数字底座"},
    {"symbol":"601728","name":"中国电信","sector":"通信/运营商","dividend_yield":2.5,"state_ownership":65.0,"reason":"云IDC增长"},
    {"symbol":"688981","name":"中芯国际","sector":"半导体/芯片","dividend_yield":0.3,"state_ownership":10.0,"reason":"芯片龙头"},
    {"symbol":"002371","name":"北方华创","sector":"半导体/设备","dividend_yield":0.4,"state_ownership":8.0,"reason":"设备龙头"},
]

# ========== 数据缓存 ==========
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
_cache = {}
CACHE_TTL = timedelta(hours=4)

def cache_get(k): 
    if k in _cache:
        d, t = _cache[k]
        if datetime.now() - t < CACHE_TTL: return d
    return None

def cache_set(k, v): _cache[k] = (v, datetime.now())

def load_json(fn):
    p = os.path.join(DATA_DIR, fn)
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f: return json.load(f)
        except: pass
    return None

# ========== 安全 ==========
CRON_SECRET = os.environ.get("CRON_SECRET","")
def verify_cron(r):
    if not CRON_SECRET: return False
    return secrets.compare_digest(r.headers.get("Authorization",""), f"Bearer {CRON_SECRET}")

# ========== API ==========
@app.get("/api/health")
async def health():
    return JSONResponse({"status":"healthy","version":"2.0","timestamp":datetime.now().isoformat()})

@app.get("/api/index")
async def get_index(index_code: str = Query("sh000001")):
    ck = f"idx_{index_code}"
    c = cache_get(ck)
    if c: return JSONResponse({"success":True,"data":c,"timestamp":datetime.now().isoformat()})
    j = load_json("index_data.json")
    if j:
        idx = j.get("indices",{}).get(index_code)
        if idx: cache_set(ck, idx); return JSONResponse({"success":True,"data":idx,"timestamp":datetime.now().isoformat()})
    # fallback
    d = {"latest":{"date":datetime.now().strftime("%Y-%m-%d"),"close":3300 if "sh" in index_code else 10800},"returns":{"1m":0,"3m":0,"1y":0}}
    cache_set(ck,d)
    return JSONResponse({"success":True,"data":d,"timestamp":datetime.now().isoformat()})

@app.get("/api/stocks/recommend")
async def recommend(limit:int=Query(20),min_score:float=Query(0),sector:str=Query(None),refresh:bool=Query(False)):
    ck = f"rec_{limit}_{min_score}_{sector}"
    if not refresh:
        c = cache_get(ck)
        if c: return JSONResponse({"success":True,"data":c,"timestamp":datetime.now().isoformat()})
    # 从JSON缓存读取
    j = load_json("recommendations.json")
    if j:
        recs = j.get("recommendations",[])
        if sector: recs = [r for r in recs if sector in (r.get("reason","")+r.get("name",""))]
        recs = [r for r in recs if r.get("final_score",0)>=min_score][:limit]
        resp = {"recommendations":recs,"total":len(recs),"errors":[],"timestamp":j.get("updated_at",""),"note":"GitHub Actions 定时刷新"}
        cache_set(ck,resp)
        return JSONResponse({"success":True,"data":resp,"timestamp":datetime.now().isoformat()})
    # 回退
    fb = {"recommendations":[],"total":0,"errors":[],"timestamp":"","note":"等待首次数据刷新"}
    cache_set(ck,fb)
    return JSONResponse({"success":True,"data":fb,"timestamp":datetime.now().isoformat()})

@app.get("/api/stocks/quality-pool")
async def quality_pool():
    return JSONResponse({"success":True,"data":{"pool":STOCK_POOL,"total":len(STOCK_POOL)},"timestamp":datetime.now().isoformat()})

@app.get("/api/market/overview")
async def market_overview():
    ck = "mkt"
    c = cache_get(ck)
    if c: return JSONResponse({"success":True,"data":c,"timestamp":datetime.now().isoformat()})
    j = load_json("market_overview.json")
    if j: cache_set(ck,j); return JSONResponse({"success":True,"data":j,"timestamp":datetime.now().isoformat()})
    return JSONResponse({"success":True,"data":{"timestamp":datetime.now().isoformat()},"timestamp":datetime.now().isoformat()})

@app.get("/api/cron/refresh")
async def cron_refresh(request: Request, time: str = Query("0925")):
    if not verify_cron(request):
        return JSONResponse({"success":False,"message":"未授权"},status_code=401)
    _cache.clear()
    return JSONResponse({"success":True,"message":f"刷新完成 {time}","refreshed_at":datetime.now().isoformat()})

# 空壳端点（避免前端报错）
@app.get("/api/sim/positions")
async def sim_positions():
    return JSONResponse({"success":True,"data":{"positions":[],"total":0},"timestamp":datetime.now().isoformat()})
@app.get("/api/sim/trades")
async def sim_trades():
    return JSONResponse({"success":True,"data":{"trades":[],"total":0},"timestamp":datetime.now().isoformat()})
@app.get("/api/sim/summary")
async def sim_summary():
    return JSONResponse({"success":True,"data":{"holdings":0,"total_pnl":0,"win_rate":0},"timestamp":datetime.now().isoformat()})
