#!/usr/bin/env python3
"""
USDA FoodData Central JSON Cleaner & Minimizer
Cleans raw USDA JSON and extracts only essential data for embeddings pipeline
"""

import json
import sys
from typing import Dict, List, Optional, Any

# USDA Nutrient ID mappings
NUTRIENT_IDS = {
    'ENERGY_KCAL': 1008,    # Energy (kcal)
    'PROTEIN': 1003,        # Protein (g)
    'FAT': 1004,           # Total lipid (fat) (g)
    'CARBS': 1005,         # Carbohydrate, by difference (g)
    'FIBER': 1079,         # Fiber, total dietary (g)
    'SUGAR': 1063,         # Sugars, Total (g)
    'SODIUM': 1093,        # Sodium, Na (mg)
    'CALCIUM': 1087,       # Calcium, Ca (mg)
    'IRON': 1089,          # Iron, Fe (mg)
    'POTASSIUM': 1092,     # Potassium, K (mg)
    'VITAMIN_C': 1162,     # Vitamin C (mg)
    'SATURATED_FAT': 1258, # Saturated fat (g)
}

def get_nutrient(nutrients: List[Dict], nutrient_id: int) -> float:
    """Extract nutrient amount by ID"""
    if not nutrients:
        return 0.0
    
    for nutrient in nutrients:
        if nutrient.get('nutrient', {}).get('id') == nutrient_id:
            amount = nutrient.get('amount', 0)
            return float(amount) if amount is not None else 0.0
    return 0.0

def extract_brand(name: str) -> Optional[str]:
    """Extract brand from food name if present"""
    name_upper = name.upper()
    brands = ['PILLSBURY', 'SABRA', 'TRIBE', 'KELLOGG', 'GENERAL MILLS', 'KRAFT', 'PEPSI', 'COCA COLA', 'MCDONALD', 'BURGER KING', 'SUBWAY']
    
    for brand in brands:
        if brand in name_upper:
            return brand.title()
    return None

def create_embedding_text(food: Dict) -> str:
    """Create searchable text for embedding generation - avoid exact numbers"""
    parts = [
        food['name'].lower(),
        food['category'].lower()
    ]
    
    # Use categorical ranges instead of exact numbers
    calories = food['calories_per_100g']
    if calories <= 50:
        parts.append('very low calorie')
    elif calories <= 100:
        parts.append('low calorie')
    elif calories <= 200:
        parts.append('moderate calorie')
    elif calories <= 400:
        parts.append('high calorie')
    else:
        parts.append('very high calorie')
    
    # Protein categories
    protein = food['protein_per_100g']
    if protein >= 20:
        parts.append('very high protein')
    elif protein >= 15:
        parts.append('high protein')
    elif protein >= 10:
        parts.append('moderate protein')
    elif protein >= 5:
        parts.append('some protein')
    else:
        parts.append('low protein')
    
    # Fat categories
    fat = food['fat_per_100g']
    if fat <= 3:
        parts.append('low fat')
    elif fat <= 10:
        parts.append('moderate fat')
    else:
        parts.append('high fat')
    
    # Carb categories
    carbs = food['carbs_per_100g']
    if carbs <= 5:
        parts.append('very low carb keto friendly')
    elif carbs <= 20:
        parts.append('low carb')
    elif carbs <= 45:
        parts.append('moderate carb')
    else:
        parts.append('high carb')
    
    # Fiber
    if food['fiber_per_100g'] >= 10:
        parts.append('very high fiber')
    elif food['fiber_per_100g'] >= 5:
        parts.append('high fiber')
    
    # Sugar
    if food['sugar_per_100g'] >= 15:
        parts.append('high sugar sweet')
    elif food['sugar_per_100g'] <= 2:
        parts.append('sugar free')
    
    # Sodium
    if food['sodium_per_100g'] >= 600:
        parts.append('high sodium salty')
    elif food['sodium_per_100g'] <= 140:
        parts.append('low sodium')
    
    # Add common search terms based on nutritional profile
    if protein >= 15 and calories <= 200:
        parts.append('lean protein snack')
    if fat >= 15 and carbs <= 10:
        parts.append('ketogenic food')
    if food['fiber_per_100g'] >= 5 and calories <= 150:
        parts.append('filling low calorie')
        
    return ' '.join(parts)

