#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B1 策略回测脚本
回测逻辑：
1. 获取最近6天的选股结果
2. 对每天选出的前10名股票（不足10个按实际数量）
3. 计算次日的收益率
4. 统计5天的回测表现
"""

import sqlite3
import requests
import pandas as pd
from datetime import datetime, timedelta

# 配置
BASE_URL = "http://139.155.158.47:8080"  # 使用服务器API
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
    except Exception as e:
        print(f"初始化回测表失败: {e}")

def save_backtest_result(result, strategy_name="b1"):
    """保存回测结果到数据库"""
    if not result:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        win_count = sum(1 for d in result['details'] if d['pnl'] > 0)
        lose_count = sum(1 for d in result['details'] if d['pnl'] < 0)
        win_rate = win_count / result['valid_count'] * 100 if result['valid_count'] > 0 else 0

        c.execute('''
            INSERT OR REPLACE INTO backtest_results
            (strategy_name, date, stock_count, valid_count, win_count, lose_count,
             win_rate, total_return, avg_return)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            strategy_name,
            result['date'],
            result['stock_count'],
            result['valid_count'],
            win_count,
            lose_count,
            win_rate,
            result['total_return'],
            result['avg_return']
        ))

        conn.commit()
        conn.close()
        print(f"✅ 回测结果已保存: {result['date']} 收益{result['avg_return']:+.2f}%")
    except Exception as e:
        print(f"❌ 保存回测结果失败: {e}")

def get_trading_dates(days=6):
    """获取最近N个交易日（包括今天）"""
    dates = []
    today = datetime.now()

    # 简单处理：获取最近N天（实际应该排除周末，但数据库中没有数据的日期会自动跳过）
    for i in range(days - 1, -1, -1):
        date = today - timedelta(days=i)
        dates.append(date.strftime('%Y-%m-%d'))

    return dates

def get_top_stocks_from_db(date, top_n=10):
    """从数据库获取指定日期评分最高的前N只股票"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        query = """
            SELECT code, name, price, score, j_val, amplitude, vol_ratio, score_detail
            FROM strategy_results
            WHERE strategy_name = 'b1' AND date = ?
            ORDER BY score DESC
            LIMIT ?
        """

        c.execute(query, (date, top_n))
        results = c.fetchall()
        conn.close()

        if not results:
            return []

        stocks = []
        for row in results:
            stocks.append({
                'code': row[0],
                'name': row[1],
                'price': row[2],
                'score': row[3],
                'j_val': row[4],
                'amplitude': row[5],
                'vol_ratio': row[6],
                'score_detail': row[7]
            })

        return stocks
    except Exception as e:
        print(f"❌ 从数据库获取 {date} 数据失败: {e}")
        return []

def get_next_day_price(code, current_date):
    """获取股票次日收盘价（会自动跳过周末）"""
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

        # 获取下一个交易日的收盘价（自动跳过周末和节假日）
        if current_idx + 1 < len(df):
            next_day = df.iloc[current_idx + 1]
            return float(next_day['Close'])

        return None
    except Exception as e:
        # print(f"获取 {code} 次日价格失败: {e}")
        return None

def calculate_daily_pnl(stocks, date):
    """计算某天选股组合次日的盈亏"""
    if not stocks:
        return None

    total_return = 0
    valid_count = 0
    details = []

    for stock in stocks:
        code = stock['code']
        buy_price = stock['price']

        # 获取次日收盘价
        next_price = get_next_day_price(code, date)

        if next_price is None:
            # print(f"  ⚠️  {code} {stock['name']} 无法获取次日价格，跳过")
            continue

        # 计算收益率
        pnl = (next_price - buy_price) / buy_price * 100
        total_return += pnl
        valid_count += 1

        details.append({
            'code': code,
            'name': stock['name'],
            'score': stock['score'],
            'buy_price': buy_price,
            'sell_price': next_price,
            'pnl': pnl
        })

    if valid_count == 0:
        return None

    avg_return = total_return / valid_count

    return {
        'date': date,
        'stock_count': len(stocks),
        'valid_count': valid_count,
        'total_return': total_return,
        'avg_return': avg_return,
        'details': details
    }

def main():
    print("=" * 80)
    print("📊 B1 策略回测分析")
    print("=" * 80)
    print(f"回测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"回测逻辑: 每天选出评分前10名，次日收盘卖出\n")

    # 初始化回测结果表
    init_backtest_table()

    # 获取最近6天的日期
    dates = get_trading_dates(6)
    print(f"📅 回测日期: {dates[0]} ~ {dates[-1]} (最近6天)\n")

    # 存储所有回测结果
    all_results = []

    # 对前5天进行回测（第6天没有次日数据）
    for i in range(5):
        date = dates[i]
        print(f"\n{'=' * 80}")
        print(f"📆 {date} (T日) → {dates[i+1] if i+1 < len(dates) else '次日'} (T+1日)")
        print(f"{'=' * 80}")

        # 获取当天评分前10的股票
        top_stocks = get_top_stocks_from_db(date, top_n=10)

        if not top_stocks:
            print(f"❌ {date} 无选股数据，跳过")
            continue

        print(f"✅ 选出 {len(top_stocks)} 只股票（按评分排序）:")
        for idx, stock in enumerate(top_stocks, 1):
            print(f"   {idx:2d}. {stock['code']} {stock['name']:8s} "
                  f"评分:{stock['score']:5.1f} 价格:{stock['price']/100:.2f}元")

        # 计算次日盈亏
        print(f"\n⏳ 计算次日收益...")
        result = calculate_daily_pnl(top_stocks, date)

        if result is None:
            print(f"❌ 无法计算次日收益（可能是数据不足）")
            continue

        all_results.append(result)

        # 保存回测结果到数据库
        save_backtest_result(result)

        # 显示详细结果
        print(f"\n📈 次日收益明细:")
        win_count = 0
        lose_count = 0

        for detail in result['details']:
            pnl_sign = "🔺" if detail['pnl'] > 0 else "🔻" if detail['pnl'] < 0 else "➖"
            pnl_color = f"{detail['pnl']:+.2f}%"
            print(f"   {pnl_sign} {detail['code']} {detail['name']:8s} "
                  f"买入:{detail['buy_price']/100:.2f} 卖出:{detail['sell_price']/100:.2f} "
                  f"收益:{pnl_color}")

            if detail['pnl'] > 0:
                win_count += 1
            elif detail['pnl'] < 0:
                lose_count += 1

        print(f"\n{'─' * 80}")
        print(f"📊 当日统计:")
        print(f"   选股数量: {result['stock_count']} 只")
        print(f"   有效样本: {result['valid_count']} 只")
        print(f"   盈利股票: {win_count} 只 ({win_count/result['valid_count']*100:.1f}%)")
        print(f"   亏损股票: {lose_count} 只 ({lose_count/result['valid_count']*100:.1f}%)")
        print(f"   平均收益: {result['avg_return']:+.2f}%")
        print(f"   累计收益: {result['total_return']:+.2f}%")

    # 汇总统计
    if all_results:
        print(f"\n\n{'=' * 80}")
        print(f"🎯 回测总结 (近5个交易日)")
        print(f"{'=' * 80}")

        total_trades = sum(r['valid_count'] for r in all_results)
        total_pnl = sum(r['total_return'] for r in all_results)
        avg_daily_return = sum(r['avg_return'] for r in all_results) / len(all_results)

        # 统计胜率
        all_details = []
        for r in all_results:
            all_details.extend(r['details'])

        win_trades = sum(1 for d in all_details if d['pnl'] > 0)
        lose_trades = sum(1 for d in all_details if d['pnl'] < 0)
        win_rate = win_trades / total_trades * 100 if total_trades > 0 else 0

        print(f"\n📅 回测天数: {len(all_results)} 天")
        print(f"📊 总交易次数: {total_trades} 次")
        print(f"📈 盈利次数: {win_trades} 次")
        print(f"📉 亏损次数: {lose_trades} 次")
        print(f"🎲 胜率: {win_rate:.1f}%")
        print(f"💰 累计收益率: {total_pnl:+.2f}%")
        print(f"📊 日均收益率: {avg_daily_return:+.2f}%")
        print(f"📈 平均单笔收益: {total_pnl/total_trades:+.2f}%")

        # 按日期展示
        print(f"\n📅 逐日收益:")
        print(f"{'─' * 80}")
        print(f"{'日期':<12} {'选股':<6} {'有效':<6} {'盈利':<6} {'亏损':<6} {'日均收益':<10} {'累计收益':<10}")
        print(f"{'─' * 80}")

        for r in all_results:
            win_count = sum(1 for d in r['details'] if d['pnl'] > 0)
            lose_count = sum(1 for d in r['details'] if d['pnl'] < 0)
            print(f"{r['date']:<12} {r['stock_count']:<6} {r['valid_count']:<6} "
                  f"{win_count:<6} {lose_count:<6} {r['avg_return']:>+9.2f}% {r['total_return']:>+9.2f}%")

        print(f"{'=' * 80}")

        # 评估
        if avg_daily_return > 0:
            print(f"\n✅ 策略表现: 正收益 (日均 {avg_daily_return:+.2f}%)")
        elif avg_daily_return == 0:
            print(f"\n➖ 策略表现: 持平")
        else:
            print(f"\n❌ 策略表现: 负收益 (日均 {avg_daily_return:+.2f}%)")
    else:
        print(f"\n❌ 没有足够的数据进行回测")

    print(f"\n{'=' * 80}")
    print(f"✅ 回测完成")
    print(f"{'=' * 80}\n")

if __name__ == "__main__":
    main()
