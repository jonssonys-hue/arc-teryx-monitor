import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re

SITES = [
    {
        "name": "Bushtukah",
        "url": "https://bushtukah.com/search?gf_169380=Arcteryx&q=arc%27teryx&options%5Bprefix%5D=last",
        "type": "shopify"
    },
    {
        "name": "Trailhead Paddle Shack",
        "url": "https://www.trailheadpaddleshack.ca/search/arc%27teryx/",
        "type": "trailhead"
    }
]

DISCOUNT_THRESHOLD = 0.20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

ARCTERYX_KEYWORDS = ["arc'teryx", "arcteryx", "arc teryx"]

def is_arcteryx(text):
    if not text:
        return False
    return any(kw in text.lower() for kw in ARCTERYX_KEYWORDS)

def extract_price(text):
    if not text:
        return None
    text = text.replace(",", "")
    match = re.search(r'[\d]+\.[\d]{2}', text)
    if match:
        return float(match.group())
    return None

def scrape_trailhead(site):
    results = []
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(site["url"], timeout=20)
        print(f"  Trailhead status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  Trailhead blocked, trying alternative...")
            return results

        soup = BeautifulSoup(response.text, "lxml")
        products = soup.find_all("li", class_=re.compile(r"product"))
        print(f"  Found {len(products)} product elements")

        for product in products:
            try:
                name_tag = product.find(class_=re.compile(r"woocommerce-loop-product__title|product.*title", re.I))
                if not name_tag:
                    name_tag = product.find(["h2", "h3"])
                name = name_tag.get_text(strip=True) if name_tag else ""

                if not is_arcteryx(name):
                    continue

                price_block = product.find(class_=re.compile(r"price"))
                if not price_block:
                    continue

                original_tag = price_block.find("del")
                sale_tag = price_block.find("ins")

                if original_tag and sale_tag:
                    original_price = extract_price(original_tag.get_text())
                    sale_price = extract_price(sale_tag.get_text())
                else:
                    prices = re.findall(r'[\d]+\.[\d]{2}', price_block.get_text().replace(",", ""))
                    if len(prices) >= 2:
                        original_price = float(max(prices, key=float))
                        sale_price = float(min(prices, key=float))
                    else:
                        continue

                if original_price and sale_price and original_price > 0 and sale_price < original_price:
                    discount = (original_price - sale_price) / original_price
                    if discount >= DISCOUNT_THRESHOLD:
                        link_tag = product.find("a", href=True)
                        link = link_tag["href"] if link_tag else site["url"]
                        results.append({
                            "site": site["name"],
                            "name": name,
                            "original_price": original_price,
                            "sale_price": sale_price,
                            "discount_pct": round(discount * 100, 1),
                            "link": link
                        })
            except Exception:
                continue

    except Exception as e:
        print(f"  Error fetching {site['name']}: {e}")

    return results

def scrape_shopify(site):
    results = []
    try:
        response = requests.get(site["url"], headers=HEADERS, timeout=20)
        soup = BeautifulSoup(response.text, "lxml")

        products = soup.find_all(class_=re.compile(r"product-item|product-card|grid-item", re.I))
        print(f"  Found {len(products)} product elements")

        for product in products:
            try:
                name_tag = product.find(class_=re.compile(r"title|name", re.I))
                name = name_tag.get_text(strip=True) if name_tag else ""

                if not is_arcteryx(name):
                    continue

                compare_tag = product.find(class_=re.compile(r"compare|was|original|regular", re.I))
                sale_tag = product.find(class_=re.compile(r"sale|price", re.I))

                if compare_tag and sale_tag:
                    original_price = extract_price(compare_tag.get_text())
                    sale_price = extract_price(sale_tag.get_text())

                    if original_price and sale_price and original_price > sale_price:
                        discount = (original_price - sale_price) / original_price
                        if discount >= DISCOUNT_THRESHOLD:
                            link_tag = product.find("a", href=True)
                            link = "https://bushtukah.com" + link_tag["href"] if link_tag else site["url"]
                            results.append({
                                "site": site["name"],
                                "name": name,
                                "original_price": original_price,
                                "sale_price": sale_price,
                                "discount_pct": round(discount * 100, 1),
                                "link": link
                            })
            except Exception:
                continue

    except Exception as e:
        print(f"  Error fetching {site['name']}: {e}")

    return results

def get_discounted_products(site):
    if site["type"] == "trailhead":
        return scrape_trailhead(site)
    else:
        return scrape_shopify(site)

def main():
    all_deals = []
    for site in SITES:
        print(f"Checking {site['name']}...")
        deals = get_discounted_products(site)
        all_deals.extend(deals)
        print(f"  Found {len(deals)} deals")

    output = {
        "last_checked": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_deals": len(all_deals),
        "deals": all_deals
    }

    with open("deals.json", "w") as f:
        json.dump(output, f, indent=2)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Arc'teryx Deal Monitor</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
    h1 {{ color: #2c3e50; }}
    .meta {{ color: #888; margin-bottom: 30px; font-size: 14px; }}
    .deal {{ background: white; border-radius: 10px; padding: 18px; margin-bottom: 16px; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
    .deal h3 {{ margin: 0 0 8px 0; color: #2c3e50; }}
    .site {{ font-size: 12px; color: #888; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 1px; }}
    .price {{ font-size: 22px; color: #e74c3c; font-weight: bold; }}
    .original {{ text-decoration: line-through; color: #aaa; font-size: 15px; margin-left: 10px; }}
    .badge {{ display: inline-block; background: #e74c3c; color: white; padding: 3px 10px; border-radius: 20px; font-size: 13px; margin-left: 10px; font-weight: bold; }}
    .link {{ display: inline-block; margin-top: 10px; color: #3498db; font-size: 13px; text-decoration: none; }}
    .link:hover {{ text-decoration: underline; }}
    .no-deals {{ background: white; border-radius: 10px; padding: 30px; text-align: center; color: #888; font-style: italic; }}
  </style>
</head>
<body>
  <h1>🏔️ Arc'teryx Deal Monitor</h1>
  <div class="meta">Last checked: {output['last_checked']} &nbsp;·&nbsp; <strong>{output['total_deals']} deal(s)</strong> found with ≥20% off</div>
"""

    if all_deals:
        for deal in sorted(all_deals, key=lambda x: -x["discount_pct"]):
            html += f"""
  <div class="deal">
    <div class="site">{deal['site']}</div>
    <h3>{deal['name']}</h3>
    <span class="price">C${deal['sale_price']:.2f}</span>
    <span class="original">C${deal['original_price']:.2f}</span>
    <span class="badge">-{deal['discount_pct']}%</span>
    <br>
    <a class="link" href="{deal['link']}" target="_blank">View product →</a>
  </div>"""
    else:
        html += '<div class="no-deals">No deals found today with 20% or more off. Check back later!</div>'

    html += "\n</body>\n</html>"

    with open("index.html", "w") as f:
        f.write(html)

    print(f"\nDone! Found {len(all_deals)} deals total.")

if __name__ == "__main__":
    main()
