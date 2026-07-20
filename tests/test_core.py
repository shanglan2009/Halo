"""
Halo 系统验证脚本
测试所有核心模块的导入和基本功能
"""
import sys
import os

# 确保项目根目录在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

def test_ias_engine():
    """测试IAS评分引擎"""
    print("=== 测试 IAS 评分引擎 ===")
    from scripts.ias_engine import IASEngine, ias_engine
    
    engine = IASEngine()
    test_data = {
        'industry': {
            'order_growth': 70, 'capacity_utilization': 75,
            'price_trend': 60, 'policy_level': 'moderate',
            'revenue_growth': 15, 'profit_growth': 20, 'roe_trend': 12,
            'etf_flow': 50, 'sector_flow': 60, 'rank_pct': 55,
            'pe_percentile': 30, 'pb_percentile': 35,
        },
        'company': {
            'pe_percentile': 25, 'pb_percentile': 30,
            'ps_ratio': 3, 'peg_ratio': 0.8, 'ev_ebitda': 8,
            'roe_5y': 25, 'roic': 18, 'gross_margin': 65,
            'net_margin': 35, 'op_cashflow': 15,
            'market_share': 60, 'cost_advantage': 55,
            'brand_power': 80, 'channel': 70, 'patents': 50, 'barrier': 65,
            'overseas_revenue_pct': 20, 'overseas_orders': 15,
            'global_clients': 30, 'overseas_capacity': 10,
        },
        'capital': {
            'day20_inflow': 0.3, 'ema_trend': 0.2,
            'shareholder_change': -0.05, 'avg_holding_increase': 0.03,
            'lhb_net_buy': 0.5, 'lhb_retail_excluded': True,
            'block_premium_pct': 2, 'block_institution_buy': True,
            'fund_increase_ratio': 0.04, 'fund_count_change': 0.1,
        },
        'momentum': {
            'ret_20d': 0.05, 'ret_60d': 0.08, 'ret_120d': 0.12,
            'sector_rank_pct': 60,
            'ma20': 150, 'ma60': 140, 'ma120': 130, 'ma250': 120,
            'price': 155,
            'vol_up_ratio': 0.4, 'vol_down_ratio': 0.3,
            'atr_pct': 2, 'beta': 0.95, 'annual_vol': 25,
        },
        'event': {
            'major_order': 3, 'policy_support': 2,
            'buyback': 0, 'executive_buy': 0,
            'reduction': 0, 'financial_risk': 0, 'regulatory_investigation': 0,
        }
    }
    
    result = engine.compute_ias('600519', '贵州茅台', test_data)
    assert result.ias_score > 0, "IAS评分应大于0"
    assert result.industry_pct >= 0, "行业评分应>=0"
    assert result.company_pct >= 0, "公司评分应>=0"
    print(f"  ✅ IAS总分: {result.ias_score:.2f}")
    print(f"  ✅ 行业: {result.industry_pct:.2f}, 公司: {result.company_pct:.2f}")
    print(f"  ✅ 资金: {result.capital_pct:.2f}, 趋势: {result.momentum_pct:.2f}")
    print(f"  ✅ 通过双重过滤: {result.passed}")


def test_timing_eval():
    """测试买入时机评估"""
    print("\n=== 测试买入时机评估 ===")
    from scripts.timing_eval import TimingEvaluator
    
    evaluator = TimingEvaluator()
    
    # 测试低估情况
    timing_data = {
        'current_pe': 15, 'pe_percentile': 15,
        'industry_avg_pe': 20,
        'price': 110, 'ma60': 120, 'ma120': 115, 'ma250': 125,
        'fcf': 1000, 'market_cap': 8000,
    }
    result = evaluator.evaluate('600519', '贵州茅台', timing_data)
    assert result.total_score > 0, "时机总分应大于0"
    print(f"  ✅ 时机总分: {result.total_score:.1f}/50")
    print(f"  ✅ 评级: {result.rating}")
    print(f"  ✅ 买入区域: {result.is_buy_zone}")
    
    # 测试高估情况
    timing_data2 = {
        'current_pe': 80, 'pe_percentile': 95,
        'industry_avg_pe': 20,
        'price': 200, 'ma60': 120, 'ma120': 115, 'ma250': 100,
        'fcf': 100, 'market_cap': 100000,
    }
    result2 = evaluator.evaluate('test', '高估股', timing_data2)
    print(f"  ✅ 高估值测试 - 总分: {result2.total_score:.1f}/50 (应该较低)")
    assert result2.total_score < result.total_score, "高估值评分应低于低估值"


def test_recommendation():
    """测试综合推荐引擎"""
    print("\n=== 测试综合推荐引擎 ===")
    from scripts.recommendation import RecommendationEngine, QUALITY_STOCK_POOL
    
    engine = RecommendationEngine()
    assert len(QUALITY_STOCK_POOL) > 20, "优质股票池应有足够标的"
    print(f"  ✅ 优质股票池: {len(QUALITY_STOCK_POOL)} 只")
    
    # 测试特征检查
    features = engine.check_features('600519', '贵州茅台', '白酒/消费', 2.5, 4.5)
    print(f"  ✅ 贵州茅台 特征匹配: {features.passed_count}/7")
    assert features.passed_count >= 3, "茅台至少应匹配3个特征"
    
    features2 = engine.check_features('600900', '长江电力', '水电/清洁能源', 3.8, 55.0)
    print(f"  ✅ 长江电力 特征匹配: {features2.passed_count}/7")
    assert features2.passed_count >= 4, "长江电力至少应匹配4个特征"


def test_api_structure():
    """测试API模块结构"""
    print("\n=== 测试API模块 ===")
    from api.index import app
    assert app is not None, "FastAPI app 应存在"
    print(f"  ✅ FastAPI app 创建成功")
    print(f"  ✅ 应用标题: {app.title}")
    
    # 检查路由
    routes = [r.path for r in app.routes]
    assert "/api/health" in routes, "应有health端点"
    assert "/api/stocks/recommend" in routes, "应有推荐端点"
    print(f"  ✅ 路由数量: {len(routes)}")


def main():
    # 设置UTF-8编码避免Windows GBK问题
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 60)
    print("Halo 系统验证测试")
    print("=" * 60)
    
    tests = [
        ("IAS评分引擎", test_ias_engine),
        ("买入时机评估", test_timing_eval),
        ("综合推荐引擎", test_recommendation),
        ("API模块", test_api_structure),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
            print(f"\n✅ {name} - 通过")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} - 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    
    if failed > 0:
        print("❌ 部分测试失败，请检查代码")
        sys.exit(1)
    else:
        print("✅ 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
