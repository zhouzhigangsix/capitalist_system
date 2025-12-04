import requests
import json
import time

BASE_URL = "http://localhost:8080"

def test_api(endpoint, params=None):
    url = f"{BASE_URL}{endpoint}"
    try:
        print(f"Testing {url} with params {params}...")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Success! Response code: {data.get('code')}")
        if data.get('code') != 0:
            print(f"❌ Error message: {data.get('message')}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    # 等待服务完全启动
    print("Waiting for service to be ready...")
    time.sleep(2)
    
    # 1. 测试健康检查
    test_api("/api/health")
    
    # 2. 测试获取行情 (平安银行)
    test_api("/api/quote", {"code": "000001"})
    
    # 3. 测试搜索
    test_api("/api/search", {"keyword": "平安"})
    
    # 4. 测试K线数据
    test_api("/api/kline", {"code": "000001", "type": "day"})

if __name__ == "__main__":
    main()
