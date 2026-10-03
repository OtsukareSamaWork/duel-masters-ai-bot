import urllib.request
import json
import urllib.error

with open("crash_dump.json", "r") as f:
    data = json.load(f)


req = urllib.request.Request(
    'http://127.0.0.1:5000/api/analyze',
    data=json.dumps(data).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    res = urllib.request.urlopen(req)
    print("SUCCESS")
    print(res.read().decode())
except urllib.error.HTTPError as e:
    print("ERROR:", e.code)
    print(e.read().decode())
