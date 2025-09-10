#!/bin/bash

# USDA Food Data Processing Pipeline
# Downloads, cleans, and uploads food data to Supabase

set -e  # Exit on any error

echo "Starting USDA Food Data Pipeline"

# Configuration
DATASET_URL="https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip"
DATA_DIR="dataset"  # Folder to store all files
ZIP_FILE="$DATA_DIR/FoodData_Central_sr_legacy_food_json_2018-04.zip"
JSON_FILE="$DATA_DIR/FoodData_Central_sr_legacy_food_json_2018-04.json"
CLEANED_FILE="$DATA_DIR/cleaned_foods.json"
SAMPLE_SIZE=1000

# Step 0: Create data directory if it doesn't exist
mkdir -p "$DATA_DIR"

# Step 1: Download dataset
echo "Downloading USDA food dataset..."
if [ ! -f "$ZIP_FILE" ]; then
    wget -O "$ZIP_FILE" "$DATASET_URL"
else
    echo "Dataset already exists, skipping download"
fi

# Step 2: Extract dataset
echo "Extracting dataset..."
if [ ! -f "$JSON_FILE" ]; then
    unzip "$ZIP_FILE" -d "$DATA_DIR"
else
    echo "Dataset already extracted"
fi

# Step 3: Clean and process data
echo "Cleaning food data (sample size: $SAMPLE_SIZE)..."
python3 scripts/usda_cleaner.py "$JSON_FILE" "$CLEANED_FILE" "$SAMPLE_SIZE"

# Step 4: Generate embeddings and upload to Supabase
echo "Generating embeddings and uploading to Supabase..."
python3 scripts/upload_foods.py "$CLEANED_FILE"

echo "Pipeline completed successfully!"
