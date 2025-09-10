-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create foods table with metadata and embeddings
CREATE TABLE foods (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  external_id TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  calories_per_100g DECIMAL(7,2) NOT NULL,
  protein_per_100g DECIMAL(7,2) NOT NULL,
  fat_per_100g DECIMAL(7,2) NOT NULL,
  carbs_per_100g DECIMAL(7,2) NOT NULL,
  fiber_per_100g DECIMAL(7,2) NOT NULL,
  sugar_per_100g DECIMAL(7,2) NOT NULL,
  sodium_per_100g DECIMAL(7,2) NOT NULL,
  calcium_mg DECIMAL(7,2),
  iron_mg DECIMAL(7,2),
  potassium_mg DECIMAL(7,2),
  vitamin_c_mg DECIMAL(7,2),
  saturated_fat_g DECIMAL(7,2),
  data_source TEXT NOT NULL DEFAULT 'usda',
  embedding_text TEXT NOT NULL,
  embedding VECTOR(1536), -- OpenAI ada-002 dimensions
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_foods_category ON foods (category);
CREATE INDEX idx_foods_calories ON foods (calories_per_100g);
CREATE INDEX idx_foods_protein ON foods (protein_per_100g);
CREATE INDEX idx_foods_external_id ON foods (external_id);

-- Add unique constraint to prevent duplicates
ALTER TABLE foods ADD CONSTRAINT unique_external_id UNIQUE (external_id);

-- Create vector similarity index (HNSW for better performance)
CREATE INDEX idx_foods_embedding ON foods 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Updated search RPC function with missing parameters
CREATE OR REPLACE FUNCTION search_foods(
  query_embedding VECTOR(1536),
  match_threshold FLOAT DEFAULT 0.78,
  match_count INT DEFAULT 20,
  min_calories DECIMAL DEFAULT NULL,
  max_calories DECIMAL DEFAULT NULL,
  min_protein DECIMAL DEFAULT NULL,
  max_protein DECIMAL DEFAULT NULL,
  min_carbs DECIMAL DEFAULT NULL,
  max_carbs DECIMAL DEFAULT NULL,
  min_fat DECIMAL DEFAULT NULL,
  max_fat DECIMAL DEFAULT NULL,
  max_sugar DECIMAL DEFAULT NULL,
  min_sodium DECIMAL DEFAULT NULL,
  max_sodium DECIMAL DEFAULT NULL,
  food_category TEXT DEFAULT NULL
)
RETURNS TABLE (
  id UUID,
  name TEXT,
  category TEXT,
  calories_per_100g DECIMAL(7,2),
  protein_per_100g DECIMAL(7,2),
  fat_per_100g DECIMAL(7,2),
  carbs_per_100g DECIMAL(7,2),
  fiber_per_100g DECIMAL(7,2),
  sugar_per_100g DECIMAL(7,2),
  sodium_per_100g DECIMAL(7,2),
  calcium_mg DECIMAL(7,2),
  iron_mg DECIMAL(7,2),
  potassium_mg DECIMAL(7,2),
  vitamin_c_mg DECIMAL(7,2),
  saturated_fat_g DECIMAL(7,2),
  similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    f.id,
    f.name,
    f.category,
    f.calories_per_100g,
    f.protein_per_100g,
    f.fat_per_100g,
    f.carbs_per_100g,
    f.fiber_per_100g,
    f.sugar_per_100g,
    f.sodium_per_100g,
    f.calcium_mg,
    f.iron_mg,
    f.potassium_mg,
    f.vitamin_c_mg,
    f.saturated_fat_g,
    (1 - (f.embedding <=> query_embedding)) as similarity
  FROM foods f
  WHERE (f.embedding <=> query_embedding) < (1 - match_threshold)
    AND (min_calories IS NULL OR f.calories_per_100g >= min_calories)
    AND (max_calories IS NULL OR f.calories_per_100g <= max_calories)
    AND (min_protein IS NULL OR f.protein_per_100g >= min_protein)
    AND (max_protein IS NULL OR f.protein_per_100g <= max_protein)
    AND (min_carbs IS NULL OR f.carbs_per_100g >= min_carbs)
    AND (max_carbs IS NULL OR f.carbs_per_100g <= max_carbs)
    AND (min_fat IS NULL OR f.fat_per_100g >= min_fat)
    AND (max_fat IS NULL OR f.fat_per_100g <= max_fat)
    AND (max_sugar IS NULL OR f.sugar_per_100g <= max_sugar)
    AND (min_sodium IS NULL OR f.sodium_per_100g >= min_sodium)
    AND (max_sodium IS NULL OR f.sodium_per_100g <= max_sodium)
    AND (food_category IS NULL OR f.category ILIKE '%' || food_category || '%')
  ORDER BY f.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;