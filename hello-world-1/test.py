import requests

def upbit_trade(request):
    try:
        response = requests.get('https://asia-northeast3-chatgpt-study-426900.cloudfunctions.net/function-hello-world')
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        return f"외부 IP 주소를 가져오는 중 오류 발생: {e}"