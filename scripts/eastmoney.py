"""
Halo - 东方财富公开API数据获取
实时行情数据，无需akshare，轻量快速

接口：
- 指数实时数据
- 个股实时行情（价格/PE/市值等）
- 个股历史K线（最高价）
"""
import json
import urllib.request
from datetime import datetime, timedelta
from typing import Optional


def _fetch(url: str) -> Optional[dict]:
    """通用HTTP GET请求"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/",
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def get_index_realtime(market: str = "sh") -> dict:
    """
    获取指数实时数据
    
    market: "sh"=上证指数, "sz"=深证成指
    返回: {name, price, change_pct, change_amt, open, high, low, volume, amount}
    """
    secid = "1.000001" if market == "sh" else "0.399001"
    url = (f"https://push2.eastmoney.com/api/qt/stock/get?"
           f"secid={secid}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170")
    
    data = _fetch(url)
    if not data or not data.get("data"):
        return {"error": "无法获取指数数据"}
    
    d = data["data"]
    return {
        "name": d.get("f58", ""),
        "price": d.get("f43", 0) / 100.0 if d.get("f43") else 0,
        "change_pct": d.get("f170", 0) / 100.0 if d.get("f170") else 0,
        "change_amt": d.get("f169", 0) / 100.0 if d.get("f169") else 0,
        "open": d.get("f46", 0) / 100.0 if d.get("f46") else 0,
        "high": d.get("f44", 0) / 100.0 if d.get("f44") else 0,
        "low": d.get("f45", 0) / 100.0 if d.get("f45") else 0,
        "volume": d.get("f47", 0),
        "amount": d.get("f48", 0),
        "updated_at": datetime.now().isoformat(),
    }


def get_stock_realtime(symbol: str) -> dict:
    """
    获取个股实时行情
    
    返回: {name, price, pe_ttm, total_mcap, change_pct, high, low, open}
    """
    # 判断市场
    if symbol.startswith("6"):
        secid = f"1.{symbol}"
    elif symbol.startswith(("0", "3")):
        secid = f"0.{symbol}"
    else:
        return {"error": f"不支持的股票代码: {symbol}"}
    
    url = (f"https://push2.eastmoney.com/api/qt/stock/get?"
           f"secid={secid}&fields=f43,f44,f45,f46,f57,f58,f60,f107,f170,f171")
    
    data = _fetch(url)
    if not data or not data.get("data"):
        return {"error": "无法获取实时行情"}
    
    d = data["data"]
    return {
        "name": d.get("f58", ""),
        "price": d.get("f43", 0) / 100.0 if d.get("f43") else 0,
        "pe_ttm": d.get("f107", 0) / 100.0 if d.get("f107") else 0,
        "total_mcap": d.get("f171", 0),
        "change_pct": d.get("f170", 0) / 100.0 if d.get("f170") else 0,
        "high": d.get("f44", 0) / 100.0 if d.get("f44") else 0,
        "low": d.get("f45", 0) / 100.0 if d.get("f45") else 0,
        "open": d.get("f46", 0) / 100.0 if d.get("f46") else 0,
        "updated_at": datetime.now().isoformat(),
    }


def get_stock_history_high(symbol: str) -> dict:
    """
    获取个股历史最高价和近1年最高价
    
    返回: {all_time_high, all_time_high_date, year_high, year_high_date}
    """
    if symbol.startswith("6"):
        secid = f"1.{symbol}"
    elif symbol.startswith(("0", "3")):
        secid = f"0.{symbol}"
    else:
        return {"all_time_high": 0, "year_high": 0}
    
    # 获取全部历史日K线（前复权）
    url = (f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6&"
           f"fields2=f51,f52,f53,f54,f55,f56,f57&"
           f"klt=101&fqt=1&end=20500101&lmt=10000")
    
    data = _fetch(url)
    if not data or not data.get("data") or not data["data"].get("klines"):
        return {"all_time_high": 0, "year_high": 0}
    
    klines = data["data"]["klines"]
    all_time_high = 0.0
    all_time_high_date = ""
    year_high = 0.0
    year_high_date = ""
    
    # 计算1年前日期
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    
    for line in klines:
        parts = line.split(",")
        if len(parts) < 4:
            continue
        date_str = parts[0]
        high_price = float(parts[3]) if parts[3] != "-" else 0
        
        if high_price > all_time_high:
            all_time_high = high_price
            all_time_high_date = date_str
        
        if date_str >= one_year_ago and high_price > year_high:
            year_high = high_price
            year_high_date = date_str
    
    return {
        "all_time_high": round(all_time_high, 2),
        "all_time_high_date": all_time_high_date,
        "year_high": round(year_high, 2),
        "year_high_date": year_high_date,
    }


def get_full_stock_info(symbol: str) -> dict:
    """获取个股完整信息（实时行情+历史最高价）"""
    realtime = get_stock_realtime(symbol)
    if "error" in realtime:
        return realtime
    
    history = get_stock_history_high(symbol)
    realtime.update(history)
    return realtime


def get_index_both() -> dict:
    """同时获取上证和深证指数"""
    sh = get_index_realtime("sh")
    sz = get_index_realtime("sz")
    return {
        "shanghai": sh,
        "shenzhen": sz,
        "updated_at": datetime.now().isoformat(),
    }
