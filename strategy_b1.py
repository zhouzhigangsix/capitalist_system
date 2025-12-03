import requests
import pandas as pd
import numpy as np
import time
import sqlite3
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8080"
MAX_WORKERS = 10  # 并发线程数
DB_FILE = "stocks.db" # 数据库文件

# 全局股票名称缓存
STOCK_NAMES_CACHE = {}

# 策略参数
M1 = 14
M2 = 28
M3 = 57
M4 = 114

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 创建策略结果表 - 添加评分字段
    c.execute('''
        CREATE TABLE IF NOT EXISTS strategy_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT,
            price REAL,
            j_val REAL,
            amplitude REAL,
            vol_ratio REAL,
            score REAL DEFAULT 0,
            score_detail TEXT,
            trend_strength REAL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(strategy_name, code, date)
        )
    ''')
    conn.commit()
    conn.close()
    print(f"📦 数据库 {DB_FILE} 初始化完成")

def load_stock_names():
    """批量加载股票代码和名称映射"""
    global STOCK_NAMES_CACHE
    try:
        print("📥 正在批量加载股票名称...")
        response = requests.get(f"{BASE_URL}/api/stock-names", timeout=30)
        response.raise_for_status()
        data = response.json()
        if data['code'] == 0:
            STOCK_NAMES_CACHE = data['data']['data']
            print(f"✅ 成功加载 {len(STOCK_NAMES_CACHE)} 只股票名称")
            return True
        else:
            print(f"❌ 加载股票名称失败: {data.get('msg', '未知错误')}")
            return False
    except Exception as e:
        print(f"❌ 批量加载股票名称失败: {e}")
        return False


def calculate_score(curr, df):
    """
    计算股票评分（100分制）

    评分维度：
    1. 超卖程度 (28分) - J值越低，分数越高
    2. 趋势强度 (24分) - 价格偏离多空线越多，趋势越强
    3. 缩量程度 (18分) - 量比越小，缩量越明显
    4. 短期动能 (15分) - 短期趋势线相对多空线偏离度
    5. 振幅收敛 (10分) - 振幅越小，变盘概率越大
    6. 流动性 (5分) - 成交额越高，流动性越好
    """
    score_detail = {}
    total_score = 0

    # 1. 超卖程度评分 (28分)
    j_val = curr['j']
    if j_val <= 0:
        score_oversold = 28
    elif j_val <= 13:
        score_oversold = 28 - (j_val / 13) * 11  # 线性递减
    else:
        score_oversold = 0
    score_detail['oversold'] = round(score_oversold, 2)
    total_score += score_oversold

    # 2. 趋势强度评分 (24分)
    # 计算价格相对多空线的偏离度
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

    # 3. 缩量程度评分 (18分)
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

    # 4. 短期动能评分 (15分)
    # 短期趋势线相对多空线的偏离度
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

    # 5. 振幅收敛评分 (10分)
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

    # 6. 流动性评分 (5分)
    # 基于最近20天平均成交额
    avg_amount = curr['amount_ma20'] if curr['amount_ma20'] > 0 else 0
    # 成交额单位：元，设定分级标准
    if avg_amount >= 500000000:  # 5亿以上
        score_liquidity = 5
    elif avg_amount >= 200000000:  # 2-5亿
        score_liquidity = 4
    elif avg_amount >= 100000000:  # 1-2亿
        score_liquidity = 3
    elif avg_amount >= 50000000:  # 5000万-1亿
        score_liquidity = 2
    elif avg_amount >= 10000000:  # 1000万-5000万
        score_liquidity = 1
    else:  # 1000万以下
        score_liquidity = 0
    score_detail['liquidity'] = round(score_liquidity, 2)
    total_score += score_liquidity

    # 构建评分详情字符串
    detail_str = f"超卖:{score_detail['oversold']},趋势:{score_detail['trend']},缩量:{score_detail['volume']},动能:{score_detail['momentum']},振幅:{score_detail['amplitude']},流动性:{score_detail['liquidity']}"

    return round(total_score, 2), detail_str, round(trend_deviation, 2)

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

def get_stock_name(code):
    """获取股票名称（优先从缓存获取）"""
    # 优先从缓存获取
    if code in STOCK_NAMES_CACHE:
        return STOCK_NAMES_CACHE[code]

    # 缓存未命中，尝试通过API获取（fallback）
    try:
        # 去掉市场前缀 (sh/sz)
        clean_code = code[2:] if code.startswith(('sh', 'sz')) else code
        response = requests.get(f"{BASE_URL}/api/search?keyword={clean_code}", timeout=5)
        response.raise_for_status()
        data = response.json()
        if data['code'] == 0 and len(data['data']) > 0:
            # 返回第一个匹配项的名称
            name = data['data'][0].get('name', '')
            # 更新到缓存
            STOCK_NAMES_CACHE[code] = name
            return name
        return ''
    except Exception:
        return ''

