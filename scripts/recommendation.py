"""
Halo - 综合推荐引擎
结合股票选择(IAS评分 50%) + 买入时机(50%) 计算最终推荐排名

最终推荐公式：
Final Score = IAS_Score × 50% + Timing_Score × 50%

机构一致性评分(ICS)：
ICS ≥ 80 → 进入核心股票池

7个选股特征检查：
1. 资产随时间增值（越久越值钱）
2. 产品无论朝代更替都被需要
3. 内生性增长（不需再投入）
4. 高分红率
5. 中国国有资本投资加仓
6. 未来社会发展趋势中受益
7. 符合中国政府政策方向
"""

from dataclasses import dataclass, field
from typing import Optional
import json
import os

from scripts.ias_engine import ias_engine, IASResult
from scripts.timing_eval import timing_evaluator, TimingResult


@dataclass
class FeatureCheck:
    """7大选股特征检查"""
    asset_appreciation: bool = False      # 1. 资产随时间增值
    timeless_demand: bool = False         # 2. 产品恒久需求
    endogenous_growth: bool = False       # 3. 内生性增长
    high_dividend: bool = False           # 4. 高分红率
    state_capital: bool = False           # 5. 国有资本投资加仓
    future_trend: bool = False            # 6. 未来社会趋势受益
    policy_aligned: bool = False          # 7. 符合政策方向
    
    @property
    def passed_count(self) -> int:
        return sum([
            self.asset_appreciation,
            self.timeless_demand,
            self.endogenous_growth,
            self.high_dividend,
            self.state_capital,
            self.future_trend,
            self.policy_aligned,
        ])
    
    @property
    def all_passed(self) -> bool:
        return self.passed_count >= 5  # 至少满足5个特征
    
    def to_dict(self) -> dict:
        return {
            "asset_appreciation": self.asset_appreciation,
            "timeless_demand": self.timeless_demand,
            "endogenous_growth": self.endogenous_growth,
            "high_dividend": self.high_dividend,
            "state_capital": self.state_capital,
            "future_trend": self.future_trend,
            "policy_aligned": self.policy_aligned,
            "passed_count": self.passed_count,
            "all_passed": self.all_passed,
        }


@dataclass
class ICSResult:
    """机构一致性评分(ICS)"""
    fund_increase: float = 0.0        # 公募基金增仓
    insurance_flow: float = 0.0       # 保险/社保资金流
    lhb_institution: float = 0.0      # 龙虎榜机构席位
    block_trade_buy: float = 0.0      # 大宗交易接盘
    continuous_inflow: float = 0.0    # 连续资金流入
    shareholder_decline: float = 0.0  # 股东人数下降
    
    @property
    def ics_score(self) -> float:
        """ICS评分 (0-100)"""
        return (self.fund_increase * 0.2 + self.insurance_flow * 0.2 +
                self.lhb_institution * 0.2 + self.block_trade_buy * 0.15 +
                self.continuous_inflow * 0.15 + self.shareholder_decline * 0.1)
    
    @property
    def is_core(self) -> bool:
        """是否进入核心股票池 (ICS >= 80)"""
        return self.ics_score >= 80
    
    def to_dict(self) -> dict:
        return {
            "ics_score": round(self.ics_score, 2),
            "is_core": self.is_core,
            "fund_increase": self.fund_increase,
            "insurance_flow": self.insurance_flow,
            "lhb_institution": self.lhb_institution,
            "block_trade_buy": self.block_trade_buy,
            "continuous_inflow": self.continuous_inflow,
            "shareholder_decline": self.shareholder_decline,
        }


