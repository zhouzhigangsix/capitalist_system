#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
只运行回测部分，不重新执行选股
"""

import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta

# 配置
BASE_URL = "http://localhost:8080"
DB_FILE = "stocks.db"

def init_backtest_table():
    """初始化回测结果表"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                date TEXT NOT NULL,
                stock_count INTEGER,
                valid_count INTEGER,
                win_count INTEGER,
                lose_count INTEGER,
                win_rate REAL,
                total_return REAL,
                avg_return REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(strategy_name, date)
            )
        ''')
        conn.commit()
        conn.close()
        print("✅ 回测结果表初始化完成")
    except Exception as e:
        print(f"初始化回测表失败: {e}")

def get_next_day_price_simple(code, current_date):
    """获取股票次日收盘价（自动跳过周末）"""
    try:
        # 获取K线数据
        response = requests.get(f"{BASE_URL}/api/kline", params={
            "code": code,
            "type": "day"
        }, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()
        if data['code'] != 0 or not data['data']:
            return None

        kline_list = data['data']['List']
        if not kline_list:
            return None

        # 转换为DataFrame
        df = pd.DataFrame(kline_list)
        df['date'] = pd.to_datetime(df['Time']).dt.strftime('%Y-%m-%d')

        # 找到当前日期的索引
        current_idx = df[df['date'] == current_date].index
        if len(current_idx) == 0:
            return None

        current_idx = current_idx[0]

        # 获取下一个交易日的收盘价
        if current_idx + 1 < len(df):
            next_day = df.iloc[current_idx + 1]
            return float(next_day['Close'])

        return None
    except Exception:
        return None

def get_next_day_price_with_date(code, current_date):
    """
    获取股票次日收盘价和实际日期（自动跳过周末）

    Returns:
        (price, date) 或 None
    """
    try:
        # 获取K线数据
        response = requests.get(f"{BASE_URL}/api/kline", params={
            "code": code,
            "type": "day"
        }, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()
        if data['code'] != 0 or not data['data']:
            return None

        kline_list = data['data']['List']
        if not kline_list:
            return None

        # 转换为DataFrame
        df = pd.DataFrame(kline_list)
        df['date'] = pd.to_datetime(df['Time']).dt.strftime('%Y-%m-%d')

        # 找到当前日期的索引
        current_idx = df[df['date'] == current_date].index
        if len(current_idx) == 0:
            return None

        current_idx = current_idx[0]

        # 获取下一个交易日的收盘价和日期
        if current_idx + 1 < len(df):
            next_day = df.iloc[current_idx + 1]
            return (float(next_day['Close']), next_day['date'])

        return None
    except Exception:
        return None

def calculate_daily_pnl_simple(stocks, date):
    """简化版：计算某天选股组合次日的盈亏"""
    if not stocks:
        return None

    total_return = 0
    valid_count = 0
    win_count = 0
    lose_count = 0

    for stock in stocks:
        code = stock['code']
        buy_price = stock['price']

        # 获取次日收盘价
        next_price = get_next_day_price_simple(code, date)

        if next_price is None:
            continue

        # 计算收益率
        pnl = (next_price - buy_price) / buy_price * 100
        total_return += pnl
        valid_count += 1

        if pnl > 0:
            win_count += 1
        elif pnl < 0:
            lose_count += 1

    if valid_count == 0:
        return None

    avg_return = total_return / valid_count
    win_rate = win_count / valid_count * 100 if valid_count > 0 else 0

    return {
        'date': date,
        'stock_count': len(stocks),
        'valid_count': valid_count,
        'win_count': win_count,
        'lose_count': lose_count,
        'total_return': total_return,
        'avg_return': avg_return,
        'win_rate': win_rate
    }

def calculate_daily_pnl_with_sell_date(stocks, select_date):
    """
    计算某天选股组合次日的盈亏，并返回实际卖出日期

    Args:
        stocks: 选股列表
        select_date: 选股日期（如2025-11-28）

    Returns:
        {
            'select_date': '2025-11-28',  # 选股日期
            'sell_date': '2025-11-29',    # 卖出日期（次日）
            'date': '2025-11-29',         # 用于保存到数据库的日期（等于sell_date）
            ...
        }
    """
    if not stocks:
        return None

    total_return = 0
    valid_count = 0
    win_count = 0
    lose_count = 0
    actual_sell_date = None
    win_stocks = []
    lose_stocks = []

    for stock in stocks:
        code = stock['code']
        name = stock['name']
        buy_price = stock['price']

        # 获取次日收盘价和实际日期
        result = get_next_day_price_with_date(code, select_date)

        if result is None:
            continue

        next_price, sell_date = result
        if actual_sell_date is None:
            actual_sell_date = sell_date

        # 计算收益率
        pnl = (next_price - buy_price) / buy_price * 100
        total_return += pnl
        valid_count += 1

        if pnl > 0:
            win_count += 1
            win_stocks.append({
                'code': code,
                'name': name,
                'pnl': pnl
            })
        elif pnl < 0:
            lose_count += 1
            lose_stocks.append({
                'code': code,
                'name': name,
                'pnl': pnl
            })

    if valid_count == 0 or actual_sell_date is None:
        return None

    avg_return = total_return / valid_count
    win_rate = win_count / valid_count * 100 if valid_count > 0 else 0

    return {
        'select_date': select_date,
        'sell_date': actual_sell_date,
        'date': actual_sell_date,  # 保存到数据库的日期（卖出日）
        'stock_count': len(stocks),
        'valid_count': valid_count,
        'win_count': win_count,
        'lose_count': lose_count,
        'total_return': total_return,
        'avg_return': avg_return,
        'win_rate': win_rate,
        'win_stocks': win_stocks,
        'lose_stocks': lose_stocks
    }

def save_backtest_result_simple(result, strategy_name="b1"):
    """保存回测结果到数据库"""
    if not result:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # 构建详细信息JSON
        import json
        details = {
            'win_stocks': result.get('win_stocks', []),
            'lose_stocks': result.get('lose_stocks', [])
        }
        details_json = json.dumps(details, ensure_ascii=False)

        c.execute('''
            INSERT OR REPLACE INTO backtest_results
            (strategy_name, date, stock_count, valid_count, win_count, lose_count,
             win_rate, total_return, avg_return, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            strategy_name,
            result['date'],
            result['stock_count'],
            result['valid_count'],
            result['win_count'],
            result['lose_count'],
            result['win_rate'],
            result['total_return'],
            result['avg_return'],
            details_json
        ))

        conn.commit()
        conn.close()
        print(f"✅ 回测结果已保存: {result['date']} 收益{result['avg_return']:+.2f}%")
    except Exception as e:
        print(f"保存回测结果失败: {e}")

