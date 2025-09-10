# CalorAI Founding Engineer Take Home Challenge

This project implements a reproducible pipeline to:

* Import a food dataset into Supabase.
* Generate embeddings for semantic search using OpenAI.
* Expose a search RPC for efficient querying.
* Build an **n8n-based chat agent** that can answer user queries against the food database.

---

## 🚀 Project Setup

Follow these steps to reproduce the project on a fresh environment:

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Setup

* Edit `.env.example` and add your **Supabase** and **OpenAI** credentials.
* Rename the file to `.env`.

### 3. Supabase Schema

* Open your Supabase dashboard → SQL Editor.
* Copy and paste the contents of `schema/supabase_schema.sql` and execute it using Ctrl + Enter.
* This sets up tables for foods and embeddings (using `pgvector`).

### 4. Data Upload

* Make the data upload script executable:

  ```bash
  chmod +x scripts/data_pipeline.sh
  ```
  Note : For this task the number of food items are restricted to 1000 which can be changed in the script by changing the SAMPLE_SIZE variable.
* Run the script to ingest foods and generate embeddings.
  ```bash
  ./scripts/data_pipeline.sh
  ```
  Note: Enter y when prompted.
* Once complete, embeddings will be uploaded to Supabase.



### 5. n8n Workflow

* Open your n8n editor.
* Copy the contents of `n8n/workflow.json` into the editor.
* Configure **Supabase**, **Groq** (https://groq.com/) and **OpenAI** credentials in their respective nodes.
* Add your Supabase URL as a variable:

  ```
  Key = SUPABASE_URL
  ```

### 6. Frontend Hook

* Copy the production webhook URL from n8n and activate your workflow.
* Open the frontend in your browser `frontend/index.html` and paste the Webhook URL and start chatting.
* You are now ready to **chat with your assistant**.

---

## 📦 Dataset

This project supports any of the approved public datasets (≥1k foods):

* [USDA FoodData Central](https://fdc.nal.usda.gov/download-datasets.html)

---
