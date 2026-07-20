"""
Halo - 中国股市投资分析系统
IAS (Intelligent Alpha Scoring) 评分引擎

评分体系：
- 第一层：行业Alpha (25%)
- 第二层：公司Alpha (30%)  
- 第三层：资金Alpha (25%)
- 第四层：趋势Alpha (20%)
- 事件驱动修正 (±10分)
"""

from dataclasses import dataclass, field
from typing import Optional
import math


@dataclass
class IndustryScore:
    """行业Alpha评分"""
    prosperity: float = 0.0       # 行业景气指数 (0-10)
    profit_trend: float = 0.0     # 行业盈利趋势 (0-5)
    capital_flow: float = 0.0     # 行业资金流 (0-5)
    valuation: float = 0.0        # 行业估值 (0-5)
    
    @property
    def total(self) -> float:
        return self.prosperity + self.profit_trend + self.capital_flow + self.valuation
    
    @property
    def normalized(self) -> float:
        """归一化到0-100"""
        return (self.total / 25.0) * 100.0


@dataclass
class CompanyScore:
    """公司Alpha评分"""
    valuation: float = 0.0        # 估值评分 (0-10)
    profitability: float = 0.0    # 盈利能力 (0-8)
    moat: float = 0.0             # 护城河评分 (0-7)
    globalization: float = 0.0    # 全球化能力 (0-5)
    
    @property
    def total(self) -> float:
        return self.valuation + self.profitability + self.moat + self.globalization
    
    @property
    def normalized(self) -> float:
        """归一化到0-100"""
        return (self.total / 30.0) * 100.0


@dataclass
class CapitalScore:
    """资金Alpha评分"""
    continuous_flow: float = 0.0   # 连续资金流 (0-8)
    concentration: float = 0.0     # 筹码集中度 (0-5)
    institution_lhb: float = 0.0   # 龙虎榜机构行为 (0-4)
    block_trade: float = 0.0       # 大宗交易 (0-4)
    fund_position: float = 0.0     # 基金持仓变化 (0-4)
    
    @property
    def total(self) -> float:
        return (self.continuous_flow + self.concentration + 
                self.institution_lhb + self.block_trade + self.fund_position)
    
    @property
    def normalized(self) -> float:
        """归一化到0-100"""
        return (self.total / 25.0) * 100.0


@dataclass
class MomentumScore:
    """趋势Alpha评分"""
    cross_section: float = 0.0     # 截面动量 (0-8)
    ma_structure: float = 0.0      # 均线结构 (0-4)
    volume_structure: float = 0.0  # 成交量结构 (0-4)
    volatility_control: float = 0.0  # 波动率控制 (0-4)
    
    @property
    def total(self) -> float:
        return (self.cross_section + self.ma_structure + 
                self.volume_structure + self.volatility_control)
    
    @property
    def normalized(self) -> float:
        """归一化到0-100"""
        return (self.total / 20.0) * 100.0


@dataclass
class EventAdjustment:
    """事件驱动修正"""
    major_order: float = 0.0       # 重大订单 +3
    policy_support: float = 0.0    # 政策支持 +2
    buyback: float = 0.0           # 回购 +2
    executive_buy: float = 0.0     # 高管增持 +2
    reduction: float = 0.0         # 减持 -4
    financial_risk: float = 0.0    # 财务风险 -5
    regulatory_investigation: float = 0.0  # 监管调查 -10
    
    @property
    def total(self) -> float:
        raw = (self.major_order + self.policy_support + self.buyback + 
                self.executive_buy + self.reduction + self.financial_risk + 
                self.regulatory_investigation)
        # 限制在±10范围内（符合文档约定）
        return max(-10.0, min(10.0, raw))


