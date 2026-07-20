"""
Halo - 模拟交易引擎
系统胜率追踪：模拟持仓、买入卖出、收益计算

规则：
1. 系统每推荐一只新股票，模拟持仓按当前交易日开盘价买100手
2. 持仓累计收益达到10%时自动模拟卖出
3. 重复推荐不重复买入，卖出后可再次买入
4. 买卖记录保留3个月
"""
import json
import os
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

# 数据文件路径
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TRADES_FILE = os.path.join(DATA_DIR, "sim_trades.json")
POSITIONS_FILE = os.path.join(DATA_DIR, "sim_positions.json")
os.makedirs(DATA_DIR, exist_ok=True)

# 模拟参数
LOTS = 100           # 每笔买入100手
TAKE_PROFIT_PCT = 0.10  # 10%止盈
RECORD_RETENTION_DAYS = 90  # 3个月记录保留


@dataclass
class Trade:
    """单笔交易记录"""
    trade_id: str
    symbol: str
    name: str
    trade_type: str  # "buy" | "sell"
    price: float
    lots: int
    amount: float
    trade_date: str
    reason: str = ""
    
    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "name": self.name,
            "trade_type": self.trade_type,
            "price": round(self.price, 2),
            "lots": self.lots,
            "amount": round(self.amount, 2),
            "trade_date": self.trade_date,
            "reason": self.reason,
        }


@dataclass
class Position:
    """持仓"""
    symbol: str
    name: str
    buy_price: float
    buy_date: str
    lots: int
    cost: float  # 总成本
    
    @property
    def current_return_pct(self, current_price: float) -> float:
        if self.cost <= 0:
            return 0.0
        return (current_price - self.buy_price) / self.buy_price
    
    @property
    def current_pnl(self, current_price: float) -> float:
        return (current_price - self.buy_price) * self.lots * 100  # 每手100股
    
    def to_dict(self, current_price: float = 0) -> dict:
        ret_pct = self.current_return_pct(current_price) if current_price > 0 else 0
        pnl = self.current_pnl(current_price) if current_price > 0 else 0
        return {
            "symbol": self.symbol,
            "name": self.name,
            "buy_price": round(self.buy_price, 2),
            "buy_date": self.buy_date,
            "lots": self.lots,
            "cost": round(self.cost, 2),
            "current_price": round(current_price, 2),
            "return_pct": round(ret_pct * 100, 2),
            "pnl": round(pnl, 2),
            "reach_take_profit": ret_pct >= TAKE_PROFIT_PCT,
        }


