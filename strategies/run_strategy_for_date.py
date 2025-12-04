#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指定日期运行选股策略
用于手动补充历史数据
"""

import requests
import pandas as pd
import numpy as np
import time
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8080"
MAX_WORKERS = 10
DB_FILE = "stocks.db"

# 全局股票名称缓存
STOCK_NAMES_CACHE = {}

# 策略参数
M1 = 14
M2 = 28
M3 = 57
M4 = 114

# 目标日期 (从命令行参数获取,格式: YYYY-MM-DD)
TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else "2025-12-02"

def load_stock_names():
    """批量加载股票名称"""
    global STOCK_NAMES_CACHE
    try:
        response = requests.get(f"{BASE_URL}/api/stock-names", timeout=30)
        response.raise_for_status()
        data = response.json()
        if data['code'] == 0:
            STOCK_NAMES_CACHE = data['data']['data']
            print(f"✅ 成功加载 {len(STOCK_NAMES_CACHE)} 只股票名称")
            return True
    except Exception as e:
        print(f"❌ 加载股票名称失败: {e}")
        return False

def get_stock_name(code):
    """获取股票名称"""
    if code in STOCK_NAMES_CACHE:
        return STOCK_NAMES_CACHE[code]
    return ''

def get_all_codes():
    """获取全市场股票代码"""
    try:
        response = requests.get(f"{BASE_URL}/api/stock-codes")
        response.raise_for_status()
        data = response.json()
        if data['code'] == 0:
            return data['data']['list']
        return []
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []

def get_kline_data(code):
    """获取K线数据"""
    try:
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
        if not kline_list or len(kline_list) < M4 + 5:
            return None

        # 转换为DataFrame
        df = pd.DataFrame(kline_list)
        df = df.rename(columns={
            'Time': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
            'Amount': 'amount',
            'Last': 'pre_close'
        })

        # 确保数值类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pre_close']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col])

        return df
    except Exception:
        return None

def calculate_indicators(df):
    """计算技术指标"""
    # 知行多空线
    df['ma_m1'] = df['close'].rolling(window=M1).mean()
    df['ma_m2'] = df['close'].rolling(window=M2).mean()
    df['ma_m3'] = df['close'].rolling(window=M3).mean()
    df['ma_m4'] = df['close'].rolling(window=M4).mean()
    df['zx_dk_line'] = (df['ma_m1'] + df['ma_m2'] + df['ma_m3'] + df['ma_m4']) / 4

    # 知行短期趋势线
    df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['zx_trend_line'] = df['ema10'].ewm(span=10, adjust=False).mean()

    # KDJ
    low_min = df['low'].rolling(window=9).min()
    high_max = df['high'].rolling(window=9).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['k'] = df['rsv'].ewm(com=2, adjust=False).mean()
    df['d'] = df['k'].ewm(com=2, adjust=False).mean()
    df['j'] = 3 * df['k'] - 2 * df['d']

    # 振幅
    df['amplitude'] = (df['high'] - df['low']) / df['pre_close'] * 100

    # 成交量均值
    df['vol_ma12'] = df['volume'].rolling(window=12).mean()

    # 成交额均值
    df['amount_ma20'] = df['amount'].rolling(window=20).mean()

    return df

def calculate_score(curr, df):
    """计算评分"""
    score_detail = {}
    total_score = 0

    # 1. 超卖程度 (28分)
    j_val = curr['j']
    if j_val <= 0:
        score_oversold = 28
    elif j_val <= 13:
        score_oversold = 28 - (j_val / 13) * 11
    else:
        score_oversold = 0
    score_detail['oversold'] = round(score_oversold, 2)
    total_score += score_oversold

    # 2. 趋势强度 (24分)
    trend_deviation = (curr['close'] - curr['zx_dk_line']) / curr['zx_dk_line'] * 100
    if trend_deviation >= 10:
        score_trend = 24
    elif trend_deviation >= 7:
        score_trend = 21
    elif trend_deviation >= 5:
        score_trend = 17
    elif trend_deviation >= 3:
        score_trend = 14
    elif trend_deviation >= 1:
        score_trend = 11
    elif trend_deviation >= 0:
        score_trend = 7
    else:
        score_trend = 0
    score_detail['trend'] = round(score_trend, 2)
    total_score += score_trend

    # 3. 缩量程度 (18分)
    vol_ratio = curr['volume'] / curr['vol_ma12'] if curr['vol_ma12'] > 0 else 1
    if vol_ratio <= 0.3:
        score_volume = 18
    elif vol_ratio <= 0.4:
        score_volume = 16
    elif vol_ratio <= 0.52:
        score_volume = 13
    else:
        score_volume = 0
    score_detail['volume'] = round(score_volume, 2)
    total_score += score_volume

    # 4. 短期动能 (15分)
    trend_strength = (curr['zx_trend_line'] - curr['zx_dk_line']) / curr['zx_dk_line'] * 100
    if trend_strength >= 5:
        score_momentum = 15
    elif trend_strength >= 3:
        score_momentum = 12
    elif trend_strength >= 1:
        score_momentum = 9
    elif trend_strength > 0:
        score_momentum = 6
    else:
        score_momentum = 0
    score_detail['momentum'] = round(score_momentum, 2)
    total_score += score_momentum

    # 5. 振幅收敛 (10分)
    amplitude = curr['amplitude']
    if amplitude <= 1:
        score_amplitude = 10
    elif amplitude <= 2:
        score_amplitude = 8
    elif amplitude <= 3:
        score_amplitude = 6
    elif amplitude <= 4:
        score_amplitude = 4
    else:
        score_amplitude = 0
    score_detail['amplitude'] = round(score_amplitude, 2)
    total_score += score_amplitude

    # 6. 流动性 (5分)
    avg_amount = curr['amount_ma20'] if curr['amount_ma20'] > 0 else 0
    if avg_amount >= 500000000:
        score_liquidity = 5
    elif avg_amount >= 200000000:
        score_liquidity = 4
    elif avg_amount >= 100000000:
        score_liquidity = 3
    elif avg_amount >= 50000000:
        score_liquidity = 2
    elif avg_amount >= 10000000:
        score_liquidity = 1
    else:
        score_liquidity = 0
    score_detail['liquidity'] = round(score_liquidity, 2)
    total_score += score_liquidity

    detail_str = f"超卖:{score_detail['oversold']},趋势:{score_detail['trend']},缩量:{score_detail['volume']},动能:{score_detail['momentum']},振幅:{score_detail['amplitude']},流动性:{score_detail['liquidity']}"

    return round(total_score, 2), detail_str, round(trend_deviation, 2)

def has_gap_in_past_days(df, days=40):
    """检查过去N天是否有跳空缺口"""
    if df is None or len(df) < 2:
        return False

    start_idx = max(0, len(df) - days - 1)
    check_df = df.iloc[start_idx:]

    for i in range(1, len(check_df)):
        curr = check_df.iloc[i]
        prev = check_df.iloc[i-1]

        # 向上跳空：当日最低价 > 前日最高价
        if curr['low'] > prev['high']:
            return True

        # 向下跳空：当日最高价 < 前日最低价
        if curr['high'] < prev['low']:
            return True

    return False


def has_top_volume_stagnant_in_past_days(df, days=40, ma_period=20,
                                         volume_threshold=1.5,
                                         up_strength_threshold=0.01):
    """检查过去N天是否有"高位放量但滞涨"的现象"""
    if df is None or len(df) < ma_period + 1:
        return False

    # 计算均线（如果还未计算）
    if 'ma20' not in df.columns:
        df['ma20'] = df['close'].rolling(window=ma_period).mean()
    if 'vol_ma20' not in df.columns:
        df['vol_ma20'] = df['volume'].rolling(window=ma_period).mean()

    # 取过去N天的数据
    start_idx = max(0, len(df) - days)
    check_df = df.iloc[start_idx:]

    # 遍历检查是否出现"高位放量但滞涨"
    for i in range(len(check_df)):
        row = check_df.iloc[i]

        # 检查均线值是否有效
        if pd.isna(row['ma20']) or pd.isna(row['vol_ma20']):
            continue

        # 条件1：高位（close > MA20）
        is_high_price = row['close'] > row['ma20']

        # 条件2：放量（volume > vol_ma20 × threshold）
        is_high_volume = row['volume'] > row['vol_ma20'] * volume_threshold

        # 条件3：滞涨或阴线
        is_stagnant = (
            row['close'] < row['open'] or  # 阴线
            (row['close'] > row['open'] and
             (row['close'] - row['open']) / row['open'] < up_strength_threshold)
        )

        # 三个条件同时满足 → 检测到危险信号
        if is_high_price and is_high_volume and is_stagnant:
            return True

    return False


def analyze_stock_for_date(code):
    """分析指定日期的股票"""
    df = get_kline_data(code)
    if df is None:
        return None

    try:
        df = calculate_indicators(df)

        # 找到目标日期的数据
        df['date_only'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        target_df = df[df['date_only'] == TARGET_DATE]

        if len(target_df) == 0:
            return None

        curr = target_df.iloc[-1]  # 获取目标日期的数据

        # 检查数据有效性
        if np.isnan(curr['zx_dk_line']) or np.isnan(curr['zx_trend_line']) or np.isnan(curr['j']):
            return None

        # 策略条件判断 (7个条件)
        cond1 = curr['close'] > curr['zx_dk_line']
        cond2 = curr['j'] < 13
        cond3 = curr['zx_trend_line'] > curr['zx_dk_line']
        cond4 = curr['amplitude'] < 4
        cond5 = curr['volume'] < (curr['vol_ma12'] * 0.52)
        # 6. 过去40天无跳空缺口
        cond6 = not has_gap_in_past_days(df, days=40)
        # 7. 过去40天无高位放量但滞涨的现象
        cond7 = not has_top_volume_stagnant_in_past_days(df, days=40, ma_period=20,
                                                         volume_threshold=1.5,
                                                         up_strength_threshold=0.01)

        if cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7:
            name = get_stock_name(code)

            # 剔除ST股票
            if name and ('ST' in name or '*ST' in name or 'S*' in name):
                return None

            score, score_detail, trend_strength = calculate_score(curr, df)

            return {
                'code': code,
                'name': name,
                'price': float(curr['close']),
                'j_val': float(curr['j']),
                'amplitude': float(curr['amplitude']),
                'vol_ratio': float(curr['volume'] / curr['vol_ma12']) if curr['vol_ma12'] > 0 else 0,
                'score': score,
                'score_detail': score_detail,
                'trend_strength': trend_strength,
                'date': TARGET_DATE
            }

    except Exception:
        pass

    return None

def save_to_db(results, strategy_name="b1"):
    """保存结果到数据库"""
    if not results:
        return

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    count = 0
    for res in results:
        try:
            c.execute('''
                INSERT OR REPLACE INTO strategy_results
                (strategy_name, code, name, price, j_val, amplitude, vol_ratio, score, score_detail, trend_strength, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                strategy_name,
                res['code'],
                res.get('name', ''),
                res['price'],
                res['j_val'],
                res['amplitude'],
                res['vol_ratio'],
                res['score'],
                res['score_detail'],
                res['trend_strength'],
                res['date']
            ))
            count += 1
        except Exception as e:
            print(f"保存 {res['code']} 失败: {e}")

    conn.commit()
    conn.close()
    print(f"💾 已保存 {count} 条记录到数据库")

def main():
    print("="*70)
    print(f"🚀 运行 B1 选股策略 - 目标日期: {TARGET_DATE}")
    print("="*70)

    load_stock_names()

    codes = get_all_codes()
    print(f"📊 获取到 {len(codes)} 只股票")

    results = []
    processed = 0
    total = len(codes)

    print("⚡️ 开始并发分析...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_code = {executor.submit(analyze_stock_for_date, code): code for code in codes}

        for future in as_completed(future_to_code):
            processed += 1
            if processed % 100 == 0:
                print(f"进度: {processed}/{total} ({(processed/total*100):.1f}%) - 命中: {len(results)}")

            res = future.result()
            if res:
                results.append(res)

    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "="*70)
    print(f"🎉 选股完成！耗时: {duration:.2f}秒")
    print(f"共扫描: {total} 只")
    print(f"命中: {len(results)} 只")
    print("="*70)

    if results:
        results.sort(key=lambda x: x['score'], reverse=True)
        save_to_db(results)

        print(f"\n📋 选股结果 Top 10 (日期: {TARGET_DATE}):")
        print("="*70)
        for idx, row in enumerate(results[:10], 1):
            print(f"{idx:2d}. {row['code']} {row['name']:8s} - 评分:{row['score']:.1f} 价格:{row['price']:.2f}")
        print("="*70)
    else:
        print("未找到符合条件的股票。")

if __name__ == "__main__":
    main()