@dataclass
class IASResult:
    """IAS评分结果"""
    symbol: str
    name: str
    
    # 四层评分
    industry: IndustryScore = field(default_factory=IndustryScore)
    company: CompanyScore = field(default_factory=CompanyScore)
    capital: CapitalScore = field(default_factory=CapitalScore)
    momentum: MomentumScore = field(default_factory=MomentumScore)
    event: EventAdjustment = field(default_factory=EventAdjustment)
    
    @property
    def industry_pct(self) -> float:
        return self.industry.normalized
    
    @property
    def company_pct(self) -> float:
        return self.company.normalized
    
    @property
    def capital_pct(self) -> float:
        return self.capital.normalized
    
    @property
    def momentum_pct(self) -> float:
        return self.momentum.normalized
    
    @property
    def ias_score(self) -> float:
        """IAS综合评分 (0-100)"""
        score = (
            self.industry_pct * 0.25 +
            self.company_pct * 0.30 +
            self.capital_pct * 0.25 +
            self.momentum_pct * 0.20 +
            self.event.total
        )
        return max(0.0, min(100.0, score))
    
    @property
    def passed(self) -> bool:
        """双重过滤规则：Industry >= 60 且 Company >= 60"""
        return self.industry_pct >= 60.0 and self.company_pct >= 60.0
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "ias_score": round(self.ias_score, 2),
            "industry_score": round(self.industry_pct, 2),
            "company_score": round(self.company_pct, 2),
            "capital_score": round(self.capital_pct, 2),
            "momentum_score": round(self.momentum_pct, 2),
            "event_adjustment": round(self.event.total, 2),
            "passed": self.passed,
            "details": {
                "industry": {
                    "prosperity": self.industry.prosperity,
                    "profit_trend": self.industry.profit_trend,
                    "capital_flow": self.industry.capital_flow,
                    "valuation": self.industry.valuation,
                },
                "company": {
                    "valuation": self.company.valuation,
                    "profitability": self.company.profitability,
                    "moat": self.company.moat,
                    "globalization": self.company.globalization,
                },
                "capital": {
                    "continuous_flow": self.capital.continuous_flow,
                    "concentration": self.capital.concentration,
                    "institution_lhb": self.capital.institution_lhb,
                    "block_trade": self.capital.block_trade,
                    "fund_position": self.capital.fund_position,
                },
                "momentum": {
                    "cross_section": self.momentum.cross_section,
                    "ma_structure": self.momentum.ma_structure,
                    "volume_structure": self.momentum.volume_structure,
                    "volatility_control": self.momentum.volatility_control,
                },
                "event": {
                    "major_order": self.event.major_order,
                    "policy_support": self.event.policy_support,
                    "buyback": self.event.buyback,
                    "executive_buy": self.event.executive_buy,
                    "reduction": self.event.reduction,
                    "financial_risk": self.event.financial_risk,
                    "regulatory_investigation": self.event.regulatory_investigation,
                }
            }
        }