@dataclass
class StockRecommendation:
    """单只股票的完整推荐结果"""
    symbol: str
    name: str
    
    # IAS评分
    ias_result: Optional[IASResult] = None
    ias_score: float = 0.0
    
    # 买入时机
    timing_result: Optional[TimingResult] = None
    timing_score: float = 0.0
    
    # 7大特征
    features: FeatureCheck = field(default_factory=FeatureCheck)
    
    # 机构一致性
    ics: ICSResult = field(default_factory=ICSResult)
    
    # 最终评分
    final_score: float = 0.0
    
    # 推荐等级
    recommendation: str = ""
    
    @property
    def final_score_weighted(self) -> float:
        """最终加权评分: IAS 50% + Timing 50%"""
        return self.ias_score * 0.5 + self.timing_score * 0.5
    
    @property
    def is_recommended(self) -> bool:
        """是否推荐买入"""
        return (self.ias_result and self.ias_result.passed and 
                self.timing_result and self.timing_result.is_buy_zone and
                self.features.all_passed and
                self.final_score >= 60)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "final_score": round(self.final_score, 2),
            "ias_score": round(self.ias_score, 2),
            "timing_score": round(self.timing_score, 2),
            "recommendation": self.recommendation,
            "is_recommended": self.is_recommended,
            "ias_details": self.ias_result.to_dict() if self.ias_result else {},
            "timing_details": self.timing_result.to_dict() if self.timing_result else {},
            "features": self.features.to_dict(),
            "ics": self.ics.to_dict(),
        }