def get_kline_data(code):
    """获取单只股票K线数据"""
    try:
        # 获取日K线，默认是前复权
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
    # 1. 计算知行多空线
    df['ma_m1'] = df['close'].rolling(window=M1).mean()
    df['ma_m2'] = df['close'].rolling(window=M2).mean()
    df['ma_m3'] = df['close'].rolling(window=M3).mean()
    df['ma_m4'] = df['close'].rolling(window=M4).mean()
    df['zx_dk_line'] = (df['ma_m1'] + df['ma_m2'] + df['ma_m3'] + df['ma_m4']) / 4

    # 2. 计算知行短期趋势线: EMA(EMA(C,10),10)
    df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['zx_trend_line'] = df['ema10'].ewm(span=10, adjust=False).mean()

    # 3. 计算KDJ
    low_min = df['low'].rolling(window=9).min()
    high_max = df['high'].rolling(window=9).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min) * 100
    df['k'] = df['rsv'].ewm(com=2, adjust=False).mean()
    df['d'] = df['k'].ewm(com=2, adjust=False).mean()
    df['j'] = 3 * df['k'] - 2 * df['d']

    # 4. 计算振幅
    df['amplitude'] = (df['high'] - df['low']) / df['pre_close'] * 100

    # 5. 计算成交量均值 (最近12天)
    df['vol_ma12'] = df['volume'].rolling(window=12).mean()

    # 6. 计算成交额均值 (最近20天，用于流动性评估)
    df['amount_ma20'] = df['amount'].rolling(window=20).mean()

    return df

def analyze_stock(code):
    """分析单只股票"""
    df = get_kline_data(code)
    if df is None:
        return None

    try:
        df = calculate_indicators(df)

        # 获取最新一行数据（当日）
        curr = df.iloc[-1]

        # 检查数据是否有效
        if np.isnan(curr['zx_dk_line']) or np.isnan(curr['zx_trend_line']) or np.isnan(curr['j']):
            return None

        # --- 策略条件判断 ---

        # 1. 股价高于当日知行多空线价格
        cond1 = curr['close'] > curr['zx_dk_line']

        # 2. 当前日 KDJ 里面的 J值 < 13
        cond2 = curr['j'] < 13

        # 3. 知行短期趋势线价格大于知行多空线价格
        cond3 = curr['zx_trend_line'] > curr['zx_dk_line']

        # 4. 当日股价振幅小于4%
        cond4 = curr['amplitude'] < 4

        # 5. 当日交易量小于最近12天交易量均量的52%
        cond5 = curr['volume'] < (curr['vol_ma12'] * 0.52)

        if cond1 and cond2 and cond3 and cond4 and cond5:
            # 获取股票名称
            name = get_stock_name(code)

            # 剔除ST股票（特别处理股票，退市风险高）
            if name and ('ST' in name or '*ST' in name or 'S*' in name):
                return None

            # 计算评分
            score, score_detail, trend_strength = calculate_score(curr, df)

            # 格式化日期
            date_str = curr['date'].split('T')[0] if 'T' in curr['date'] else curr['date']

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
                'date': date_str
            }

    except Exception as e:
        pass

    return None

def get_score_level(score):
    """根据评分返回星级"""
    if score >= 90:
        return "⭐⭐⭐⭐⭐"
    elif score >= 80:
        return "⭐⭐⭐⭐"
    elif score >= 70:
        return "⭐⭐⭐"
    elif score >= 60:
        return "⭐⭐"
    else:
        return "⭐"

