import requests
import os
from urllib.parse import urlparse
import time
from pathlib import Path

def sanitize_filename(url):
    """
    Convert URL to a valid filename
    """
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    
    if not path:
        path = 'index'
    
    # Remove file extension if present
    if '.' in path.split('/')[-1]:
        path = path.rsplit('.', 1)[0]
    
    # Replace invalid characters
    filename = path.replace('/', '_').replace('?', '_').replace('&', '_').replace('=', '_')
    
    # Limit filename length
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename + '.html'

def fetch_html_from_url(url, output_folder):
    """
    Fetch HTML content from a URL and save it to a file
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        print(f"Fetching: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Create filename from URL
        filename = sanitize_filename(url)
        filepath = os.path.join(output_folder, filename)
        
        # Save HTML content
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(response.text)
        
        print(f"  ✓ Saved: {filename}")
        return True
        
    except requests.RequestException as e:
        print(f"  ✗ Error fetching {url}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error saving {url}: {e}")
        return False

def read_urls_from_file(filename='urls.txt'):
    """
    Read URLs from urls.txt file
    """
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            urls = [line.strip() for line in file if line.strip()]
        return urls
    except FileNotFoundError:
        print(f"Error: {filename} not found. Please run url_fetcher.py first.")
        return []
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []

def create_output_folder(folder_name='html_files'):
    """
    Create output folder if it doesn't exist
    """
    try:
        Path(folder_name).mkdir(exist_ok=True)
        print(f"Output folder: {folder_name}")
        return folder_name
    except Exception as e:
        print(f"Error creating folder: {e}")
        return None

def main():
    # Create output folder
    output_folder = create_output_folder()
    if not output_folder:
        return
    
    # Read URLs from urls.txt
    urls = read_urls_from_file()
    if not urls:
        return
    
    print(f"Found {len(urls)} URLs to fetch")
    print("=" * 50)
    
    # Fetch HTML for each URL
    successful = 0
    failed = 0
    
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] ", end="")
        
        if fetch_html_from_url(url, output_folder):
            successful += 1
        else:
            failed += 1
        
        # Add a small delay to be respectful to the server
        time.sleep(1)
    
    print("=" * 50)
    print(f"Download complete!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Files saved in: {output_folder}/")

if __name__ == "__main__":
    main() 