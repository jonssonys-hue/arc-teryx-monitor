import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

SITES = [
    {
        "name": "Bushtukah",
        "url": "https://bushtukah.com/search?gf_169380=Arcteryx&q=arc%27teryx&options%5Bprefix%5D=last"
    },
    {
        "name": "Trailhead Paddle Shack",
        "url": "https://www.trailheadpaddleshack.ca/search/arc%27teryx/"
    }
]

DISCOUNT_THRESHOLD = 0.20  # 20%

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_discounted_products(site):
    results = []
    try:
        response = requests.get(site["url"], headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "lxml")

        # Look for products with both original and sale prices
        products = soup.find_all(class_=lambda c: c and any(
            x in c for x in ["product", "item", "card"]
        ))

        for product in products:
            try:
                name_tag = product.find(["h2", "h3", "h4", "a"], class_=lambda c: c and "title" in str(c).lower())
                name = name_tag.get_text(strip=True) if name_tag else None

                # Look for sale/compare price
                compare_tag = product.find(class_=lambda c: c and any(
                    x in str(c).lower() for x in ["compare", "original", "was", "regular"]
                ))
                sale_tag = product.find(class_=lambda c: c and any(
                    x in str(c).lower() for x in ["sale", "price", "discounted"]
                ))

                if name and compare_tag and sale_tag:
                    compare_text = compare_tag.get_text(strip=True).replace("$", "").replace(",", "").strip()
                    sale_text = sale_tag.get_text(strip=True).replace("$", "").replace(",", "").strip()

                    try:
                        compare_price = float(''.join(filter(lambda x: x.isdigit() or x == '.', compare_text)))
                        sale_price = float(''.join(filter(lambda x: x.isdigit() or x == '.', sale_text)))

                        if compare_price > 0 and sale_price < compare_price:
                            discount = (compare_price - sale_price) / compare_price
                            if discount >= DISCOUNT_THRESHOLD:
                                results.append({
                                    "site": site["name"],
                                    "name": name,
                                    "original_price": compare_price,
                                    "sale_price": sale_price,
                                    "discount_pct": round(discount * 100, 1)
                                })
                    except (ValueError, ZeroDivisionError):
                        pass
            except Exception:
                pass

    except Exception as e:
        print(f"Error fetching {site['name']}: {e}")

    return results

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

    # Generate simple HTML dashboard
    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Arc'teryx Deal Monitor</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #2c3e50; }}
    .meta {{ color: #888; margin-bottom: 30px; }}
    .deal {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
    .deal h3 {{ margin: 0 0 8px 0; color: #2c3e50; }}
    .site {{ font-size: 12px; color: #888; margin-bottom: 4px; }}
    .price {{ font-size: 18px; color: #e74c3c; font-weight: bold; }}
    .original {{ text-decoration: line-through; color: #aaa; font-size: 14px; margin-left: 8px; }}
    .badge {{ display: inline-block; background: #e74c3c; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; margin-left: 8px; }}
    .no-deals {{ color: #888; font-style: italic; }}
  </style>
</head>
<body>
  <h1>🏔️ Arc'teryx Deal Monitor</h1>
  <div class="meta">Last checked: {output['last_checked']} &nbsp;|&nbsp; {output['total_deals']} deal(s) found (≥20% off)</div>
"""

    if all_deals:
        for deal in sorted(all_deals, key=lambda x: -x["discount_pct"]):
            html += f"""
  <div class="deal">
    <div class="site">{deal['site']}</div>
    <h3>{deal['name']}</h3>
    <span class="price">${deal['sale_price']:.2f}</span>
    <span class="original">${deal['original_price']:.2f}</span>
    <span class="badge">-{deal['discount_pct']}%</span>
  </div>"""
    else:
        html += '<p class="no-deals">No deals found today with 20% or more off.</p>'

    html += "\n</body>\n</html>"

    with open("index.html", "w") as f:
        f.write(html)

    print(f"\nDone! Found {len(all_deals)} deals total.")

if __name__ == "__main__":
    main()
