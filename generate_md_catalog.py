import os
import json
import argparse
import glob
from typing import List, Dict
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

load_dotenv()

CATALOG_PATH = "catalog.json"
MARKDOWN_DIR = "markdown_files"

def get_llm_summary(content: str, filename: str, model=None) -> List[str]:
    if not model:
        return ["[LLM not available]", f"Page: {filename}"]
    prompt = f"""
You are an expert assistant. Given the following markdown content from a website page, extract ONLY the main topics, categories, or types of information that are present in this file. Do NOT include any detailed facts, data, or descriptions. Your goal is to help another AI system quickly identify which files are relevant to a user's question by listing what general information or sections this file covers.

Return the output as a JSON array of strings, where each string is a high-level topic or category present in the file. Do not include any detailed content, explanations, or page-specific keywords. Focus on general, reusable topic labels that describe the kinds of information found in the file.

Markdown content (filename: {filename}):
---
{content}
---

Return only the JSON array of topic strings.
"""
    response = model.generate_content(prompt)
    import re
    import ast
    match = re.search(r'\[[\s\S]*\]', response.text)
    if match:
        json_str = match.group(0)
        try:
            summary = json.loads(json_str)
        except Exception:
            summary = ast.literal_eval(json_str)
        if isinstance(summary, list):
            return summary
    return [response.text.strip()]

def analyze_markdown_file(file_path: str, model=None) -> Dict:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        filename = os.path.basename(file_path)
        summary = get_llm_summary(content, filename, model)
        return {
            'filename': filename,
            'summary': summary
        }
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return None

def generate_catalog(input_folder: str, output_file: str, db_info: dict):
    md_files = glob.glob(os.path.join(input_folder, '*.md'))
    if not md_files:
        print(f"No markdown files found in {input_folder}/")
        return
    print(f"Found {len(md_files)} markdown files to analyze")
    print("=" * 60)
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("GEMINI_API_KEY not set. LLM summaries will be placeholders.")
        model = None
    else:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
    catalog = []
    for i, file_path in enumerate(md_files, 1):
        filename = os.path.basename(file_path)
        print(f"[{i}/{len(md_files)}] Analyzing: {filename}")
        result = analyze_markdown_file(file_path, model)
        if result:
            catalog.append(result)
            print(f"  ✓ Bullets: {len(result['summary'])}")
        else:
            print(f"  ✗ Failed to analyze")
        print()
    catalog_obj = {
        "db_info": db_info,
        "pages": catalog
    }
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(catalog_obj, file, indent=2, ensure_ascii=False)
    print("=" * 60)
    print("CATALOG GENERATION COMPLETE!")
    print(f"Catalog saved to: {output_file}")

def load_catalog():
    if os.path.exists(CATALOG_PATH):
        with open(CATALOG_PATH, "r") as f:
            return json.load(f)
    return {}

def save_catalog(catalog):
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)

def is_new_or_updated(file_path, catalog):
    mtime = os.path.getmtime(file_path)
    rel_path = os.path.relpath(file_path, MARKDOWN_DIR)
    entry = catalog.get(rel_path)
    return not entry or entry["mtime"] != mtime

def update_catalog():
    catalog = load_catalog()
    for root, _, files in os.walk(MARKDOWN_DIR):
        for file in files:
            if file.endswith(".md"):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, MARKDOWN_DIR)
                mtime = os.path.getmtime(path)
                if is_new_or_updated(path, catalog):
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    catalog[rel_path] = {
                        "mtime": mtime,
                        "updated": datetime.now().isoformat(),
                        "content": content[:100]  # preview
                    }
    save_catalog(catalog)

def main():
    parser = argparse.ArgumentParser(description='Generate a user-focused catalog from markdown files using Gemini LLM.')
    parser.add_argument('--input-folder', default='markdown_files', help='Folder containing markdown files')
    parser.add_argument('--output-file', default='catalog.json', help='Output catalog JSON file')
    args = parser.parse_args()
    db_info = {
        "description": "The following types of data can be fetched directly from the database via DB queries:",
        "available_data": [
            "Speakers: names, designations, profiles, photos, LinkedIn links, and speaker order.",
            "Sessions: day, sector, session topic, subtopic, start/end time, and session-speaker mapping.",
            "Speaker-Session Mapping: which speakers are in which sessions, and their roles.",
            "Schedule: session times, days, and topics.",
            "Awards, panels, and special program participants (if present in DB)."
        ],
        "note": "For any question about speakers, sessions, or the event schedule, the system will use the database for the most accurate and up-to-date information."
    }
    if not os.path.exists(args.input_folder):
        print(f"Error: {args.input_folder}/ folder not found.")
        return
    generate_catalog(args.input_folder, args.output_file, db_info)
    update_catalog()

if __name__ == "__main__":
    main()