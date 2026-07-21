"""
Halo - 买入时机评估模块
三维估值锚定连续赋分模型（总分100分）

核心原则：即使是优秀企业，也必须以合理甚至低估价格买入。

评分组成：
1. 历史分位连续得分 (40分) — 纵向对比：相对自己的历史贵不贵
2. 行业PE偏离度连续得分 (30分) — 横向对比：相对同行贵不贵
3. 行业景气度连续得分 (30分) — 成长性调整：市场为什么给这个估值
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TimingResult:
    """买入时机评估结果"""
    symbol: str
    name: str
    
    # 五维评分 (总分120)
    score_historical: float = 0.0   # 历史PE分位得分 (0-40)
    score_industry_pe: float = 0.0  # 行业PE偏离得分 (0-30)
    score_prosperity: float = 0.0   # 行业景气度得分 (0-30)
    score_pb: float = 0.0           # PB分位得分 (0-10)
    score_dividend: float = 0.0     # 股息率得分 (0-10)
    
    # 原始数据
    current_pe: float = 0.0
    pe_percentile: float = 0.5
    industry_avg_pe: float = 0.0
    pe_deviation: float = 0.0
    industry_growth: float = 0.0
    pb_percentile: float = 0.5      # PB历史分位 (0-1)
    dividend_yield: float = 0.0     # 股息率 (如0.05=5%)
    
    @property
    def total_score(self) -> float:
        """买入时机总分 (0-120)"""
        return (self.score_historical + self.score_industry_pe + 
                self.score_prosperity + self.score_pb + self.score_dividend)
    
    @property
    def normalized_score(self) -> float:
        """归一化到0-100"""
        return self.total_score / 120.0 * 100.0
    
    @property
    def rating(self) -> str:
        """买入时机评级（阈值下调10分）"""
        s = self.normalized_score
        if s >= 70:
            return "★★★★★ 极度低估"
        elif s >= 55:
            return "★★★★ 显著低估"
        elif s >= 42:
            return "★★★ 合理偏低"
        elif s >= 28:
            return "★★ 合理偏高"
        elif s >= 15:
            return "★ 偏贵"
        else:
            return "☆ 太贵"
    
    @property
    def is_buy_zone(self) -> bool:
        """是否处于买入区域 (总分>=72, 即归一化>=60)"""
        return self.normalized_score >= 60
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "total_score": round(self.total_score, 2),
            "normalized_score": round(self.normalized_score, 2),
            "rating": self.rating,
            "is_buy_zone": self.is_buy_zone,
            "details": {
                "score_historical": round(self.score_historical, 2),
                "score_industry_pe": round(self.score_industry_pe, 2),
                "score_prosperity": round(self.score_prosperity, 2),
                "score_pb": round(self.score_pb, 2),
                "score_dividend": round(self.score_dividend, 2),
                "current_pe": round(self.current_pe, 2),
                "pe_percentile": round(self.pe_percentile, 2),
                "industry_avg_pe": round(self.industry_avg_pe, 2),
                "pe_deviation": round(self.pe_deviation, 4),
                "industry_growth": round(self.industry_growth, 4),
                "pb_percentile": round(self.pb_percentile, 2),
                "dividend_yield": round(self.dividend_yield, 4),
            }
        }


class TimingEvaluator:
    """三维估值锚定连续赋分模型"""
    
    @staticmethod
    def score_historical(pe_percentile: float) -> float:
        """
        维度一：历史分位连续得分 (权重40%)
        
        公式：score = (1 - pe_percentile) × 40
        
        pe_percentile=0   → 40分（历史最低位）
        pe_percentile=0.5 → 20分（历史中位）
        pe_percentile=1.0 → 0分（历史最高位）
        """
        if pe_percentile < 0:
            return 40.0
        return max(0.0, min(40.0, (1.0 - pe_percentile) * 40.0))
    
    @staticmethod
    def score_industry_pe(current_pe: float, industry_avg_pe: float) -> float:
        """
        维度二：行业PE偏离度连续得分 (权重30%)
        
        偏离度 = (个股PE / 行业平均PE) - 1
        
        偏离度 ≤ -0.30（大幅折价30%+）→ 30分（满分）
        偏离度 ≥ +0.50（溢价50%+）    → 0分
        中间线性区：score = [1 - (偏离度 + 0.30) / 0.80] × 30
        """
        if current_pe <= 0 or industry_avg_pe <= 0:
            return 15.0  # 数据缺失给中位分
        
        deviation = (current_pe / industry_avg_pe) - 1.0
        
        if deviation <= -0.30:
            return 30.0
        if deviation >= 0.50:
            return 0.0
        
        # 线性区间 [-0.30, +0.50]
        return max(0.0, min(30.0, (1.0 - (deviation + 0.30) / 0.80) * 30.0))
    
    @staticmethod
    def score_prosperity(industry_growth: float) -> float:
        """
        维度三：行业景气度连续得分 (权重30%)
        
        以GDP增速(~5%)为基准锚。
        
        industry_growth ≤ -0.10（强衰退）    → 5分（保底）
        industry_growth ≥ +0.30（高速增长）  → 30分（封顶）
        中间线性区：score = (growth + 0.10) / 0.40 × 30
        """
        if industry_growth <= -0.10:
            return 5.0
        if industry_growth >= 0.30:
            return 30.0
        
        return max(5.0, min(30.0, (industry_growth + 0.10) / 0.40 * 30.0))
    
    @staticmethod
    def score_pb(pb_percentile: float) -> float:
        """
        维度四：PB分位得分 (权重10分)
        
        PB越低越好：pb_percentile=0 → 10分, pb_percentile=1 → 0分
        """
        return max(0.0, min(10.0, (1.0 - pb_percentile) * 10.0))
    
    @staticmethod
    def score_dividend(dividend_yield: float) -> float:
        """
        维度五：股息率得分 (权重10分)
        
        股息率越高越好：0% → 0分, 5% → 10分, ≥8% → 10分封顶
        """
        return max(0.0, min(10.0, dividend_yield * 200.0))
    
    def evaluate(self, symbol: str, name: str, data: dict) -> TimingResult:
        """
        完整买入时机评估（五维模型）
        
        data参数：
        - pe_percentile: PE历史分位 (0-1)
        - current_pe: 当前PE(TTM)
        - industry_avg_pe: 行业平均PE
        - industry_growth: 行业预期净利润增速 (如0.15=15%)
        - pb_percentile: PB历史分位 (0-1)
        - dividend_yield: 股息率 (如0.05=5%)
        """
        pe_percentile = data.get("pe_percentile", 0.5)
        current_pe = data.get("current_pe", 0)
        industry_avg_pe = data.get("industry_avg_pe", 0)
        industry_growth = data.get("industry_growth", 0.05)
        pb_percentile = data.get("pb_percentile", 0.5)
        dividend_yield = data.get("dividend_yield", 0)
        
        result = TimingResult(symbol=symbol, name=name)
        result.current_pe = current_pe
        result.pe_percentile = pe_percentile
        result.industry_avg_pe = industry_avg_pe
        result.industry_growth = industry_growth
        result.pb_percentile = pb_percentile
        result.dividend_yield = dividend_yield
        
        if industry_avg_pe > 0:
            result.pe_deviation = (current_pe / industry_avg_pe) - 1.0
        
        result.score_historical = self.score_historical(pe_percentile)
        result.score_industry_pe = self.score_industry_pe(current_pe, industry_avg_pe)
        result.score_prosperity = self.score_prosperity(industry_growth)
        result.score_pb = self.score_pb(pb_percentile)
        result.score_dividend = self.score_dividend(dividend_yield)
        
        return result


# 创建全局评估器实例
timing_evaluator = TimingEvaluator()