class IASEngine:
    """IAS评分引擎 - 计算股票的综合Alpha评分"""
    
    @staticmethod
    def score_industry_prosperity(
        order_growth: float,        # 订单增长率 (%)
        capacity_utilization: float, # 产能利用率 (%)
        price_trend: float,          # 商品价格趋势 (%)
        policy_level: str            # 政策支持级别: "strong"/"moderate"/"weak"/"none"
    ) -> float:
        """
        行业景气指数评分 (0-10分)
        
        指标：订单、产能利用率、商品价格、政策支持
        80-100: 10分, 60-80: 7分, 40-60: 4分, <40: 0分
        """
        # 政策支持映射
        policy_score = {"strong": 25, "moderate": 18, "weak": 10, "none": 0}
        policy_pts = policy_score.get(policy_level.lower(), 0)
        
        # 各指标等权加权
        raw_score = (
            order_growth * 0.25 +
            capacity_utilization * 0.25 +
            price_trend * 0.25 +
            policy_pts * 0.25
        )
        
        if raw_score >= 80:
            return 10.0
        elif raw_score >= 60:
            return 7.0
        elif raw_score >= 40:
            return 4.0
        else:
            return 0.0
    
    @staticmethod
    def score_industry_profit(revenue_growth: float, profit_growth: float, roe_trend: float) -> float:
        """
        行业盈利趋势评分 (0-5分)
        
        数据：营收增长、利润增长、ROE趋势
        """
        score = (revenue_growth * 0.3 + profit_growth * 0.4 + roe_trend * 0.3) / 20.0
        return max(0.0, min(5.0, score * 5.0))
    
    @staticmethod
    def score_industry_capital(etf_flow: float, sector_flow: float, rank_pct: float) -> float:
        """
        行业资金流评分 (0-5分)
        
        数据：行业ETF资金流、板块资金流、行业涨跌排名
        rank_pct: 排名百分位 (0-100, 越高越好)
        """
        score = (etf_flow * 0.35 + sector_flow * 0.35 + rank_pct * 0.30) / 20.0
        return max(0.0, min(5.0, score * 5.0))
    
    @staticmethod
    def score_industry_valuation(pe_percentile: float, pb_percentile: float) -> float:
        """
        行业估值评分 (0-5分)
        
        数据：行业PE历史分位、行业PB历史分位
        分位越低越好（被低估）
        """
        # 反转：低分位=高分
        pe_score = max(0, 100 - pe_percentile) / 20.0
        pb_score = max(0, 100 - pb_percentile) / 20.0
        score = (pe_score + pb_score) / 2.0
        return max(0.0, min(5.0, score))
    
    @staticmethod
    def score_company_valuation(
        pe_percentile: float, pb_percentile: float,
        ps_ratio: float, peg_ratio: float, ev_ebitda: float
    ) -> float:
        """
        公司估值评分 (0-10分)
        
        指标：PE分位、PB分位、PS、PEG、EV/EBITDA
        输出 Value Score (0-100)
        """
        # PE分位越低越好
        pe_score = max(0, 100 - pe_percentile)
        # PB分位越低越好
        pb_score = max(0, 100 - pb_percentile)
        # PS: 低PS好 (<2好, >8差)
        ps_score = max(0, 100 - ps_ratio * 12.5) if ps_ratio > 0 else 100
        # PEG: <1好
        peg_score = max(0, 100 - peg_ratio * 50) if peg_ratio > 0 else 100
        # EV/EBITDA: <10好
        ev_score = max(0, 100 - ev_ebitda * 5) if ev_ebitda > 0 else 100
        
        value_score = (pe_score * 0.3 + pb_score * 0.2 + ps_score * 0.15 + 
                       peg_score * 0.2 + ev_score * 0.15)
        
        return max(0.0, min(10.0, value_score / 10.0))
    
    @staticmethod
    def score_company_profitability(
        roe_5y: float, roic: float, gross_margin: float,
        net_margin: float, op_cashflow: float
    ) -> float:
        """
        公司盈利能力评分 (0-8分)
        
        指标：ROE(5年趋势)、ROIC、毛利率、净利率、经营现金流
        """
        # ROE >= 15% 好
        roe_score = min(100, roe_5y / 15.0 * 100) if roe_5y > 0 else 0
        # ROIC >= 10% 好
        roic_score = min(100, roic / 10.0 * 100) if roic > 0 else 0
        # 毛利率 >= 30% 好
        margin_score = min(100, gross_margin / 30.0 * 100)
        # 净利率 >= 15% 好
        net_score = min(100, net_margin / 15.0 * 100)
        # 经营现金流/营收 >= 10% 好
        cf_score = min(100, op_cashflow / 10.0 * 100)
        
        score = (roe_score * 0.25 + roic_score * 0.2 + margin_score * 0.2 + 
                 net_score * 0.2 + cf_score * 0.15) / 12.5
        
        return max(0.0, min(8.0, score))
    
    @staticmethod
    def score_moat(
        market_share: float, cost_advantage: float,
        brand_power: float, channel: float, patents: float, barrier: float
    ) -> float:
        """
        护城河评分 (0-7分)
        
        维度：市占率、成本优势、品牌力、渠道、专利、行业壁垒
        输出 Moat Score (0-100)
        """
        moat_score = (
            market_share * 0.2 +
            cost_advantage * 0.15 +
            brand_power * 0.15 +
            channel * 0.15 +
            patents * 0.15 +
            barrier * 0.2
        )
        return max(0.0, min(7.0, moat_score / 100.0 * 7.0))
    
    @staticmethod
    def score_globalization(
        overseas_revenue_pct: float, overseas_orders: float,
        global_clients: float, overseas_capacity: float
    ) -> float:
        """
        全球化能力评分 (0-5分)
        
        指标：海外收入占比、海外订单、全球客户结构、海外产能
        """
        score = (overseas_revenue_pct * 0.35 + overseas_orders * 0.25 + 
                 global_clients * 0.2 + overseas_capacity * 0.2) / 20.0
        return max(0.0, min(5.0, score))
    
    @staticmethod
    def score_capital_flow(day20_inflow: float, ema_trend: float) -> float:
        """
        连续资金流评分 (0-8分)
        
        指标：20日主力净流入、EMA资金趋势
        """
        inflow_score = min(100, max(0, day20_inflow * 100 + 50))
        ema_score = min(100, max(0, ema_trend * 100 + 50))
        score = (inflow_score * 0.5 + ema_score * 0.5) / 12.5
        return max(0.0, min(8.0, score))
    
    @staticmethod
    def score_concentration(
        shareholder_change: float,  # 股东人数变化率 (负值为好)
        avg_holding_increase: float  # 人均持股提升率
    ) -> float:
        """
        筹码集中度评分 (0-5分)
        
        指标：股东人数变化、人均持股提升
        """
        # 股东人数下降=筹码集中=好
        holder_score = min(100, max(0, -shareholder_change * 500 + 50))
        holding_score = min(100, max(0, avg_holding_increase * 500 + 50))
        score = (holder_score * 0.5 + holding_score * 0.5) / 20.0
        return max(0.0, min(5.0, score))
    
    @staticmethod
    def score_institution_lhb(net_buy_amount: float, retail_excluded: bool) -> float:
        """
        龙虎榜机构行为评分 (0-4分)
        
        指标：机构专用席位净买入、游资剔除
        """
        if not retail_excluded:
            return 0.0
        # 净买入量标准化
        score = min(100, max(0, net_buy_amount * 1000 + 50)) / 25.0
        return max(0.0, min(4.0, score))
    
    @staticmethod
    def score_block_trade(premium_pct: float, institution_buy: bool) -> float:
        """
        大宗交易评分 (0-4分)
        
        指标：溢价/折价成交、机构接盘行为
        """
        if not institution_buy:
            return 0.0
        # 溢价为正，折价为负
        premium_score = min(100, max(0, premium_pct * 200 + 50))
        score = (premium_score * 0.6 + (50 if institution_buy else 0) * 0.4) / 25.0
        return max(0.0, min(4.0, score))
    
    @staticmethod
    def score_fund_position(increase_ratio: float, fund_count_change: float) -> float:
        """
        基金持仓变化评分 (0-4分)
        
        指标：公募基金增仓比例、持仓基金数量变化
        """
        ratio_score = min(100, max(0, increase_ratio * 1000 + 50))
        count_score = min(100, max(0, fund_count_change * 100 + 50))
        score = (ratio_score * 0.5 + count_score * 0.5) / 25.0
        return max(0.0, min(4.0, score))
    
    @staticmethod
    def score_cross_section_momentum(
        ret_20d: float, ret_60d: float, ret_120d: float, sector_rank_pct: float
    ) -> float:
        """
        截面动量评分 (0-8分)
        
        指标：20/60/120日收益率排名、行业内排名
        """
        ret_score = (ret_20d * 0.4 + ret_60d * 0.3 + ret_120d * 0.3) * 100
        rank_score = sector_rank_pct
        score = (ret_score * 0.5 + rank_score * 0.5) / 12.5
        return max(0.0, min(8.0, score))
    
    @staticmethod
    def score_ma_structure(ma20: float, ma60: float, ma120: float, ma250: float, price: float) -> float:
        """
        均线结构评分 (0-4分)
        
        多头结构：MA20 > MA60 > MA120 > MA250
        """
        if price <= 0 or ma250 <= 0:
            return 0.0
        
        score = 0.0
        # 价格在MA250之上
        if price > ma250:
            score += 1.0
        # MA20 > MA60
        if ma20 > ma60:
            score += 1.0
        # MA60 > MA120
        if ma60 > ma120:
            score += 1.0
        # MA120 > MA250（完美多头）
        if ma120 > ma250:
            score += 1.0
        
        return score
    
    @staticmethod
    def score_volume_structure(vol_up_ratio: float, vol_down_ratio: float) -> float:
        """
        成交量结构评分 (0-4分)
        
        指标：放量上涨、缩量回调
        """
        # 放量上涨比例
        up_score = min(100, max(0, vol_up_ratio * 200)) / 25.0
        # 缩量回调（反转，缩量好）
        down_score = min(100, max(0, (1 - vol_down_ratio) * 200)) / 25.0
        score = up_score * 0.6 + down_score * 0.4
        return max(0.0, min(4.0, score))
    
    @staticmethod
    def score_volatility(atr_pct: float, beta: float, annual_vol: float) -> float:
        """
        波动率控制评分 (0-4分)
        
        指标：ATR、Beta、年化波动率
        低波动更好（风险控制）
        """
        # ATR越低越好（atr_pct为百分比，如3表示3%）
        atr_score = max(0, 100 - atr_pct * 10) / 25.0
        # Beta接近1最好
        beta_score = max(0, 100 - abs(beta - 1.0) * 50) / 25.0
        # 年化波动率越低越好（annual_vol为百分比，如30表示30%）
        vol_score = max(0, 100 - annual_vol * 2) / 25.0
        
        score = atr_score * 0.3 + beta_score * 0.3 + vol_score * 0.4
        return max(0.0, min(4.0, score))
    
    def compute_ias(self, symbol: str, name: str, data: dict) -> IASResult:
        """
        计算完整IAS评分
        
        data字典包含所有需要的输入参数
        """
        result = IASResult(symbol=symbol, name=name)
        
        # === 第一层：行业Alpha (25%) ===
        ind_data = data.get("industry", {})
        result.industry.prosperity = self.score_industry_prosperity(
            order_growth=ind_data.get("order_growth", 0),
            capacity_utilization=ind_data.get("capacity_utilization", 0),
            price_trend=ind_data.get("price_trend", 0),
            policy_level=ind_data.get("policy_level", "none")
        )
        result.industry.profit_trend = self.score_industry_profit(
            revenue_growth=ind_data.get("revenue_growth", 0),
            profit_growth=ind_data.get("profit_growth", 0),
            roe_trend=ind_data.get("roe_trend", 0)
        )
        result.industry.capital_flow = self.score_industry_capital(
            etf_flow=ind_data.get("etf_flow", 0),
            sector_flow=ind_data.get("sector_flow", 0),
            rank_pct=ind_data.get("rank_pct", 0)
        )
        result.industry.valuation = self.score_industry_valuation(
            pe_percentile=ind_data.get("pe_percentile", 50),
            pb_percentile=ind_data.get("pb_percentile", 50)
        )
        
        # === 第二层：公司Alpha (30%) ===
        comp_data = data.get("company", {})
        result.company.valuation = self.score_company_valuation(
            pe_percentile=comp_data.get("pe_percentile", 50),
            pb_percentile=comp_data.get("pb_percentile", 50),
            ps_ratio=comp_data.get("ps_ratio", 5),
            peg_ratio=comp_data.get("peg_ratio", 1.5),
            ev_ebitda=comp_data.get("ev_ebitda", 10)
        )
        result.company.profitability = self.score_company_profitability(
            roe_5y=comp_data.get("roe_5y", 10),
            roic=comp_data.get("roic", 8),
            gross_margin=comp_data.get("gross_margin", 25),
            net_margin=comp_data.get("net_margin", 10),
            op_cashflow=comp_data.get("op_cashflow", 8)
        )
        result.company.moat = self.score_moat(
            market_share=comp_data.get("market_share", 50),
            cost_advantage=comp_data.get("cost_advantage", 50),
            brand_power=comp_data.get("brand_power", 50),
            channel=comp_data.get("channel", 50),
            patents=comp_data.get("patents", 50),
            barrier=comp_data.get("barrier", 50)
        )
        result.company.globalization = self.score_globalization(
            overseas_revenue_pct=comp_data.get("overseas_revenue_pct", 0),
            overseas_orders=comp_data.get("overseas_orders", 0),
            global_clients=comp_data.get("global_clients", 0),
            overseas_capacity=comp_data.get("overseas_capacity", 0)
        )
        
        # === 第三层：资金Alpha (25%) ===
        cap_data = data.get("capital", {})
        result.capital.continuous_flow = self.score_capital_flow(
            day20_inflow=cap_data.get("day20_inflow", 0),
            ema_trend=cap_data.get("ema_trend", 0)
        )
        result.capital.concentration = self.score_concentration(
            shareholder_change=cap_data.get("shareholder_change", 0),
            avg_holding_increase=cap_data.get("avg_holding_increase", 0)
        )
        result.capital.institution_lhb = self.score_institution_lhb(
            net_buy_amount=cap_data.get("lhb_net_buy", 0),
            retail_excluded=cap_data.get("lhb_retail_excluded", False)
        )
        result.capital.block_trade = self.score_block_trade(
            premium_pct=cap_data.get("block_premium_pct", 0),
            institution_buy=cap_data.get("block_institution_buy", False)
        )
        result.capital.fund_position = self.score_fund_position(
            increase_ratio=cap_data.get("fund_increase_ratio", 0),
            fund_count_change=cap_data.get("fund_count_change", 0)
        )
        
        # === 第四层：趋势Alpha (20%) ===
        mom_data = data.get("momentum", {})
        result.momentum.cross_section = self.score_cross_section_momentum(
            ret_20d=mom_data.get("ret_20d", 0),
            ret_60d=mom_data.get("ret_60d", 0),
            ret_120d=mom_data.get("ret_120d", 0),
            sector_rank_pct=mom_data.get("sector_rank_pct", 0)
        )
        result.momentum.ma_structure = self.score_ma_structure(
            ma20=mom_data.get("ma20", 0),
            ma60=mom_data.get("ma60", 0),
            ma120=mom_data.get("ma120", 0),
            ma250=mom_data.get("ma250", 0),
            price=mom_data.get("price", 0)
        )
        result.momentum.volume_structure = self.score_volume_structure(
            vol_up_ratio=mom_data.get("vol_up_ratio", 0),
            vol_down_ratio=mom_data.get("vol_down_ratio", 0)
        )
        result.momentum.volatility_control = self.score_volatility(
            atr_pct=mom_data.get("atr_pct", 3),
            beta=mom_data.get("beta", 1.0),
            annual_vol=mom_data.get("annual_vol", 30)
        )
        
        # === 事件驱动修正 ===
        evt_data = data.get("event", {})
        result.event.major_order = evt_data.get("major_order", 0)
        result.event.policy_support = evt_data.get("policy_support", 0)
        result.event.buyback = evt_data.get("buyback", 0)
        result.event.executive_buy = evt_data.get("executive_buy", 0)
        result.event.reduction = evt_data.get("reduction", 0)
        result.event.financial_risk = evt_data.get("financial_risk", 0)
        result.event.regulatory_investigation = evt_data.get("regulatory_investigation", 0)
        
        return result


# 创建全局引擎实例
ias_engine = IASEngine()
