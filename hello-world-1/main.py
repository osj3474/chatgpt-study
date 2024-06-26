import functions_framework
import jwt
import hashlib
import os
import uuid
from urllib.parse import urlencode, unquote
import requests
import json

access_key = os.environ['UPBIT_OPEN_API_ACCESS_KEY']
secret_key = os.environ['UPBIT_OPEN_API_SECRET_KEY']
server_url = os.environ['UPBIT_OPEN_API_SERVER_URL']

chatgpt_key = os.environ['CHATGPT_KEY']

@functions_framework.http
def upbit_trade(request):
    params = request.get_json()
    ticker = params['ticker']
    volume = params['volume']
    price = params['price']

    # 자산 보유 여부로 포지션 설정
    myPosition, myPrice, myAmount, myBalance = getPositionAndPriceAndBalance(ticker)

    # content for chatgpt
    info = getCurrentInfo(ticker)
    oneMinute = getCurrentMinutesCandle(ticker, 1)
    tenMinute = getCurrentMinutesCandle(ticker, 10)
    orderInfo = getCurrentOrderInfo(ticker)
    content = f'''The average price of the {ticker} I bought is {myPrice} and holding quantity is {myAmount}. My remaining balance is {myBalance}. {ticker} info is {info}. And 1 minute candle information is {oneMinute}. And 10 minute candle information is {tenMinute}. The current asking price information is {orderInfo}.'''
    
    buyAble = "가능" if myBalance>price else "불가능:잔고부족"
    sellAble = "가능" if myAmount>volume else "불가능:판매수량부족"
    
    # chatgpt api
    result = getChatGptConsulting(content, ticker)

    print(f'''============= 현재 상태 =============
    거래티커 : {ticker}
    보유수량 : {myAmount}
    잔고     : {myBalance}
    상태     : 매수({buyAble}), 매도({sellAble})
    요청질문 : {content}
    응답     : {result}
====================================''')

    if 'BBUUYY' in result and myBalance>price:
        print("✅ BUY")
        rs = buy(ticker, price)
        print(rs)
    elif 'SSEELLLL' in result and myAmount>volume:
        print("🚨 SELL")
        rs = sell(ticker, volume)
        print(rs)
    elif 'HHOOLLDD' in result:
        print("🅿️ HOLD")
    else:
        print("❌ No action")
    print("")
    return result
    
def getPositionAndPriceAndBalance(ticker):
    myAccount = getMyAccount()
    myPrice = 0
    myAmount = 0
    exists = 'off'
    for item in myAccount:
        if item['currency'] == ticker:
            exists = 'on'
            myPrice = int(float(item['avg_buy_price']))   # 평단가
            myAmount = int(float(item['balance']))        # 보유 수량
        if item['currency'] == 'KRW':
            myBalance = int(float(item['balance']))       # 현재 잔고
            
    return exists, myPrice, myAmount, myBalance

def getMyAccount():
    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
    }

    jwt_token = jwt.encode(payload, secret_key)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization,
    }

    res = requests.get(server_url + '/v1/accounts', headers=headers)
    return res.json()

def getCurrentInfo(ticker):
    response = requests.get(f'https://api.upbit.com/v1/ticker?markets=KRW-{ticker}')
    data = json.loads(response.text)

    return {
        'opening_price': data[0]['opening_price'],
        'high_price': data[0]['high_price'],
        'low_price': data[0]['low_price'],
        'trade_price': data[0]['trade_price'],
        'prev_closing_price': data[0]['prev_closing_price'],
        'change': data[0]['change'],
        'change_price': data[0]['change_price'],
        'change_rate': data[0]['change_rate'],
        'signed_change_price': data[0]['signed_change_price'],
        'signed_change_rate': data[0]['signed_change_rate'],
        'trade_volume': data[0]['trade_volume'],
        'acc_trade_price': data[0]['acc_trade_price'],
        'acc_trade_price_24h': data[0]['acc_trade_price_24h'],
        'acc_trade_volume': data[0]['acc_trade_volume'],
        'acc_trade_volume_24h': data[0]['acc_trade_volume_24h'],
        'highest_52_week_price': data[0]['highest_52_week_price'],
        'highest_52_week_date': data[0]['highest_52_week_date'],
        'lowest_52_week_price': data[0]['lowest_52_week_price'],
        'lowest_52_week_date': data[0]['lowest_52_week_date'],
        'timestamp': data[0]['timestamp']
    }

def getCurrentMinutesCandle(ticker, minute):
    response = requests.get(f'https://api.upbit.com/v1/candles/minutes/{minute}?market=KRW-{ticker}&count=10')
    return response.text

def getCurrentOrderInfo(ticker):
    # 요청할 데이터 설정
    ASKING_PRICE_URL = f"https://api.upbit.com/v1/orderbook?markets=KRW-{ticker}&level=10"
    response = requests.get(ASKING_PRICE_URL)
    return response.text

def getChatGptConsulting(content, ticker):
    # API 엔드포인트와 헤더 설정
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {chatgpt_key}'
    }

    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
        {
            "role": "system",
            "content": f"Let's assume you're a {ticker} scalping trading expert. Your transactions take place every 30 minutes. Please answer based on the information about {ticker} whether you want to buy, sell, or hold. Please summarize the reason and tell me together. Please put the word 'BBUUYY' if you are going to buy it, 'SSEELLLL' if you are going to sell it, and 'HHOOLLDD' if you are going to have it on the first line."
        },
        {
            "role": "user",
            "content": content
        }
        ],
        "max_tokens": 2000,
        "temperature": 0
    }

    # requests 모듈을 사용하여 POST 요청 보내기
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    return result['choices'][0]['message']['content']


def buy(ticker, price):
    params = {
        'market': f'KRW-{ticker}',
        'side': 'bid',
        'ord_type': 'price',
        'price': price
    }
    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }

    jwt_token = jwt.encode(payload, secret_key)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization,
    }

    res = requests.post(server_url + '/v1/orders', json=params, headers=headers)
    return res.json()

def sell(ticker, volume):
    params = {
        'market': f'KRW-{ticker}',
        'side': 'ask',
        'ord_type': 'market',
        'volume': volume
    }
    query_string = unquote(urlencode(params, doseq=True)).encode("utf-8")

    m = hashlib.sha512()
    m.update(query_string)
    query_hash = m.hexdigest()

    payload = {
        'access_key': access_key,
        'nonce': str(uuid.uuid4()),
        'query_hash': query_hash,
        'query_hash_alg': 'SHA512',
    }

    jwt_token = jwt.encode(payload, secret_key)
    authorization = 'Bearer {}'.format(jwt_token)
    headers = {
    'Authorization': authorization,
    }

    res = requests.post(server_url + '/v1/orders', json=params, headers=headers)
    return res.json()