def main():
    print("🚀 开始执行 B1 选股策略（含量化评分）...")
    print(f"📅 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    init_db()

    # 0. 批量加载股票名称（性能优化）
    load_stock_names()

    # 1. 获取股票列表
    codes = get_all_codes()
    print(f"📊 获取到 {len(codes)} 只股票")

    # 测试模式：只跑前100只
    # codes = codes[:100]

    results = []
    processed = 0
    total = len(codes)

    print("⚡️ 开始并发分析...")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_code = {executor.submit(analyze_stock, code): code for code in codes}

        for future in as_completed(future_to_code):
            code = future_to_code[future]
            processed += 1
            if processed % 100 == 0:
                print(f"进度: {processed}/{total} ({(processed/total*100):.1f}%) - 命中: {len(results)}")

            res = future.result()
            if res:
                results.append(res)
                stars = get_score_level(res['score'])
                print(f"✅ 发现目标: {res['code']} - 价格:{res['price']:.2f} 评分:{res['score']:.1f} {stars}")

    end_time = time.time()
    duration = end_time - start_time

    print("\n" + "="*70)
    print(f"🎉 选股完成！耗时: {duration:.2f}秒")
    print(f"共扫描: {total} 只")
    print(f"命中: {len(results)} 只")
    print("="*70)

    if results:
        # 按评分降序排序
        results.sort(key=lambda x: x['score'], reverse=True)

        # 保存到数据库
        save_to_db(results)

        # 转换为DataFrame展示
        res_df = pd.DataFrame(results)
        print("\n📋 选股结果（按评分降序）:")
        print("="*70)
        for idx, row in res_df.head(20).iterrows():
            stars = get_score_level(row['score'])
            print(f"{stars} {row['code']} - 评分:{row['score']:.1f} 价格:{row['price']:.2f} J值:{row['j_val']:.2f} 振幅:{row['amplitude']:.2f}%")

        print("\n" + "="*70)
        print(f"💡 评分说明:")
        print(f"   90-100分 ⭐⭐⭐⭐⭐ : 极优，重点关注")
        print(f"   80-89分  ⭐⭐⭐⭐  : 优秀，高概率机会")
        print(f"   70-79分  ⭐⭐⭐   : 良好，符合预期")
        print(f"   60-69分  ⭐⭐    : 一般，信号偏弱")
        print(f"   <60分    ⭐     : 较差，优先级低")
        print("="*70)
    else:
        print("未找到符合条件的股票。")

    # 执行前一天的回测
    run_previous_day_backtest()

def run_previous_day_backtest():
    """运行前一天的回测（T-1日选股，T日验证收益）"""
    print("\n" + "="*70)
    print("🔄 开始计算前一天选股的回测收益...")
    print("="*70)

    try:
        # 导入回测脚本的功能
        from datetime import timedelta

        # 获取前一个交易日的日期（简单处理：向前推1-3天）
        today = datetime.now()
        prev_dates = []
        for i in range(1, 4):
            prev_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            prev_dates.append(prev_date)

        # 初始化回测表
        init_backtest_table()

        # 尝试对前3天内的每一天进行回测
        backtest_success = False
        for prev_date in prev_dates:
            print(f"\n📅 尝试回测日期: {prev_date}")

            # 获取该日期评分前10的股票
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                SELECT code, name, price, score, j_val, amplitude, vol_ratio, score_detail
                FROM strategy_results
                WHERE strategy_name = 'b1' AND date = ?
                ORDER BY score DESC
                LIMIT 10
            """, (prev_date,))

            rows = c.fetchall()
            conn.close()

            if not rows:
                print(f"  ⚠️  {prev_date} 无选股数据，跳过")
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
            result = calculate_daily_pnl_simple(top_stocks, prev_date)

            if result:
                # 保存回测结果
                save_backtest_result_simple(result)
                print(f"  ✅ 回测完成: 平均收益 {result['avg_return']:+.2f}%, 胜率 {result['win_rate']:.1f}%")
                backtest_success = True
                break  # 成功回测一天就退出
            else:
                print(f"  ⚠️  无法计算次日收益，可能是数据不足")

        if not backtest_success:
            print("\n❌ 未能成功回测任何日期")

        print("="*70)
    except Exception as e:
        print(f"❌ 回测执行失败: {e}")
        import traceback
        traceback.print_exc()

def calculate_daily_pnl_simple(stocks, date):
    """简化版：计算某天选股组合次日的盈亏"""
    if not stocks:
        return None

    total_return = 0
    valid_count = 0
    win_count = 0
    lose_count = 0

    # 保存详细信息
    win_stocks = []  # 盈利股票
    lose_stocks = []  # 亏损股票

    for stock in stocks:
        code = stock['code']
        name = stock.get('name', '')
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

    if valid_count == 0:
        return None

    avg_return = total_return / valid_count
    win_rate = win_count / valid_count * 100 if valid_count > 0 else 0

    # 生成详细信息JSON
    import json
    details = {
        'win_stocks': win_stocks,
        'lose_stocks': lose_stocks
    }
    details_json = json.dumps(details, ensure_ascii=False)

    return {
        'date': date,
        'stock_count': len(stocks),
        'valid_count': valid_count,
        'win_count': win_count,
        'lose_count': lose_count,
        'total_return': total_return,
        'avg_return': avg_return,
        'win_rate': win_rate,
        'details': details_json
    }

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
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(strategy_name, date)
            )
        ''')

        # 检查是否需要添加details列（如果表已存在但没有details列）
        try:
            c.execute('SELECT details FROM backtest_results LIMIT 1')
        except:
            # details列不存在，添加它
            c.execute('ALTER TABLE backtest_results ADD COLUMN details TEXT')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"初始化回测表失败: {e}")

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
    except Exception as e:
        print(f"保存回测结果失败: {e}")

if __name__ == "__main__":
    main()