class SimEngine:
    """模拟交易引擎"""
    
    def __init__(self):
        self._trades: list[Trade] = []
        self._positions: dict[str, Position] = {}  # key: symbol
        self._sold_symbols: dict[str, str] = {}  # symbol -> sold_date
        self._load()
    
    def _load(self):
        """加载持久化数据"""
        # 加载交易记录
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._trades = [
                    Trade(**{k: v for k, v in t.items() if k in Trade.__dataclass_fields__})
                    for t in data.get("trades", [])
                ]
            except Exception:
                self._trades = []
        
        # 加载持仓
        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for p in data.get("positions", []):
                    pos = Position(
                        symbol=p["symbol"],
                        name=p["name"],
                        buy_price=p["buy_price"],
                        buy_date=p["buy_date"],
                        lots=p["lots"],
                        cost=p["cost"],
                    )
                    self._positions[p["symbol"]] = pos
                self._sold_symbols = dict(data.get("sold_symbols", []))
            except Exception:
                self._positions = {}
                self._sold_symbols = {}
        
        # 清理过期记录
        self._cleanup()
    
    def _save(self):
        """持久化数据"""
        # 保存交易记录
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "trades": [t.to_dict() for t in self._trades],
                "updated_at": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
        
        # 保存持仓
        with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "positions": [p.to_dict() for p in self._positions.values()],
                "sold_symbols": [[s, d] for s, d in self._sold_symbols.items()],
                "updated_at": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
    
    def _cleanup(self):
        """清理超过3个月的交易记录和已卖出记录"""
        cutoff = datetime.now() - timedelta(days=RECORD_RETENTION_DAYS)
        self._trades = [
            t for t in self._trades
            if datetime.fromisoformat(t.trade_date) >= cutoff
        ]
        # 清理过期已卖出记录
        self._sold_symbols = {
            s: d for s, d in self._sold_symbols.items()
            if datetime.fromisoformat(d) >= cutoff
        }
    
    def _generate_trade_id(self) -> str:
        return f"T{datetime.now().strftime('%Y%m%d%H%M%S')}{len(self._trades):04d}"
    
    def has_position(self, symbol: str) -> bool:
        """检查是否持有某股票"""
        return symbol in self._positions
    
    def can_buy(self, symbol: str) -> bool:
        """检查是否可以买入（未持仓且未在已卖出列表中）"""
        return not self.has_position(symbol) and symbol not in self._sold_symbols
    
    def buy(self, symbol: str, name: str, price: float, date: str = "", reason: str = "") -> Optional[Trade]:
        """
        模拟买入
        返回交易记录，不可买入时返回None
        """
        if self.has_position(symbol):
            return None  # 已持仓，不重复买入
        
        if symbol in self._sold_symbols:
            return None  # 已卖出但尚未再次推荐
        
        if price <= 0:
            return None
        
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        amount = price * LOTS * 100  # 每手100股
        
        # 创建持仓
        position = Position(
            symbol=symbol,
            name=name,
            buy_price=price,
            buy_date=trade_date,
            lots=LOTS,
            cost=amount,
        )
        self._positions[symbol] = position
        
        # 记录交易
        trade = Trade(
            trade_id=self._generate_trade_id(),
            symbol=symbol,
            name=name,
            trade_type="buy",
            price=price,
            lots=LOTS,
            amount=amount,
            trade_date=trade_date,
            reason=reason,
        )
        self._trades.append(trade)
        self._save()
        return trade
    
    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """检查是否达到止盈条件"""
        if symbol not in self._positions:
            return False
        pos = self._positions[symbol]
        return pos.current_return_pct(current_price) >= TAKE_PROFIT_PCT
    
    def sell(self, symbol: str, price: float, date: str = "", reason: str = "") -> Optional[Trade]:
        """
        模拟卖出（止盈触发）
        """
        if symbol not in self._positions:
            return None
        
        if price <= 0:
            return None
        
        pos = self._positions[symbol]
        trade_date = date or datetime.now().strftime("%Y-%m-%d")
        amount = price * LOTS * 100
        pnl = (price - pos.buy_price) * LOTS * 100
        
        trade = Trade(
            trade_id=self._generate_trade_id(),
            symbol=symbol,
            name=pos.name,
            trade_type="sell",
            price=price,
            lots=LOTS,
            amount=amount,
            trade_date=trade_date,
            reason=f"{reason} | 盈亏: {pnl:.2f}",
        )
        self._trades.append(trade)
        
        # 移除持仓，加入已卖出列表
        del self._positions[symbol]
        self._sold_symbols[symbol] = trade_date
        self._save()
        return trade
    
    def re_enable_buy(self, symbol: str):
        """卖出后系统再次推荐时，允许重新买入"""
        self._sold_symbols.pop(symbol, None)
        self._save()
    
    def get_position(self, symbol: str) -> Optional[Position]:
        return self._positions.get(symbol)
    
    def get_all_positions(self) -> list[Position]:
        return list(self._positions.values())
    
    def get_trades(self, limit: int = 50) -> list[Trade]:
        """获取最近的交易记录"""
        return sorted(self._trades, key=lambda t: t.trade_date, reverse=True)[:limit]
    
    def get_trades_by_symbol(self, symbol: str) -> list[Trade]:
        """获取某股票的交易记录"""
        return [t for t in self._trades if t.symbol == symbol]
    
    def get_summary(self) -> dict:
        """获取汇总统计"""
        total_buys = sum(1 for t in self._trades if t.trade_type == "buy")
        total_sells = sum(1 for t in self._trades if t.trade_type == "sell")
        
        # 计算累计盈亏
        total_pnl = 0.0
        win_count = 0
        loss_count = 0
        for t in self._trades:
            if t.trade_type == "sell" and "盈亏:" in t.reason:
                try:
                    pnl_str = t.reason.split("盈亏:")[1].strip()
                    pnl = float(pnl_str)
                    total_pnl += pnl
                    if pnl > 0:
                        win_count += 1
                    else:
                        loss_count += 1
                except (ValueError, IndexError):
                    pass
        
        total_trades = win_count + loss_count
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "total_buys": total_buys,
            "total_sells": total_sells,
            "holdings": len(self._positions),
            "total_pnl": round(total_pnl, 2),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_rate, 1),
            "updated_at": datetime.now().isoformat(),
        }
    
    def process_recommendations(self, recommendations: list, price_map: dict = None):
        """
        根据推荐列表处理模拟交易
        
        recommendations: [{"symbol": "600519", "name": "贵州茅台", ...}, ...]
        price_map: {"600519": 1800.00, ...}  # 开盘价映射
        """
        if price_map is None:
            price_map = {}
        
        recommended_symbols = set()
        today = datetime.now().strftime("%Y-%m-%d")
        
        for rec in recommendations:
            symbol = rec.get("symbol", "")
            name = rec.get("name", "")
            recommended_symbols.add(symbol)
            
            # 如果已卖出且在推荐列表中，允许重新买入
            if symbol in self._sold_symbols and not self.has_position(symbol):
                self.re_enable_buy(symbol)
            
            # 尝试买入
            price = price_map.get(symbol, 0)
            if price > 0 and self.can_buy(symbol):
                self.buy(symbol, name, price, today, f"系统推荐买入: IAS={rec.get('ias_score', 0):.1f}")
        
        # 检查止盈（需要当前价格）
        for symbol, pos in list(self._positions.items()):
            current_price = price_map.get(symbol, 0)
            if current_price > 0 and self.check_take_profit(symbol, current_price):
                self.sell(symbol, current_price, today, "止盈10%自动卖出")
        
        return self.get_summary()


# 全局实例
sim_engine = SimEngine()
