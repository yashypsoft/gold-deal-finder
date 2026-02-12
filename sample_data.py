# sample_data.py
import json
from datetime import datetime, timedelta
import random
from pathlib import Path

def create_sample_scans(count=5):
    """Create sample scan data for testing"""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    sources = ['AJIO', 'Myntra']
    purities = ['24K', '22K', '18K']
    brands = ['Tanishq', 'Kalyan', 'Malabar', 'PC Jeweller', 'Senco']
    
    for i in range(count):
        scan_time = datetime.now() - timedelta(days=i*2, hours=random.randint(1, 12))
        timestamp = scan_time.strftime("%Y%m%d_%H%M%S")
        
        products = []
        for j in range(random.randint(50, 150)):
            weight = random.choice([1, 2, 5, 8, 10, 20, 50])
            purity = random.choice(purities)
            source = random.choice(sources)
            brand = random.choice(brands)
            
            base_price = random.randint(5500, 6500)
            selling_price = weight * base_price * random.uniform(0.85, 1.15)
            expected_price = weight * base_price * 1.1
            
            product = {
                'source': source,
                'title': f"{weight}g {purity} Gold {'Coin' if random.random() > 0.5 else 'Jewellery'} - {brand}",
                'description': f"Pure {purity} gold product",
                'weight_grams': weight,
                'purity': purity,
                'product_type': 'coin' if random.random() > 0.5 else 'jewellery',
                'is_jewellery': random.choice([True, False]),
                'selling_price': round(selling_price, 2),
                'expected_price': round(expected_price, 2),
                'discount_percent': round((expected_price - selling_price) / expected_price * 100, 2),
                'price_per_gram': round(selling_price / weight, 2),
                'url': f"https://www.{source.lower()}.com/product/{j}",
                'image_url': '',
                'brand': brand,
                'spot_price': round(base_price, 2),
                'making_charges_percent': random.choice([0, 8, 12, 15]),
                'gst_percent': 3,
                'timestamp': scan_time.isoformat()
            }
            products.append(product)
        
        scan_data = {
            'timestamp': scan_time.isoformat(),
            'total_products': len(products),
            'products': products
        }
        
        filename = data_dir / f"scan_results_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(scan_data, f, indent=2)
        
        print(f"✅ Created sample scan: {filename}")
    
    print(f"\n📊 Created {count} sample scan files in data/ directory")

if __name__ == "__main__":
    create_sample_scans(10)