class RecommendationEngine:
    """综合推荐引擎"""
    
    def __init__(self):
        self.ias_engine = ias_engine
        self.timing_evaluator = timing_evaluator
    
    def check_features(self, symbol: str, name: str, sector: str = "", 
                       dividend_yield: float = 0, state_ownership: float = 0) -> FeatureCheck:
        """
        检查7大选股特征
        
        基于股票代码、行业分类、分红率、国有持股等信息判断
        """
        features = FeatureCheck()
        
        # 定义符合特征的行业/板块
        # 这些行业的产品/资产通常不会随时间贬值
        appreciating_sectors = [
            "白酒", "中药", "食品饮料", "消费",
            "品牌消费", "老字号", "奢侈品",
            "黄金", "珠宝", "艺术品",
            "水电", "核电", "清洁能源",
            "港口", "机场", "高速公路", "铁路",
            "通信", "数据中心",
        ]
        
        # 恒久需求行业（无论社会如何发展都需要）
        timeless_sectors = [
            "白酒", "中药", "食品饮料", "调味品", "粮油",
            "电力", "水务", "燃气", "供热",
            "银行", "保险",
            "通信", "运营商",
            "医药", "医疗",
            "教育",
            "殡葬",
        ]
        
        # 内生增长型行业（高ROE、低资本开支）
        endogenous_sectors = [
            "白酒", "中药", "调味品", "食品饮料",
            "互联网平台", "软件服务",
            "品牌消费", "奢侈品",
            "水电", "核电",
            "检测服务",
        ]
        
        # 高分红行业
        high_dividend_sectors = [
            "银行", "煤炭", "石油石化", "电力",
            "高速公路", "铁路", "港口",
            "白酒", "家电",
            "通信运营商",
        ]
        
        # 国有资本重点布局方向
        state_capital_sectors = [
            "半导体", "芯片", "集成电路",
            "新能源", "光伏", "风电", "储能",
            "军工", "航空航天",
            "人工智能", "大数据", "云计算",
            "生物医药", "创新药",
            "高端制造", "工业母机",
            "稀土", "稀有金属",
            "粮食", "种业",
        ]
        
        # 未来社会趋势受益行业
        future_trend_sectors = [
            "人工智能", "AI", "机器人", "自动化",
            "新能源", "光伏", "风电", "储能", "氢能",
            "半导体", "芯片",
            "生物医药", "创新药", "CXO",
            "数字经济", "东数西算", "云计算",
            "老龄化", "养老", "医疗",
            "碳中和", "碳达峰",
            "消费升级", "国货崛起",
        ]
        
        # 政策支持方向
        policy_sectors = [
            "人工智能", "AI", "半导体", "芯片",
            "新能源", "光伏", "风电", "储能",
            "高端制造", "智能制造",
            "生物医药", "创新药",
            "数字经济", "信创",
            "碳中和", "绿色能源",
            "种业", "粮食安全",
            "军工", "国防安全",
            "稀土", "关键矿产",
            "一带一路",
        ]
        
        def _match_any(sector_str: str, target_list: list) -> bool:
            for t in target_list:
                if t in sector_str:
                    return True
            return False
        
        # 综合判断
        features.asset_appreciation = _match_any(sector, appreciating_sectors)
        features.timeless_demand = _match_any(sector, timeless_sectors)
        features.endogenous_growth = _match_any(sector, endogenous_sectors)
        features.high_dividend = dividend_yield >= 3.0 or _match_any(sector, high_dividend_sectors)
        features.state_capital = state_ownership >= 5.0 or _match_any(sector, state_capital_sectors)
        features.future_trend = _match_any(sector, future_trend_sectors)
        features.policy_aligned = _match_any(sector, policy_sectors)
        
        return features
    
    def compute_ics(self, capital_data: dict) -> ICSResult:
        """计算机构一致性评分"""
        ics = ICSResult()
        
        # 公募基金增仓 (0-100, 基准50)
        fund_increase = capital_data.get("fund_increase_ratio") or 0
        ics.fund_increase = min(100, max(0, fund_increase * 1000 + 50))
        
        # 保险/社保资金流 (使用公募基金增仓+持仓基金数量变化作为代理信号)
        fund_count = capital_data.get("fund_count_change") or 0
        ics.insurance_flow = min(100, max(0, fund_increase * 800 + fund_count * 200 + 40))
        
        # 龙虎榜机构席位 (渐进评分：有机构参与≥50, 净买入越多越高)
        lhb_net_buy = capital_data.get("lhb_net_buy") or 0
        lhb_retail = capital_data.get("lhb_retail_excluded", False)
        if lhb_retail:
            ics.lhb_institution = min(100, max(0, 55 + lhb_net_buy * 300))
        else:
            ics.lhb_institution = 30  # 未上龙虎榜或游资主导
        
        # 大宗交易接盘 (溢价成交+机构接盘为正向信号)
        premium = capital_data.get("block_premium_pct") or 0
        inst_buy = capital_data.get("block_institution_buy", False)
        if inst_buy:
            ics.block_trade_buy = min(100, max(0, 50 + premium * 200))
        else:
            ics.block_trade_buy = 10  # 无机构接盘，低分
        
        # 连续资金流入 (主力资金净流入趋势)
        day20_inflow = capital_data.get("day20_inflow") or 0
        ics.continuous_inflow = min(100, max(0, day20_inflow * 500 + 50))
        
        # 股东人数下降 (股东人数减少=筹码集中=利好，符号取反)
        shareholder_change = capital_data.get("shareholder_change") or 0
        ics.shareholder_decline = min(100, max(0, -shareholder_change * 1000 + 50))
        
        return ics
    
    def recommend(self, stock_data: dict) -> StockRecommendation:
        """
        对单只股票进行完整分析和推荐
        
        stock_data: 来自DataCollector.collect_stock_data()的完整数据
        """
        symbol = stock_data["meta"]["symbol"]
        name = stock_data["meta"].get("name", symbol)
        
        rec = StockRecommendation(symbol=symbol, name=name)
        
        # 1. IAS评分
        rec.ias_result = self.ias_engine.compute_ias(symbol, name, stock_data)
        rec.ias_score = rec.ias_result.ias_score
        
        # 2. 买入时机评估
        timing_data = stock_data.get("timing", {})
        rec.timing_result = self.timing_evaluator.evaluate(symbol, name, timing_data)
        rec.timing_score = rec.timing_result.normalized_score
        
        # 3. 7大特征检查
        sector = stock_data.get("meta", {}).get("sector", "")
        dividend_yield = stock_data.get("meta", {}).get("dividend_yield", 0)
        state_ownership = stock_data.get("meta", {}).get("state_ownership", 0)
        rec.features = self.check_features(symbol, name, sector, dividend_yield, state_ownership)
        
        # 4. 机构一致性评分
        capital_data = stock_data.get("capital", {})
        rec.ics = self.compute_ics(capital_data)
        
        # 5. 最终评分
        rec.final_score = rec.final_score_weighted
        
        # 6. 推荐等级
        if rec.final_score >= 85:
            rec.recommendation = "⭐⭐⭐⭐⭐ 强烈推荐"
        elif rec.final_score >= 75:
            rec.recommendation = "⭐⭐⭐⭐ 推荐"
        elif rec.final_score >= 65:
            rec.recommendation = "⭐⭐⭐ 关注"
        elif rec.final_score >= 55:
            rec.recommendation = "⭐⭐ 观望"
        else:
            rec.recommendation = "⭐ 不推荐"
        
        # 修正：如果IAS或时机不及格，降级
        if not rec.ias_result.passed:
            rec.recommendation = "❌ 行业/公司评分不及格"
        elif not rec.timing_result.is_buy_zone:
            rec.recommendation = "⏳ 买入时机未到（偏贵）"
        elif not rec.features.all_passed:
            rec.recommendation = "⚠️ 未满足核心选股特征"
        
        return rec
    
    def batch_recommend(self, stocks_data: list) -> list:
        """
        批量分析多只股票并排名
        
        返回按final_score降序排列的推荐列表
        """
        recommendations = []
        errors = []
        
        for data in stocks_data:
            try:
                rec = self.recommend(data)
                recommendations.append(rec)
            except Exception as e:
                errors.append({
                    "symbol": data.get("meta", {}).get("symbol", "unknown"),
                    "error": str(e)
                })
        
        # 按最终评分降序排列
        recommendations.sort(key=lambda r: r.final_score, reverse=True)
        
        return [r.to_dict() for r in recommendations]


