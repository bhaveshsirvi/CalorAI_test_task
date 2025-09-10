#!/usr/bin/env python3
"""
Upload cleaned food data to Supabase
Tracks progress and avoids unnecessary embedding generation for existing foods
"""
import json
import os
import sys
from typing import List, Dict, Optional, Set
import openai
from supabase import create_client, Client
import time
from tqdm import tqdm
from dotenv import load_dotenv
import tiktoken

# Load environment variables
load_dotenv()

# Configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Progress tracking
PROGRESS_FILE = 'upload_progress.json'

def setup_clients() -> tuple[Client, openai.OpenAI]:
    """Initialize Supabase and OpenAI clients"""
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY]):
        print("Missing environment variables. Please set:")
        print("- SUPABASE_URL")
        print("- SUPABASE_SERVICE_KEY") 
        print("- OPENAI_API_KEY")
        sys.exit(1)
    
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    return supabase, openai_client

def load_progress() -> Dict:
    """Load upload progress from file"""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load progress file: {e}")
    
    return {
        'uploaded_ids': [],
        'last_batch': 0,
        'total_uploaded': 0
    }

def save_progress(progress: Dict):
    """Save upload progress to file"""
    try:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save progress: {e}")

def get_existing_food_ids(supabase: Client) -> Set[str]:
    """Get all existing external_ids from database"""
    print("Checking existing foods in database...")
    
    try:
        all_ids = set()
        page_size = 1000
        offset = 0
        
        while True:
            result = supabase.table('foods')\
                .select('external_id')\
                .range(offset, offset + page_size - 1)\
                .execute()
            
            if not result.data:
                break
                
            batch_ids = {row['external_id'] for row in result.data}
            all_ids.update(batch_ids)
            
            if len(result.data) < page_size:
                break
                
            offset += page_size
            
        print(f"Found {len(all_ids)} existing foods in database")
        return all_ids
        
    except Exception as e:
        print(f"Error fetching existing foods: {e}")
        return set()

def calculate_embedding_cost(texts: List[str]) -> tuple[int, float]:
    """Calculate accurate token count and cost for embeddings using tiktoken"""
    try:
        encoding = tiktoken.encoding_for_model("text-embedding-ada-002")
        
        total_tokens = 0
        for text in texts:
            tokens = encoding.encode(text)
            total_tokens += len(tokens)
        
        # text-embedding-ada-002 batch pricing: $0.00005 per 1K tokens
        cost = (total_tokens * 0.00005) / 1000
        
        return total_tokens, cost
        
    except Exception as e:
        print(f"Warning: Could not calculate exact tokens, using estimate: {e}")
        total_tokens = sum(len(text.split()) * 1.3 for text in texts)  
        cost = (total_tokens * 0.0001) / 1000
        return int(total_tokens), cost

