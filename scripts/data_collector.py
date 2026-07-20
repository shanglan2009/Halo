"""
Halo - 数据采集模块
从AkShare、东方财富等免费数据源获取中国股市数据

数据源：
- AkShare: 行情/资金流/龙虎榜/行业数据
- 东方财富: 实时行情/财务数据
- 巨潮资讯: 财报/公告

注意：Tushare需要token，在环境变量TUSHARE_TOKEN中配置
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import numpy as np

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def safe_float(value, default=0.0) -> float:
    """安全转换为float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


class DataCollector:
    """数据采集器 - 从多个数据源获取股票数据"""
    
    def __init__(self):
        self.cache = {}
    
    def _cache_key(self, prefix: str, *args) -> str:
        return f"{prefix}_{'_'.join(str(a) for a in args)}"
    
    def _load_cache(self, key: str) -> Optional[dict]:
        """加载缓存数据"""
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 检查缓存是否在24小时内
                cached_time = data.get("_cached_at", "")
                if cached_time:
                    cached_dt = datetime.fromisoformat(cached_time)
                    if datetime.now() - cached_dt < timedelta(hours=24):
                        return data
            except Exception:
                pass
        return None
    
    def _save_cache(self, key: str, data: dict):
        """保存缓存数据"""
        data["_cached_at"] = datetime.now().isoformat()
        cache_file = os.path.join(CACHE_DIR, f"{key}.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    # ========== 指数数据 ==========
    
    def get_index_data(self, index_code: str = "sh000001") -> dict:
        """
        获取指数数据（上证指数/深成指）
        index_code: sh000001=上证指数, sz399001=深证成指
        """
        cache_key = self._cache_key("index", index_code)
        cached = self._load_cache(cache_key)
        if cached:
            return cached
        
        try:
            import akshare as ak
            
            if index_code == "sh000001":
                df = ak.stock_zh_index_daily(symbol="sh000001")
            elif index_code == "sz399001":
                df = ak.stock_zh_index_daily(symbol="sz399001")
            else:
                return {"error": f"不支持的指数代码: {index_code}"}
            
            if df is None or df.empty:
                return {"error": "无法获取指数数据"}
            
            # 最近一年数据
            df["date"] = pd.to_datetime(df["date"])
            one_year_ago = datetime.now() - timedelta(days=365)
            df_recent = df[df["date"] >= one_year_ago].copy()
            
            if df_recent.empty:
                df_recent = df.tail(250)
            
            result = {
                "latest": {
                    "date": df_recent["date"].iloc[-1].strftime("%Y-%m-%d"),
                    "close": safe_float(df_recent["close"].iloc[-1]),
                    "open": safe_float(df_recent["open"].iloc[-1]),
                    "high": safe_float(df_recent["high"].iloc[-1]),
                    "low": safe_float(df_recent["low"].iloc[-1]),
                    "volume": safe_float(df_recent["volume"].iloc[-1]),
                },
                "returns": {
                    "1m": safe_float(df_recent["close"].pct_change(20).iloc[-1] * 100),
                    "3m": safe_float(df_recent["close"].pct_change(60).iloc[-1] * 100),
                    "6m": safe_float(df_recent["close"].pct_change(120).iloc[-1] * 100),
                    "1y": safe_float(df_recent["close"].pct_change(250).iloc[-1] * 100) if len(df_recent) >= 250 else 0,
                },
                "history": [
                    {"date": row["date"].strftime("%Y-%m-%d"), "close": safe_float(row["close"])}
                    for _, row in df_recent.tail(60).iterrows()
                ]
            }
            
            self._save_cache(cache_key, result)
            return result
            
        except ImportError:
            return {"error": "请安装akshare: pip install akshare"}
        except Exception as e:
            return {"error": f"获取指数数据失败: {str(e)}"}
    
    # ========== 股票行情数据 ==========
    
    def get_stock_daily(self, symbol: str) -> dict:
        """
        获取个股日线数据
        
        symbol: 股票代码，如 '600519' (贵州茅台)
        """
        cache_key = self._cache_key("stock_daily", symbol)
        cached = self._load_cache(cache_key)
        if cached:
            return cached
        
        try:
            import akshare as ak
            
            # 判断交易所
            if symbol.startswith("6"):
                full_symbol = f"sh{symbol}"
            elif symbol.startswith(("0", "3")):
                full_symbol = f"sz{symbol}"
            else:
                full_symbol = symbol
            
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                     start_date=(datetime.now() - timedelta(days=400)).strftime("%Y%m%d"),
                                     end_date=datetime.now().strftime("%Y%m%d"),
                                     adjust="qfq")
            
            if df is None or df.empty:
                return {"error": f"无法获取股票 {symbol} 的行情数据"}
            
            # 计算均线
            df = df.sort_values("日期")
            closes = df["收盘"].astype(float)
            df["MA20"] = closes.rolling(20).mean()
            df["MA60"] = closes.rolling(60).mean()
            df["MA120"] = closes.rolling(120).mean()
            df["MA250"] = closes.rolling(250).mean()
            
            # 计算收益率
            df["ret_20d"] = closes.pct_change(20)
            df["ret_60d"] = closes.pct_change(60)
            df["ret_120d"] = closes.pct_change(120)
            
            # 计算波动率
            df["volatility_20d"] = closes.pct_change().rolling(20).std()
            
            latest = df.iloc[-1]
            
            result = {
                "symbol": symbol,
                "latest": {
                    "date": str(latest["日期"]),
                    "open": safe_float(latest["开盘"]),
                    "close": safe_float(latest["收盘"]),
                    "high": safe_float(latest["最高"]),
                    "low": safe_float(latest["最低"]),
                    "volume": safe_float(latest["成交量"]),
                    "amount": safe_float(latest["成交额"]),
                },
                "ma": {
                    "ma20": safe_float(latest["MA20"]),
                    "ma60": safe_float(latest["MA60"]),
                    "ma120": safe_float(latest["MA120"]),
                    "ma250": safe_float(latest["MA250"]),
                },
                "returns": {
                    "ret_20d": safe_float(latest["ret_20d"]),
                    "ret_60d": safe_float(latest["ret_60d"]),
                    "ret_120d": safe_float(latest["ret_120d"]),
                },
                "volatility_20d": safe_float(latest["volatility_20d"]),
            }
            
            self._save_cache(cache_key, result)
            return result
            
        except ImportError:
            return {"error": "请安装akshare: pip install akshare"}
        except Exception as e:
            return {"error": f"获取股票行情失败: {str(e)}"}
    
    # ========== 行业数据 ==========
    
    def get_sector_data(self) -> list:
        """获取行业板块数据"""
        cache_key = self._cache_key("sector_data")
        cached = self._load_cache(cache_key)
        if cached and "sectors" in cached:
            return cached["sectors"]
        
        try:
            import akshare as ak
            
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                return []
            
            sectors = []
            for _, row in df.head(20).iterrows():
                sectors.append({
                    "name": str(row.get("板块名称", "")),
                    "code": str(row.get("板块代码", "")),
                    "latest_price": safe_float(row.get("最新价", 0)),
                    "pct_change": safe_float(row.get("涨跌幅", 0)),
                })
            
            self._save_cache(cache_key, {"sectors": sectors})
            return sectors
            
        except ImportError:
            return []
        except Exception as e:
            return []
    
    # ========== 资金流数据 ==========
    
    def get_money_flow(self, symbol: str) -> dict:
        """
        获取个股资金流向数据
        """
        cache_key = self._cache_key("money_flow", symbol)
        cached = self._load_cache(cache_key)
        if cached:
            return cached
        
        try:
            import akshare as ak
            
            df = ak.stock_individual_fund_flow(stock=symbol, market="sh" if symbol.startswith("6") else "sz")
            
            if df is None or df.empty:
                return {"error": "无法获取资金流数据"}
            
            # 最近20日主力净流入
            recent = df.head(20)
            main_net_inflow = safe_float(recent["主力净流入-净额"].sum()) if "主力净流入-净额" in recent.columns else 0
            total_amount = safe_float(recent["成交额"].sum()) if "成交额" in recent.columns else 1
            
            result = {
                "symbol": symbol,
                "main_net_inflow_20d": main_net_inflow,
                "main_inflow_ratio": main_net_inflow / total_amount if total_amount > 0 else 0,
            }
            
            self._save_cache(cache_key, result)
            return result
            
        except ImportError:
            return {"error": "请安装akshare"}
        except Exception as e:
            return {"error": f"获取资金流失败: {str(e)}"}
    
    # ========== 龙虎榜数据 ==========
    
    def get_lhb_data(self, symbol: str, days: int = 20) -> dict:
        """
        获取龙虎榜数据
        """
        cache_key = self._cache_key("lhb", symbol)
        cached = self._load_cache(cache_key)
        if cached:
            return cached
        
        try:
            import akshare as ak
            
            df = ak.stock_lhb_detail_em(date=datetime.now().strftime("%Y%m%d"))
            
            if df is None or df.empty:
                return {"net_buy": 0, "institution_buy": 0, "retail_excluded": False}
            
            # 筛选该股票
            stock_data = df[df["代码"] == symbol] if "代码" in df.columns else pd.DataFrame()
            
            result = {
                "net_buy": safe_float(stock_data["净买入额"].sum()) if not stock_data.empty else 0,
                "institution_net_buy": 0,
                "retail_excluded": not stock_data.empty,
            }
            
            self._save_cache(cache_key, result)
            return result
            
        except ImportError:
            return {"net_buy": 0, "institution_buy": 0, "retail_excluded": False}
        except Exception:
            return {"net_buy": 0, "institution_buy": 0, "retail_excluded": False}
    
    # ========== 大宗交易 ==========
    
    def get_block_trade(self, symbol: str) -> dict:
        """获取大宗交易数据"""
        try:
            import akshare as ak
            
            df = ak.stock_dzjy_mrmx(symbol=symbol, 
                                     start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                                     end_date=datetime.now().strftime("%Y%m%d"))
            
            if df is None or df.empty:
                return {"premium_pct": 0, "institution_buy": False}
            
            # 计算平均溢价率
            if "成交价" in df.columns and "当日收盘价" in df.columns:
                premium = safe_float(((df["成交价"].astype(float) - df["当日收盘价"].astype(float)) / 
                                       df["当日收盘价"].astype(float)).mean() * 100)
            else:
                premium = 0
            
            return {
                "premium_pct": premium,
                "institution_buy": premium > -3,  # 溢价或小幅折价视为机构接盘
            }
            
        except Exception:
            return {"premium_pct": 0, "institution_buy": False}
    
    # ========== 财务数据 ==========
    
    def get_financial_data(self, symbol: str) -> dict:
        """
        获取财务数据（通过东方财富或Tushare）
        """
        cache_key = self._cache_key("financial", symbol)
        cached = self._load_cache(cache_key)
        if cached:
            return cached
        
        try:
            import akshare as ak
            
            # 获取财务指标
            df = ak.stock_financial_analysis_indicator(symbol=symbol)
            
            if df is None or df.empty:
                return self._mock_financial_data(symbol)
            
            latest = df.iloc[0] if len(df) > 0 else {}
            
            result = {
                "symbol": symbol,
                "roe": safe_float(latest.get("净资产收益率", 0)),
                "roa": safe_float(latest.get("总资产收益率", 0)),
                "gross_margin": safe_float(latest.get("销售毛利率", 0)),
                "net_margin": safe_float(latest.get("销售净利率", 0)),
                "debt_ratio": safe_float(latest.get("资产负债率", 0)),
                "current_ratio": safe_float(latest.get("流动比率", 0)),
            }
            
            self._save_cache(cache_key, result)
            return result
            
        except ImportError:
            return self._mock_financial_data(symbol)
        except Exception:
            return self._mock_financial_data(symbol)
    
    def _mock_financial_data(self, symbol: str) -> dict:
        """返回模拟财务数据（当数据源不可用时）"""
        return {
            "symbol": symbol,
            "roe": 0,
            "roa": 0,
            "gross_margin": 0,
            "net_margin": 0,
            "debt_ratio": 0,
            "current_ratio": 0,
            "_note": "数据源暂不可用，使用默认值"
        }
    
    # ========== PE/PB历史分位 ==========
    
    def get_valuation_percentile(self, symbol: str) -> dict:
        """
        计算PE/PB历史分位（基于近10年数据）
        """
        cache_key = self._cache_key("valuation", symbol)
        cached = self._load_cache(cache_key)
        if cached:
            return cached
        
        try:
            import akshare as ak
            
            # 使用AkShare获取个股历史估值数据
            # 这里使用 daily 数据近似计算
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                     start_date=(datetime.now() - timedelta(days=3650)).strftime("%Y%m%d"),
                                     end_date=datetime.now().strftime("%Y%m%d"),
                                     adjust="qfq")
            
            if df is None or df.empty:
                return {"pe_percentile": 50, "pb_percentile": 50, "current_pe": 0, "current_pb": 0}
            
            closes = df["收盘"].astype(float)
            
            # 估算PE/PB分位（基于收盘价变化近似，实际需要财务数据）
            current_price = closes.iloc[-1]
            price_percentile = (closes < current_price).sum() / len(closes) * 100
            
            result = {
                "pe_percentile": round(price_percentile, 1),
                "pb_percentile": round(price_percentile, 1),
                "current_pe": 0,  # 需要财务数据才能精确计算
                "current_pb": 0,
                "_note": "PE/PB分位基于价格近似估算，精确值需要Tushare Pro"
            }
            
            self._save_cache(cache_key, result)
            return result
            
        except Exception:
            return {"pe_percentile": 50, "pb_percentile": 50, "current_pe": 0, "current_pb": 0}
    
    # ========== 股东人数 ==========
    
    def get_shareholder_data(self, symbol: str) -> dict:
        """获取股东人数变化"""
        try:
            import akshare as ak
            
            df = ak.stock_zh_a_gdhs(symbol=symbol)
            
            if df is None or df.empty or len(df) < 2:
                return {"shareholder_change": 0, "avg_holding_increase": 0}
            
            latest = safe_float(df.iloc[0].get("股东人数", 0))
            previous = safe_float(df.iloc[1].get("股东人数", 0))
            
            change = (latest - previous) / previous if previous > 0 else 0
            
            return {
                "shareholder_change": -change,  # 负值为好（人数下降）
                "avg_holding_increase": -change * 0.8,  # 粗略估算人均持股提升
            }
            
        except Exception:
            return {"shareholder_change": 0, "avg_holding_increase": 0}
    
    # ========== 综合数据采集 ==========
    
    def collect_stock_data(self, symbol: str, name: str = "") -> dict:
        """
        采集单只股票的全部所需数据，用于IAS评分和买入时机评估
        
        返回统一格式的数据字典
        """
        # 并行获取各类数据（简化：顺序获取）
        daily_data = self.get_stock_daily(symbol)
        money_flow = self.get_money_flow(symbol)
        lhb_data = self.get_lhb_data(symbol)
        block_trade = self.get_block_trade(symbol)
        financial = self.get_financial_data(symbol)
        valuation = self.get_valuation_percentile(symbol)
        shareholder = self.get_shareholder_data(symbol)
        
        # 获取行情数据
        price = 0
        ma20 = ma60 = ma120 = ma250 = 0
        ret_20d = ret_60d = ret_120d = 0
        vol_20d = 0
        
        if "ma" in daily_data:
            ma = daily_data["ma"]
            ma20 = ma.get("ma20", 0)
            ma60 = ma.get("ma60", 0)
            ma120 = ma.get("ma120", 0)
            ma250 = ma.get("ma250", 0)
        
        if "latest" in daily_data:
            price = daily_data["latest"].get("close", 0)
        
        if "returns" in daily_data:
            ret = daily_data["returns"]
            ret_20d = ret.get("ret_20d", 0)
            ret_60d = ret.get("ret_60d", 0)
            ret_120d = ret.get("ret_120d", 0)
        
        vol_20d = daily_data.get("volatility_20d", 0)
        
        # 组装数据
        data = {
            # IAS评分 - 行业数据
            "industry": {
                "order_growth": 0,       # 需外部数据源
                "capacity_utilization": 0,
                "price_trend": 0,
                "policy_level": "moderate",
                "revenue_growth": 0,
                "profit_growth": 0,
                "roe_trend": 0,
                "etf_flow": 0,
                "sector_flow": 0,
                "rank_pct": 50,
                "pe_percentile": 50,
                "pb_percentile": 50,
            },
            # IAS评分 - 公司数据
            "company": {
                "pe_percentile": valuation.get("pe_percentile", 50),
                "pb_percentile": valuation.get("pb_percentile", 50),
                "ps_ratio": 0,
                "peg_ratio": 0,
                "ev_ebitda": 0,
                "roe_5y": financial.get("roe", 0),
                "roic": financial.get("roa", 0),
                "gross_margin": financial.get("gross_margin", 0),
                "net_margin": financial.get("net_margin", 0),
                "op_cashflow": 0,
                "market_share": 0,
                "cost_advantage": 0,
                "brand_power": 0,
                "channel": 0,
                "patents": 0,
                "barrier": 0,
                "overseas_revenue_pct": 0,
                "overseas_orders": 0,
                "global_clients": 0,
                "overseas_capacity": 0,
            },
            # IAS评分 - 资金数据
            "capital": {
                "day20_inflow": money_flow.get("main_inflow_ratio", 0),
                "ema_trend": 0,
                "shareholder_change": shareholder.get("shareholder_change", 0),
                "avg_holding_increase": shareholder.get("avg_holding_increase", 0),
                "lhb_net_buy": lhb_data.get("net_buy", 0),
                "lhb_retail_excluded": lhb_data.get("retail_excluded", False),
                "block_premium_pct": block_trade.get("premium_pct", 0),
                "block_institution_buy": block_trade.get("institution_buy", False),
                "fund_increase_ratio": 0,
                "fund_count_change": 0,
            },
            # IAS评分 - 趋势数据
            "momentum": {
                "ret_20d": ret_20d,
                "ret_60d": ret_60d,
                "ret_120d": ret_120d,
                "sector_rank_pct": 50,
                "ma20": ma20,
                "ma60": ma60,
                "ma120": ma120,
                "ma250": ma250,
                "price": price,
                "vol_up_ratio": 0,
                "vol_down_ratio": 0,
                "atr_pct": vol_20d * 100 if vol_20d else 3,
                "beta": 1.0,
                "annual_vol": vol_20d * (252 ** 0.5) * 100 if vol_20d else 30,
            },
            # 事件修正
            "event": {
                "major_order": 0,
                "policy_support": 0,
                "buyback": 0,
                "executive_buy": 0,
                "reduction": 0,
                "financial_risk": 0,
                "regulatory_investigation": 0,
            },
            # 买入时机数据
            "timing": {
                "current_pe": valuation.get("current_pe", 0),
                "pe_percentile": valuation.get("pe_percentile", 50),
                "industry_avg_pe": 0,
                "price": price,
                "ma60": ma60,
                "ma120": ma120,
                "ma250": ma250,
                "fcf": 0,
                "market_cap": 0,
            },
            # 元数据
            "meta": {
                "symbol": symbol,
                "name": name,
                "data_source": "akshare",
                "collected_at": datetime.now().isoformat(),
            }
        }
        
        # 检测是否有子模块返回mock数据，传播_note标记
        if financial.get("_note") or valuation.get("_note"):
            data["meta"]["_note"] = "部分数据使用默认值"
        
        return data


# 创建全局采集器实例
data_collector = DataCollector()
