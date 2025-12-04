import requests
import os

GROK_API_KEY = os.getenv("GROK_API_KEY")

def analyze_ratios(ratios):
    prompt = f"Interpret these financial ratios: {ratios}"
    r = requests.post(
        "https://api.grok.example/v1/generate",
        headers={"Authorization": f"Bearer {GROK_API_KEY}"},
        json={"prompt": prompt}
    )
    return r.json()
