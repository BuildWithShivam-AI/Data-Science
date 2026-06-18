import requests
import json
import time
import socket
import traceback

# =========================
# CONFIGURATION
# =========================

industry_id = "6038"
station_id = "Station_13275"

token = "MTIwMzIwMjZfbWFnX2Zsb3dfc3lzdGVtX3NfaW5jXzEzMDE1OA=="

url = f"http://dpcccems.nic.in/dlcpcb-api/api/industry/{industry_id}/station/{station_id}/data"

headers = {
    "Authorization": f"Basic {token}",
    "Content-Type": "application/json"
}

payload = [
    {
        "deviceId": "MG2511FM_E2",
        "params": [
            {
                "parameter": "flow, flow totalizer",
                "value": "0",
                "unit": "Lit",
                "timestamp": str(int(time.time() * 1000)),
                "flag": "U"
            }
        ]
    }
]

# =========================
# DEBUG INFORMATION
# =========================

print("\n========== REQUEST ==========")
print("URL:")
print(url)

print("\nHeaders:")
print(json.dumps(headers, indent=4))

print("\nPayload:")
print(json.dumps(payload, indent=4))
print("=============================\n")

# =========================
# DNS TEST
# =========================

try:
    print("Checking DNS Resolution...")
    ip = socket.gethostbyname("dpccocems.nic.in")
    print("Resolved IP:", ip)
except Exception as dns_error:
    print("\nDNS ERROR")
    print(type(dns_error).__name__)
    print(str(dns_error))

# =========================
# API CALL
# =========================

try:

    response = requests.post(
        url=url,
        headers=headers,
        json=payload,
        timeout=30
    )

    print("\n========== RESPONSE ==========")
    print("Status Code:", response.status_code)
    print("Reason:", response.reason)

    print("\nResponse Headers:")
    print(dict(response.headers))

    print("\nResponse Body:")
    print(response.text)

    try:
        print("\nResponse JSON:")
        print(json.dumps(response.json(), indent=4))
    except:
        pass

    print("==============================")

except requests.exceptions.ConnectionError as e:

    print("\nCONNECTION ERROR")
    print(type(e).__name__)
    print(str(e))

except requests.exceptions.Timeout as e:

    print("\nTIMEOUT ERROR")
    print(type(e).__name__)
    print(str(e))

except requests.exceptions.HTTPError as e:

    print("\nHTTP ERROR")
    print(type(e).__name__)
    print(str(e))

except requests.exceptions.RequestException as e:

    print("\nREQUEST ERROR")
    print(type(e).__name__)
    print(str(e))

except Exception as e:

    print("\nUNEXPECTED ERROR")
    print(type(e).__name__)
    print(str(e))

    print("\nFULL TRACEBACK")
    traceback.print_exc()