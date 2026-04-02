
import sys
import os
import requests
from bs4 import BeautifulSoup
import re

sys.path.append(os.getcwd())
from data.fetchers.screener_fetcher import resolve_screener_code, HEADERS, _parse_number, SCREENER_BASE_URL

def test_full_ratios():
    symbol = "ASIANPAINT.NS"
    code = resolve_screener_code(symbol)
    url = SCREENER_BASE_URL.format(code=code)
    response = requests.get(url, headers=HEADERS, timeout=20)
    soup = BeautifulSoup(response.text, "lxml")
    
    ratios = {}
    for item in soup.select("ul#top-ratios li"):
        name_tag = item.select_one("span.name")
        value_tag = item.select_one("span.number")
        if not name_tag or not value_tag:
            continue
        key = name_tag.get_text(" ", strip=True).lower()
        value = _parse_number(value_tag.get_text(" ", strip=True))
        print(f"DEBUG: Found ratio: '{key}' = {value}")
        if value is not None:
            ratios[key] = value
            
if __name__ == "__main__":
    test_full_ratios()
