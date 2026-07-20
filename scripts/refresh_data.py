"""
Halo - 定时数据刷新脚本
由 GitHub Actions 在每个交易日 9:25 / 13:05 / 14:50 (北京时间) 执行

功能：
1. 获取上证/深成指数实时数据
2. 获取优质股票池全部股票的行情数据
3. 计算 IAS 评分 + 买入时机评估 + 综合推荐
4. 结果保存为 JSON 文件（提交回仓库供 Vercel 前端读取）
"""
import sys
import os
import json
from datetime import datetime

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.data_collector import data_collector
from scripts.ias_engine import ias_engine
from scripts.timing_eval import timing_evaluator
from scripts.recommendation import recommendation_engine, QUALITY_STOCK_POOL

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)


def refresh_index_data():
    """刷新指数数据"""
    print("[INDEX] 获取指数数据...")
    results = {}
    
    for code, name in [("sh000001", "上证指数"), ("sz399001", "深证成指")]:
        try:
            data = data_collector.get_index_data(code)
            if "error" in data:
                print(f"  [WARN] {name}: {data['error']}")
                results[code] = {"error": data["error"]}
            else:
                results[code] = {
                    "name": name,
                    "latest": data.get("latest", {}),
                    "returns": data.get("returns", {}),
                }
                print(f"  [OK] {name}: {data.get('latest', {}).get('close', 'N/A')}")
        except Exception as e:
            print(f"  [ERR] {name}: {e}")
            results[code] = {"error": str(e)}
    
    # 保存
    path = os.path.join(DATA_DIR, "index_data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "indices": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"  [SAVE] 已保存到 {path}")
    return results


def refresh_stock_recommendations():
    """刷新股票推荐数据"""
    print("\n[STOCK] 获取股票数据并计算评分...")
    recommendations = []
    errors = []
    success_count = 0
    
    for i, stock_info in enumerate(QUALITY_STOCK_POOL):
        symbol = stock_info["symbol"]
        name = stock_info["name"]
        
        try:
            print(f"  [{i+1}/{len(QUALITY_STOCK_POOL)}] {name} ({symbol})...", end=" ")
            
            # 采集数据
            stock_data = data_collector.collect_stock_data(symbol, name)
            
            # 如果数据采集完全失败（akshare不可用），跳过
            if stock_data.get("meta", {}).get("_note"):
                print("[WARN] 数据不完整，跳过")
                errors.append({"symbol": symbol, "name": name, "error": "数据不完整"})
                continue
            
            # 添加元数据
            stock_data["meta"]["sector"] = stock_info.get("sector", "")
            stock_data["meta"]["dividend_yield"] = stock_info.get("dividend_yield", 0)
            stock_data["meta"]["state_ownership"] = stock_info.get("state_ownership", 0)
            stock_data["meta"]["reason"] = stock_info.get("reason", "")
            
            # 计算评分
            rec = recommendation_engine.recommend(stock_data)
            rec_dict = rec.to_dict()
            rec_dict["reason"] = stock_info.get("reason", "")
            rec_dict["source"] = "live"
            
            recommendations.append(rec_dict)
            success_count += 1
            print(f"[OK] IAS={rec_dict['ias_score']:.1f} Timing={rec_dict['timing_score']:.1f} Final={rec_dict['final_score']:.1f}")
            
        except Exception as e:
            print(f"[ERR] {e}")
            errors.append({"symbol": symbol, "name": name, "error": str(e)})
    
    # 按最终评分降序
    recommendations.sort(key=lambda r: r["final_score"], reverse=True)
    
    # 保存
    result = {
        "updated_at": datetime.now().isoformat(),
        "total": len(recommendations),
        "success_count": success_count,
        "recommendations": recommendations,
        "errors": errors,
    }
    path = os.path.join(DATA_DIR, "recommendations.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n  [OK] 成功: {success_count}/{len(QUALITY_STOCK_POOL)}")
    print(f"  [SAVE] 已保存到 {path}")
    return result


def refresh_market_overview():
    """刷新市场概览"""
    print("\n[OVERVIEW] 生成市场概览...")
    
    overview = {
        "updated_at": datetime.now().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "macro_analysis": {
            "population_trend": "老龄化加速 — 利好中药、医疗器械、养老产业",
            "debt_cycle": "去杠杆中后期 — 利好高股息、现金流稳定的国企",
            "policy_direction": "科技自主+内需拉动 — 利好半导体、AI、新能源、消费",
            "social_trend": "消费升级+数字化 — 利好品牌消费、数字经济",
        },
        "investment_themes": [
            {
                "theme": "老龄化 + 健康中国",
                "drivers": "人口结构变化",
                "sectors": "中药、医疗器械、创新药",
                "stocks": ["600436 片仔癀", "000538 云南白药", "600085 同仁堂", "300760 迈瑞医疗", "600276 恒瑞医药"],
            },
            {
                "theme": "科技自主可控",
                "drivers": "中美博弈 + 政策支持",
                "sectors": "半导体、AI、信创",
                "stocks": ["688981 中芯国际", "002371 北方华创", "002415 海康威视"],
            },
            {
                "theme": "碳中和 + 新能源",
                "drivers": "全球能源转型",
                "sectors": "水电、核电、新能源车、光伏",
                "stocks": ["600900 长江电力", "300750 宁德时代", "002594 比亚迪"],
            },
            {
                "theme": "高股息 + 国企改革",
                "drivers": "低利率环境 + 政策推动",
                "sectors": "银行、能源、运营商",
                "stocks": ["601939 建设银行", "601088 中国神华", "600941 中国移动"],
            },
            {
                "theme": "消费升级 + 国货崛起",
                "drivers": "内需 + 品牌壁垒",
                "sectors": "白酒、调味品、家电",
                "stocks": ["600519 贵州茅台", "000858 五粮液", "603288 海天味业"],
            },
            {
                "theme": "全球化 + 出海",
                "drivers": "产能输出",
                "sectors": "家电出海、新能源出海",
                "stocks": ["600690 海尔智家", "000333 美的集团"],
            },
        ],
    }
    
    path = os.path.join(DATA_DIR, "market_overview.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)
    print(f"  [SAVE] 已保存到 {path}")
    return overview


def main():
    print("=" * 60)
    print("Halo 数据刷新")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)
    
    results = {
        "refresh_time": datetime.now().isoformat(),
        "index_data": None,
        "recommendations": None,
        "market_overview": None,
    }
    
    # 1. 指数数据
    try:
        results["index_data"] = refresh_index_data()
    except Exception as e:
        print(f"[ERR] 指数数据刷新失败: {e}")
    
    # 2. 股票推荐
    try:
        results["recommendations"] = refresh_stock_recommendations()
    except Exception as e:
        print(f"[ERR] 推荐数据刷新失败: {e}")
    
    # 3. 市场概览
    try:
        results["market_overview"] = refresh_market_overview()
    except Exception as e:
        print(f"[ERR] 市场概览刷新失败: {e}")
    
    # 保存刷新状态
    status_path = os.path.join(DATA_DIR, "refresh_status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump({
            "last_refresh": datetime.now().isoformat(),
            "success": results["recommendations"] is not None,
            "stock_count": len(results["recommendations"]["recommendations"]) if results["recommendations"] else 0,
        }, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 60)
    print("[DONE] 数据刷新完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
