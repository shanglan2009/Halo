"""
Halo - 买入时机评估模块
估值分析（满分50分）- 不便宜不买

核心原则：即使是优秀企业，也必须以合理甚至低估价格买入。

评分组成：
1. 历史估值分位 (20分)
2. 行业估值比较 (10分)
3. 均线位置 (10分)
4. 自由现金流收益率 (10分)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimingResult:
    """买入时机评估结果"""
    symbol: str
    name: str
    
    # 四项评分
    historical_pe_score: float = 0.0     # 历史估值分位 (0-20)
    industry_pe_score: float = 0.0       # 行业估值比较 (0-10)
    ma_position_score: float = 0.0       # 均线位置 (0-10)
    fcf_yield_score: float = 0.0         # 自由现金流收益率 (0-10)
    
    # 原始数据
    current_pe: float = 0.0
    pe_percentile: float = 50.0
    industry_avg_pe: float = 0.0
    pe_to_industry: float = 1.0
    price: float = 0.0
    ma60: float = 0.0
    ma120: float = 0.0
    ma250: float = 0.0
    fcf_yield: float = 0.0
    
    @property
    def total_score(self) -> float:
        """买入时机总分 (0-50)"""
        return (self.historical_pe_score + self.industry_pe_score + 
                self.ma_position_score + self.fcf_yield_score)
    
    @property
    def normalized_score(self) -> float:
        """归一化到0-100"""
        return (self.total_score / 50.0) * 100.0
    
    @property
    def rating(self) -> str:
        """买入时机评级"""
        s = self.total_score
        if s >= 45:
            return "★★★★★ 极佳买点"
        elif s >= 38:
            return "★★★★ 良好买点"
        elif s >= 30:
            return "★★★ 合理买点"
        elif s >= 20:
            return "★★ 偏贵"
        else:
            return "★ 太贵"
    
    @property
    def is_buy_zone(self) -> bool:
        """是否处于买入区域 (>=30分)"""
        return self.total_score >= 30
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "total_score": round(self.total_score, 2),
            "normalized_score": round(self.normalized_score, 2),
            "rating": self.rating,
            "is_buy_zone": self.is_buy_zone,
            "details": {
                "historical_pe_score": round(self.historical_pe_score, 2),
                "industry_pe_score": round(self.industry_pe_score, 2),
                "ma_position_score": round(self.ma_position_score, 2),
                "fcf_yield_score": round(self.fcf_yield_score, 2),
                "current_pe": round(self.current_pe, 2),
                "pe_percentile": round(self.pe_percentile, 2),
                "industry_avg_pe": round(self.industry_avg_pe, 2),
                "pe_to_industry": round(self.pe_to_industry, 2),
                "fcf_yield_pct": round(self.fcf_yield * 100, 2),
                "price": round(self.price, 2),
                "ma250": round(self.ma250, 2),
                "ma250_position": round(self.price / self.ma250 - 1, 4) if self.ma250 > 0 else 0
            }
        }


class TimingEvaluator:
    """买入时机评估器"""
    
    @staticmethod
    def evaluate_historical_pe(current_pe: float, pe_percentile: float) -> float:
        """
        历史估值分位评分 (0-20分)
        
        比较当前PE(TTM)与过去10年历史PE区间。
        
        评分规则：
        - 0%-20%分位: 20分
        - 20%-40%分位: 15分
        - 40%-60%分位: 8分
        - 60%以上: 0分
        """
        if current_pe <= 0:
            return 0.0
        
        if pe_percentile <= 20:
            return 20.0
        elif pe_percentile <= 40:
            return 15.0
        elif pe_percentile <= 60:
            return 8.0
        else:
            return 0.0
    
    @staticmethod
    def evaluate_industry_pe(current_pe: float, industry_avg_pe: float) -> float:
        """
        行业估值比较评分 (0-10分)
        
        计算：当前PE ÷ 行业平均PE
        
        评分规则：
        - ≤0.8: 10分
        - 0.8-1.0: 8分
        - 1.0-1.2: 5分
        - >1.2: 0分
        """
        if current_pe <= 0 or industry_avg_pe <= 0:
            return 0.0
        
        ratio = current_pe / industry_avg_pe
        
        if ratio <= 0.8:
            return 10.0
        elif ratio <= 1.0:
            return 8.0
        elif ratio <= 1.2:
            return 5.0
        else:
            return 0.0
    
    @staticmethod
    def evaluate_ma_position(price: float, ma60: float, ma120: float, ma250: float) -> float:
        """
        均线位置评分 (0-10分)
        
        重点关注MA250（年线）。
        
        评分规则：
        - 低于MA250超过10%: 10分
        - MA250±10%: 8分
        - 高于MA250 10%-30%: 5分
        - 高于MA250超过30%: 0分
        """
        if price <= 0 or ma250 <= 0:
            return 0.0
        
        deviation = (price - ma250) / ma250  # 偏离MA250的比例
        
        if deviation < -0.10:
            return 10.0
        elif deviation <= 0.10:
            return 8.0
        elif deviation <= 0.30:
            return 5.0
        else:
            return 0.0
    
    @staticmethod
    def evaluate_fcf_yield(fcf: float, market_cap: float) -> float:
        """
        自由现金流收益率评分 (0-10分)
        
        计算：自由现金流 ÷ 总市值
        
        评分规则：
        - ≥10%: 10分
        - 8%-10%: 8分
        - 5%-8%: 5分
        - <5%: 0分
        """
        if fcf <= 0 or market_cap <= 0:
            return 0.0
        
        fcf_yield = fcf / market_cap
        
        if fcf_yield >= 0.10:
            return 10.0
        elif fcf_yield >= 0.08:
            return 8.0
        elif fcf_yield >= 0.05:
            return 5.0
        else:
            return 0.0
    
    def evaluate(self, symbol: str, name: str, data: dict) -> TimingResult:
        """
        完整买入时机评估
        
        data参数:
        - current_pe: 当前PE(TTM)
        - pe_percentile: PE历史分位 (0-100)
        - industry_avg_pe: 行业平均PE
        - price: 当前价格
        - ma60: 60日均线
        - ma120: 120日均线
        - ma250: 250日均线
        - fcf: 自由现金流
        - market_cap: 总市值
        """
        current_pe = data.get("current_pe", 0)
        pe_percentile = data.get("pe_percentile", 50)
        industry_avg_pe = data.get("industry_avg_pe", 0)
        price = data.get("price", 0)
        ma60 = data.get("ma60", 0)
        ma120 = data.get("ma120", 0)
        ma250 = data.get("ma250", 0)
        fcf = data.get("fcf", 0)
        market_cap = data.get("market_cap", 0)
        
        result = TimingResult(symbol=symbol, name=name)
        result.current_pe = current_pe
        result.pe_percentile = pe_percentile
        result.industry_avg_pe = industry_avg_pe
        result.price = price
        result.ma60 = ma60
        result.ma120 = ma120
        result.ma250 = ma250
        
        result.historical_pe_score = self.evaluate_historical_pe(current_pe, pe_percentile)
        result.industry_pe_score = self.evaluate_industry_pe(current_pe, industry_avg_pe)
        result.ma_position_score = self.evaluate_ma_position(price, ma60, ma120, ma250)
        result.fcf_yield_score = self.evaluate_fcf_yield(fcf, market_cap)
        
        if market_cap > 0:
            result.fcf_yield = fcf / market_cap
            result.pe_to_industry = current_pe / industry_avg_pe if industry_avg_pe > 0 else 0
        
        return result


# 创建全局评估器实例
timing_evaluator = TimingEvaluator()