def generate_embeddings(texts: List[str], openai_client: openai.OpenAI) -> List[List[float]]:
    """Generate embeddings for a batch of texts with retry logic"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            response = openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
            
        except Exception as e:
            print(f"Embedding generation attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt) 
            else:
                raise e

def filter_new_foods(foods: List[Dict], existing_ids: Set[str], progress: Dict) -> List[Dict]:
    """Filter out foods that already exist or have been uploaded"""
    uploaded_ids = set(progress.get('uploaded_ids', []))
    
    new_foods = []
    for food in foods:
        external_id = food['external_id']
        if external_id not in existing_ids and external_id not in uploaded_ids:
            new_foods.append(food)
    
    skipped_existing = len(foods) - len(new_foods) - len(uploaded_ids)
    skipped_progress = len(uploaded_ids)
    
    print(f"Foods analysis:")
    print(f"  Total foods: {len(foods)}")
    print(f"  Already in DB: {skipped_existing}")
    print(f"  Previously uploaded: {skipped_progress}")
    print(f"  New to upload: {len(new_foods)}")
    
    return new_foods

def batch_upload_foods(foods: List[Dict], supabase: Client, openai_client: openai.OpenAI, 
                      batch_size: int = 50) -> int:
    """Upload foods in batches with progress tracking"""
    
    if not foods:
        print("No new foods to upload")
        return 0
    
    # Load existing progress
    progress = load_progress()
    start_batch = progress.get('last_batch', 0)
    uploaded_count = progress.get('total_uploaded', 0)
    
    total_batches = (len(foods) + batch_size - 1) // batch_size
    
    # Calculate embedding cost estimate with tiktoken
    embedding_texts = [food['embedding_text'] for food in foods]
    total_tokens, estimated_cost = calculate_embedding_cost(embedding_texts)
    print(f"Total tokens: {total_tokens:,}")
    print(f"Estimated embedding cost: ${estimated_cost:.6f}")
    
    with tqdm(total=len(foods), initial=start_batch * batch_size, 
              desc="Uploading foods") as pbar:
        
        for i in range(start_batch, total_batches):
            batch_start = i * batch_size
            batch_end = min(batch_start + batch_size, len(foods))
            batch = foods[batch_start:batch_end]
            
            try:
                # Generate embeddings for batch
                embedding_texts = [food['embedding_text'] for food in batch]
                embeddings = generate_embeddings(embedding_texts, openai_client)
                
                if len(embeddings) != len(batch):
                    print(f"Warning: Embedding count mismatch for batch {i + 1}")
                    continue
                
                # Prepare upload data
                upload_data = []
                batch_ids = []
                
                for j, food in enumerate(batch):
                    upload_row = {
                        'external_id': food['external_id'],
                        'name': food['name'],
                        'description': food['description'],
                        'category': food['category'],
                        'calories_per_100g': food['calories_per_100g'],
                        'protein_per_100g': food['protein_per_100g'],
                        'fat_per_100g': food['fat_per_100g'],
                        'carbs_per_100g': food['carbs_per_100g'],
                        'fiber_per_100g': food['fiber_per_100g'],
                        'sugar_per_100g': food['sugar_per_100g'],
                        'sodium_per_100g': food['sodium_per_100g'],
                        'calcium_mg': food['nutrients']['calcium_mg'],
                        'iron_mg': food['nutrients']['iron_mg'],
                        'potassium_mg': food['nutrients']['potassium_mg'],
                        'vitamin_c_mg': food['nutrients']['vitamin_c_mg'],
                        'saturated_fat_g': food['nutrients']['saturated_fat_g'],
                        'data_source': food['data_source'],
                        'embedding_text': food['embedding_text'],
                        'embedding': embeddings[j]
                    }
                    upload_data.append(upload_row)
                    batch_ids.append(food['external_id'])
                
                # Upload batch
                result = supabase.table('foods').upsert(
                    upload_data, 
                    on_conflict='external_id'
                ).execute()
                
                # Update progress
                uploaded_count += len(batch)
                progress['uploaded_ids'].extend(batch_ids)
                progress['last_batch'] = i + 1
                progress['total_uploaded'] = uploaded_count
                save_progress(progress)
                
                pbar.update(len(batch))
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error uploading batch {i + 1}: {e}")
                print(f"Progress saved. Resume with same command.")
                return uploaded_count
    
    # Clean up progress file on successful completion
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        print("Upload completed successfully. Progress file cleaned up.")
    
    return uploaded_count

def load_cleaned_data(file_path: str) -> List[Dict]:
    """Load cleaned food data from JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'foods' in data:
            return data['foods']
        elif isinstance(data, list):
            return data
        else:
            print("Unknown data format")
            return []
            
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_foods.py <cleaned_foods.json> [--limit N]")
        print("Environment variables required:")
        print("- SUPABASE_URL") 
        print("- SUPABASE_SERVICE_KEY")
        print("- OPENAI_API_KEY")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Parse optional limit
    limit = None
    if '--limit' in sys.argv:
        try:
            limit_idx = sys.argv.index('--limit') + 1
            limit = int(sys.argv[limit_idx])
        except (ValueError, IndexError):
            print("Invalid limit value")
            sys.exit(1)
    
    # Setup
    supabase, openai_client = setup_clients()
    
    # Load data
    print(f"Loading data from {input_file}...")
    all_foods = load_cleaned_data(input_file)
    
    if not all_foods:
        print("No foods found in input file")
        sys.exit(1)
    
    # Apply limit if specified
    if limit:
        all_foods = all_foods[:limit]
        print(f"Limited to {len(all_foods)} foods")
    
    # Get existing foods and filter new ones
    existing_ids = get_existing_food_ids(supabase)
    progress = load_progress()
    new_foods = filter_new_foods(all_foods, existing_ids, progress)
    
    if not new_foods:
        print("All foods already exist in database!")
        return
    
    # Confirm upload
    print(f"\nReady to upload {len(new_foods)} new foods")
    if not progress.get('last_batch', 0):  # Fresh start
        confirm = input("Continue? (y/n): ")
        if confirm.lower() != 'y':
            print("Upload cancelled")
            sys.exit(0)
    else:
        print(f"Resuming from batch {progress['last_batch']}")
    
    # Upload
    uploaded = batch_upload_foods(new_foods, supabase, openai_client)
    
    # Final status
    total_in_db = len(existing_ids) + uploaded
    print(f"\nUpload complete!")
    print(f"Newly uploaded: {uploaded}")
    print(f"Total foods in database: {total_in_db}")

if __name__ == "__main__":
    main()