# 预定义的符合7大特征的优质股票池
# 这些是中国股市中符合"越久越值钱、恒久需求、内生增长、高分红"特征的标的

QUALITY_STOCK_POOL = [
    {
        "symbol": "600519", "name": "贵州茅台", "sector": "白酒/消费",
        "dividend_yield": 2.5, "state_ownership": 4.5,
        "reason": "品牌护城河极深，越陈越香，产品恒久需求，高ROE内生增长"
    },
    {
        "symbol": "000858", "name": "五粮液", "sector": "白酒/消费",
        "dividend_yield": 2.2, "state_ownership": 3.0,
        "reason": "浓香龙头，品牌价值随时间增值，消费升级受益"
    },
    {
        "symbol": "600809", "name": "山西汾酒", "sector": "白酒/消费",
        "dividend_yield": 1.8, "state_ownership": 2.5,
        "reason": "清香型龙头，品牌复兴，全国化扩张"
    },
    {
        "symbol": "600436", "name": "片仔癀", "sector": "中药/消费",
        "dividend_yield": 2.0, "state_ownership": 5.0,
        "reason": "国家保密配方，越久越值钱，老龄化受益，政策支持中药"
    },
    {
        "symbol": "000538", "name": "云南白药", "sector": "中药/消费",
        "dividend_yield": 3.5, "state_ownership": 10.0,
        "reason": "国家保密配方，百年品牌，消费+医药双重属性"
    },
    {
        "symbol": "600085", "name": "同仁堂", "sector": "中药/消费",
        "dividend_yield": 2.5, "state_ownership": 8.0,
        "reason": "350年老字号，品牌随时间增值，中医药政策受益"
    },
    {
        "symbol": "600900", "name": "长江电力", "sector": "水电/清洁能源",
        "dividend_yield": 3.8, "state_ownership": 55.0,
        "reason": "水电资产永续经营，现金流稳定，高分红，碳中和受益"
    },
    {
        "symbol": "600886", "name": "国投电力", "sector": "水电/清洁能源",
        "dividend_yield": 3.2, "state_ownership": 45.0,
        "reason": "清洁能源龙头，资产不折旧，国有资本控股，政策支持"
    },
    {
        "symbol": "601088", "name": "中国神华", "sector": "煤炭/能源",
        "dividend_yield": 6.5, "state_ownership": 60.0,
        "reason": "煤炭+电力+铁路一体化，超高分红，国有控股"
    },
    {
        "symbol": "601857", "name": "中国石油", "sector": "石油/能源",
        "dividend_yield": 4.5, "state_ownership": 80.0,
        "reason": "国家能源安全核心资产，国有绝对控股，高分红"
    },
    {
        "symbol": "600028", "name": "中国石化", "sector": "石油/能源",
        "dividend_yield": 5.5, "state_ownership": 70.0,
        "reason": "炼化+加油站网络，国有控股，稳定高分红"
    },
    {
        "symbol": "601939", "name": "建设银行", "sector": "银行/金融",
        "dividend_yield": 5.8, "state_ownership": 60.0,
        "reason": "国有大行，分红率高，国家金融安全基石"
    },
    {
        "symbol": "601398", "name": "工商银行", "sector": "银行/金融",
        "dividend_yield": 5.5, "state_ownership": 65.0,
        "reason": "全球最大银行，国有控股，稳定高分红"
    },
    {
        "symbol": "601288", "name": "农业银行", "sector": "银行/金融",
        "dividend_yield": 5.6, "state_ownership": 70.0,
        "reason": "国有大行，三农金融服务，政策支持，高分红"
    },
    {
        "symbol": "600036", "name": "招商银行", "sector": "银行/金融",
        "dividend_yield": 4.5, "state_ownership": 25.0,
        "reason": "零售银行之王，品牌价值高，ROE行业领先"
    },
    {
        "symbol": "601318", "name": "中国平安", "sector": "保险/金融",
        "dividend_yield": 4.2, "state_ownership": 5.0,
        "reason": "综合金融巨头，保险+银行+科技，老龄化受益"
    },
    {
        "symbol": "600690", "name": "海尔智家", "sector": "家电/消费",
        "dividend_yield": 3.0, "state_ownership": 10.0,
        "reason": "全球化家电龙头，品牌价值高，海外收入占比超50%"
    },
    {
        "symbol": "000333", "name": "美的集团", "sector": "家电/消费",
        "dividend_yield": 3.5, "state_ownership": 8.0,
        "reason": "家电综合龙头，全球布局，智能制造升级"
    },
    {
        "symbol": "000651", "name": "格力电器", "sector": "家电/消费",
        "dividend_yield": 4.5, "state_ownership": 15.0,
        "reason": "空调霸主，品牌护城河，高分红，国有资本参股"
    },
    {
        "symbol": "603288", "name": "海天味业", "sector": "调味品/消费",
        "dividend_yield": 1.8, "state_ownership": 2.0,
        "reason": "调味品绝对龙头，产品恒久需求，渠道壁垒深厚"
    },
    {
        "symbol": "600887", "name": "伊利股份", "sector": "食品饮料/消费",
        "dividend_yield": 3.2, "state_ownership": 5.0,
        "reason": "乳业龙头，消费升级受益，产品恒久需求"
    },
    {
        "symbol": "002415", "name": "海康威视", "sector": "AI/安防/科技",
        "dividend_yield": 2.8, "state_ownership": 8.0,
        "reason": "AI视觉龙头，技术壁垒，全球第一，数字经济受益"
    },
    {
        "symbol": "300750", "name": "宁德时代", "sector": "新能源/电池",
        "dividend_yield": 0.8, "state_ownership": 3.0,
        "reason": "动力电池全球龙头，新能源趋势，技术壁垒深厚"
    },
    {
        "symbol": "002594", "name": "比亚迪", "sector": "新能源/汽车",
        "dividend_yield": 0.5, "state_ownership": 2.0,
        "reason": "新能源车全球龙头，垂直整合，技术+品牌双壁垒"
    },
    {
        "symbol": "600276", "name": "恒瑞医药", "sector": "医药/创新药",
        "dividend_yield": 1.2, "state_ownership": 3.0,
        "reason": "创新药龙头，研发壁垒，老龄化+健康中国受益"
    },
    {
        "symbol": "300760", "name": "迈瑞医疗", "sector": "医疗器械/医药",
        "dividend_yield": 1.5, "state_ownership": 2.0,
        "reason": "医疗器械龙头，全球化布局，国产替代+医疗新基建"
    },
    {
        "symbol": "600941", "name": "中国移动", "sector": "通信/运营商",
        "dividend_yield": 4.5, "state_ownership": 70.0,
        "reason": "通信基础设施，国有控股，数字经济底座，高分红"
    },
    {
        "symbol": "601728", "name": "中国电信", "sector": "通信/运营商",
        "dividend_yield": 2.5, "state_ownership": 65.0,
        "reason": "云计算+IDC增长，国有控股，数字化转型受益"
    },
    {
        "symbol": "688981", "name": "中芯国际", "sector": "半导体/芯片",
        "dividend_yield": 0.3, "state_ownership": 10.0,
        "reason": "芯片制造龙头，国产替代核心，国家大基金重点投资"
    },
    {
        "symbol": "002371", "name": "北方华创", "sector": "半导体/设备",
        "dividend_yield": 0.4, "state_ownership": 8.0,
        "reason": "半导体设备龙头，国产替代，政策重点支持"
    },
]


# 创建全局推荐引擎实例
recommendation_engine = RecommendationEngine()