def run_backtest():
    """
    运行回测
    逻辑：选股日期X的股票 → 在日期Y（X的下一个交易日）卖出
    回测结果保存为日期Y，表示"Y日收盘时的收益"

    例如：11-28选股 → 11-29收盘卖出，结果保存为date=11-29
    """
    print("="*70)
    print("🔄 开始计算回测收益...")
    print("="*70)

    # 初始化回测表
    init_backtest_table()

    # 获取前几天的日期
    today = datetime.now()

    # 获取所有有选股数据的日期
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT DISTINCT date
        FROM strategy_results
        WHERE strategy_name = 'b1'
        ORDER BY date DESC
        LIMIT 10
    """)
    stock_dates = [row[0] for row in c.fetchall()]
    conn.close()

    print(f"📅 发现选股日期: {stock_dates}")

    backtest_count = 0
    for select_date in stock_dates:
        print(f"\n📅 回测: {select_date} 选股")

        # 获取该日期评分前10的股票
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            SELECT code, name, price, score, j_val, amplitude, vol_ratio, score_detail
            FROM strategy_results
            WHERE strategy_name = 'b1' AND date = ?
            ORDER BY score DESC
            LIMIT 10
        """, (select_date,))

        rows = c.fetchall()
        conn.close()

        if not rows:
            print(f"  ⚠️  无选股数据，跳过")
            continue

        top_stocks = []
        for row in rows:
            top_stocks.append({
                'code': row[0],
                'name': row[1],
                'price': row[2],
                'score': row[3],
                'j_val': row[4],
                'amplitude': row[5],
                'vol_ratio': row[6],
                'score_detail': row[7]
            })

        print(f"  ✅ 找到 {len(top_stocks)} 只股票")

        # 计算次日收益
        result = calculate_daily_pnl_with_sell_date(top_stocks, select_date)

        if result:
            # 保存回测结果（使用卖出日期作为回测日期）
            save_backtest_result_simple(result)
            print(f"  ✅ {result['select_date']} 选股 → {result['sell_date']} 卖出")
            print(f"     平均收益 {result['avg_return']:+.2f}%, 胜率 {result['win_rate']:.1f}%")
            backtest_count += 1
        else:
            print(f"  ⚠️  无法计算次日收益（可能今天还未收盘）")

    print(f"\n{'='*70}")
    print(f"✅ 共完成 {backtest_count} 个交易日的回测")
    print(f"{'='*70}")

if __name__ == "__main__":
    run_backtest()