def clean_food_data(raw_food: Dict) -> Optional[Dict]:
    """Clean and minimize USDA food data"""
    
    # Validate required fields
    if not raw_food.get('description'):
        return None
    
    nutrients = raw_food.get('foodNutrients', [])
    if not nutrients:
        return None
    
    # Extract basic info
    external_id = str(raw_food.get('fdcId', ''))
    name = raw_food['description'].strip()
    category = raw_food.get('foodCategory', {}).get('description', 'Unknown')
    
    # Extract key nutrients per 100g
    calories = get_nutrient(nutrients, NUTRIENT_IDS['ENERGY_KCAL'])
    protein = get_nutrient(nutrients, NUTRIENT_IDS['PROTEIN'])
    fat = get_nutrient(nutrients, NUTRIENT_IDS['FAT'])
    carbs = get_nutrient(nutrients, NUTRIENT_IDS['CARBS'])
    fiber = get_nutrient(nutrients, NUTRIENT_IDS['FIBER'])
    
    # Handle sugar ID variations (SR Legacy might use different ID)
    sugar = get_nutrient(nutrients, NUTRIENT_IDS['SUGAR'])
    if sugar == 0:
        # Try alternative sugar ID (Total Sugars in SR Legacy)
        sugar = get_nutrient(nutrients, 2000)
    
    sodium = get_nutrient(nutrients, NUTRIENT_IDS['SODIUM'])
    
    # Skip foods with missing critical data
    if not name or calories == 0:
        return None
    
    # Create clean food object
    clean_food = {
        'external_id': external_id,
        'name': name,
        'description': name,
        'brand': extract_brand(name),
        'category': category,
        'calories_per_100g': round(calories, 2),
        'protein_per_100g': round(protein, 2),
        'fat_per_100g': round(fat, 2),
        'carbs_per_100g': round(carbs, 2),
        'fiber_per_100g': round(fiber, 2),
        'sugar_per_100g': round(sugar, 2),
        'sodium_per_100g': round(sodium, 2),
        'data_source': 'usda',
        'nutrients': {
            'calcium_mg': round(get_nutrient(nutrients, NUTRIENT_IDS['CALCIUM']), 2),
            'iron_mg': round(get_nutrient(nutrients, NUTRIENT_IDS['IRON']), 2),
            'potassium_mg': round(get_nutrient(nutrients, NUTRIENT_IDS['POTASSIUM']), 2),
            'vitamin_c_mg': round(get_nutrient(nutrients, NUTRIENT_IDS['VITAMIN_C']), 2),
            'saturated_fat_g': round(get_nutrient(nutrients, NUTRIENT_IDS['SATURATED_FAT']), 2)
        }
    }
    
    # Add embedding text
    clean_food['embedding_text'] = create_embedding_text(clean_food)
    
    return clean_food

def process_usda_json(input_file: str, output_file: str, limit: Optional[int] = None):
    """Process USDA JSON file and output cleaned data"""
    
    print(f"Reading {input_file}...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Handle different USDA JSON structures
    foods = []
    if isinstance(data, dict):
        if 'FoundationFoods' in data:
            foods = data['FoundationFoods']
        elif 'SRLegacyFoods' in data:
            foods = data['SRLegacyFoods']
        elif 'foods' in data:
            foods = data['foods']
        else:
            # Single food object
            foods = [data]
    elif isinstance(data, list):
        foods = data
    
    print(f"Found {len(foods)} foods in input")
    
    # Clean foods
    cleaned_foods = []
    skipped = 0
    
    for i, food in enumerate(foods):
        if limit and len(cleaned_foods) >= limit:
            break
            
        clean_food = clean_food_data(food)
        if clean_food:
            cleaned_foods.append(clean_food)
        else:
            skipped += 1
        
        # Progress indicator
        if (i + 1) % 1000 == 0:
            print(f"Processed {i + 1}/{len(foods)} foods, cleaned: {len(cleaned_foods)}, skipped: {skipped}")
    
    print(f"Cleaning complete: {len(cleaned_foods)} foods cleaned, {skipped} skipped")
    
    # Save cleaned data
    output_data = {
        'metadata': {
            'total_foods': len(cleaned_foods),
            'source': 'usda_fooddata_central',
            'cleaned_by': 'usda_json_cleaner.py'
        },
        'foods': cleaned_foods
    }
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Saved cleaned data to {output_file}")
        
    except Exception as e:
        print(f"Error writing output file: {e}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python usda_cleaner.py <input_json> <output_json> [limit]")
        print("Example: python usda_cleaner.py foundation_foods.json cleaned_foods.json 10000")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    process_usda_json(input_file, output_file, limit)

if __name__ == "__main__":
    main()