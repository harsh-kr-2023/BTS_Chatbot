import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

def fetch_urls_from_website(base_url):
    """
    Fetch all URLs from a website and save them to urls.txt
    """
    try:
        # Send GET request to the website
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(base_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all links
        urls = set()
        
        # Get all anchor tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)
            
            # Only include URLs from the same domain
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                urls.add(full_url)
        
        # Get all script tags with src
        for script in soup.find_all('script', src=True):
            src = script['src']
            full_url = urljoin(base_url, src)
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                urls.add(full_url)
        
        # Get all link tags with href (CSS, etc.)
        for link_tag in soup.find_all('link', href=True):
            href = link_tag['href']
            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                urls.add(full_url)
        
        # Get all img tags with src
        for img in soup.find_all('img', src=True):
            src = img['src']
            full_url = urljoin(base_url, src)
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                urls.add(full_url)
        
        # Also look for URLs in the page content (for any missed URLs)
        page_text = response.text
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        found_urls = re.findall(url_pattern, page_text)
        
        for url in found_urls:
            if urlparse(url).netloc == urlparse(base_url).netloc:
                urls.add(url)
        
        return sorted(list(urls))
        
    except requests.RequestException as e:
        print(f"Error fetching the website: {e}")
        return []
    except Exception as e:
        print(f"Error processing the website: {e}")
        return []

def save_urls_to_file(urls, filename='urls.txt'):
    """
    Save URLs to a text file
    """
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            for url in urls:
                file.write(url + '\n')
        print(f"Successfully saved {len(urls)} URLs to {filename}")
    except Exception as e:
        print(f"Error saving URLs to file: {e}")

def main():
    base_url = "https://bengalurutechsummit.com/BTS-Demo-2025/"
    
    print(f"Fetching URLs from: {base_url}")
    print("Please wait...")
    
    urls = fetch_urls_from_website(base_url)
    
    if urls:
        print(f"Found {len(urls)} URLs:")
        for url in urls:
            print(f"  - {url}")
        
        save_urls_to_file(urls)
    else:
        print("No URLs found or error occurred.")

if __name__ == "__main__":
    main() 