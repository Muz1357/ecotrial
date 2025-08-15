import requests

url = "https://web-production-6010a.up.railway.app/plan_trip"
payload = {
    "start": "Colombo, Sri Lanka",
    "end": "Kandy, Sri Lanka"
}
headers = {
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)
print(response.status_code)
print(response.json())