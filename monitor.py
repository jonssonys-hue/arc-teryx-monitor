import requests
from bs4 import BeautifulSoup
import json
import os
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

DISCOUNT_THRESHOLD = 0.20  # 20%

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def extract_price(text):
    """Extract numeric price from a string like C$94.99 or $189.99"""
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
        response = requests.get(site["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "lxml")

        # Trailhead uses WooCommerce-style product listings
        products = soup.find_all("li", class_=re.compile(r"product"))

        for product in products:
            try:
                # Product name
                name_tag = product.find(["h2", "h3", "a"], class_=re.compile(r"woocommerce-loop-product__title|product.*title|entry-title", re.I))
                if not name_tag:
                    name_tag = product.find("a", class_=re.compile(r"title|name", re.I))
                name = name_tag.get_text(strip=True) if name_tag else None

                # Prices
                price_block = product.find(class_=re.compile(r"price"))
                if not price_block:
                    continue

                price_text = price_block.get_text(separator=" ", strip=True)

                # Look for del (original) and ins (sale) tags
                original_tag = price_block.find("del")
                sale_tag = price_block.find("ins")

                if original_tag and sale_tag:
                    original_price = extract_price(original_tag.get_text())
                    sale_price = extract_price(sale_tag.get_text())
                elif original_tag:
                    original_price = extract_price(original_tag.get_text())
                    sale_price = extract_price(price_text.replace(original_tag.get_text(), ""))
                else:
                    # Try to find two prices in the text
                    prices = re.findall(r'[\d]+\.[\d]{2}', price_text.replace(",", ""))
                    if len(prices) >= 2:
                        original_price = float(max(prices, key=float))
                        sale_price = float(min(prices, key=float))
                    else:
                        continue

                if original_price and sale_price and original_price > 0 and sale_price < original_price:
                    discount = (original_price - sale_price) / original_price
                    if discount >= DISCOUNT_THRESHOLD:
                        # Get product link
                        link_tag = product.find("a", href=True)
                        link = link_tag["href"] if link_tag else site["url"]

                        results.append({
                            "site": site["name"],
                            "name": name or "Unknown Product",
                            "original_price": original_price,
                            "sale_price": sale_price,
                            "discount_pct": round(discount * 100, 1),
                            "link": link
                        })
            except Exception as e:
                continue

    except Exception as e:
        print(f"Error fetching {site['name']}: {e}")

    return results

def scrape_shopify(site):
    results = []
    try:
        # Use Shopify JSON API for more reliable data
        api_url = "https://bushtukah.com/search?q=arc%27teryx&view=json" 
        response = requests.get(site["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "lxml")

        products = soup.find_all(class_=re.compile(r"product-item|product-card|grid-item", re.I))

        for product in products:
            try:
                name_tag = product.find(class_=re.compile(r"title|name", re.I))
                name = name_tag.get_text(strip=True) if name_tag else None

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
                                "name": name or "Unknown Product",
                                "original_price": original_price,
                                "sale_price": sale_price,
                                "discount_pct": round(discount * 100, 1),
                                "link": link
                            })
            except Exception:
                continue

    except Exception as e:
        print(f"Error fetching {site['name']}: {e}")

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

    # Save results to JSON
    output = {
        "last_checked": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "total_deals": len(all_deals),
        "deals": all_deals
    }

    with open("deals.json", "w") as f:
        json.dump(output, f, indent=2)

    # Generate HTML dashboard
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
    .header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
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
