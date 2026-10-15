import httpx
r = httpx.get("https://router.huggingface.co/v1/models")
for m in r.json()["data"]:
    print(m["id"])