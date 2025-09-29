import os
import re
from bs4 import BeautifulSoup
from pathlib import Path
import glob

def clean_html_content(html_content):
    """
    Clean HTML content by removing head, navbar, scripts, footer, and inline styles
    """
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove entire head section
    if soup.head:
        soup.head.extract()
    
    # Remove all script tags
    for script in soup.find_all('script'):
        script.extract()
    
    # Remove all style tags
    for style in soup.find_all('style'):
        style.extract()
    
    # Remove all link tags (CSS, favicon, etc.)
    for link in soup.find_all('link'):
        link.extract()
    
    # Remove all meta tags
    for meta in soup.find_all('meta'):
        meta.extract()
    
    # Remove all title tags
    for title in soup.find_all('title'):
        title.extract()
    
    # Remove inline styles from all elements
    from bs4 import Tag
    for element in soup.find_all():
        if isinstance(element, Tag) and 'style' in element.attrs:
            del element.attrs['style']
    
    # Remove common navbar elements (header, nav, etc.)
    for element in soup.find_all(['header', 'nav', 'navbar']):
        element.extract()
    
    # Remove footer elements
    for element in soup.find_all(['footer', 'footer-nav']):
        element.extract()
    
    # Remove elements with common navbar/footer classes (but preserve partner-header)
    for element in soup.find_all(class_=re.compile(r'(nav|footer|menu|sidebar)', re.I)):
        element.extract()
    
    # Remove header elements but preserve partner-header
    for element in soup.find_all(class_=re.compile(r'^header$', re.I)):
        element.extract()
    
    # Remove elements with common navbar/footer IDs
    for element in soup.find_all(id=re.compile(r'(nav|header|footer|menu|sidebar)', re.I)):
        element.extract()
    
    # Remove cookie-related elements
    # Remove elements with cookie-related classes
    for element in soup.find_all(class_=re.compile(r'(cookie|consent|gdpr|privacy|accept|banner|notice|popup|modal)', re.I)):
        element.extract()
    
    # Remove elements with cookie-related IDs
    for element in soup.find_all(id=re.compile(r'(cookie|consent|gdpr|privacy|accept|banner|notice|popup|modal)', re.I)):
        element.extract()
    
    # Remove common cookie consent elements by tag and text content
    for element in soup.find_all(['div', 'section', 'aside']):
        if element.get_text():
            text = element.get_text().lower()
            if any(keyword in text for keyword in ['cookie', 'consent', 'gdpr', 'privacy policy', 'accept cookies', 'we use cookies']):
                element.extract()
    
    # Get the cleaned HTML
    cleaned_html = str(soup)
    
    # Remove empty lines (lines that contain only whitespace or are completely empty)
    cleaned_html = re.sub(r'\n\s*\n', '\n', cleaned_html)
    
    # Remove trailing empty lines at the end of the file
    cleaned_html = cleaned_html.rstrip('\n')
    
    return cleaned_html

def get_file_size(filepath):
    """
    Get file size in bytes
    """
    return os.path.getsize(filepath)

def format_file_size(size_bytes):
    """
    Convert bytes to human readable format
    """
    if size_bytes == 0:
        return "0B"
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    return f"{size_bytes:.1f}{size_names[i]}"

def clean_html_file(input_file, output_file):
    """
    Clean a single HTML file
    """
    try:
        # Read original file
        with open(input_file, 'r', encoding='utf-8') as file:
            original_content = file.read()
        
        original_size = get_file_size(input_file)
        
        # Clean the HTML content
        cleaned_content = clean_html_content(original_content)
        
        # Write cleaned content
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(cleaned_content)
        
        cleaned_size = get_file_size(output_file)
        size_reduction = original_size - cleaned_size
        reduction_percentage = (size_reduction / original_size) * 100 if original_size > 0 else 0
        
        return {
            'success': True,
            'original_size': original_size,
            'cleaned_size': cleaned_size,
            'reduction': size_reduction,
            'reduction_percentage': reduction_percentage
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def clean_all_html_files(input_folder='html_files', output_folder='cleaned_html_files'):
    """
    Clean all HTML files in the input folder and save to output folder
    """
    # Create output folder
    Path(output_folder).mkdir(exist_ok=True)
    
    # Find all HTML files
    html_files = glob.glob(os.path.join(input_folder, '*.html'))
    
    if not html_files:
        print(f"No HTML files found in {input_folder}/")
        return
    
    print(f"Found {len(html_files)} HTML files to clean")
    print(f"Output folder: {output_folder}/")
    print("=" * 60)
    
    total_original_size = 0
    total_cleaned_size = 0
    successful = 0
    failed = 0
    
    for i, input_file in enumerate(html_files, 1):
        filename = os.path.basename(input_file)
        output_file = os.path.join(output_folder, filename)
        
        print(f"[{i}/{len(html_files)}] Cleaning: {filename}")
        
        result = clean_html_file(input_file, output_file)
        
        if result['success']:
            successful += 1
            total_original_size += result['original_size']
            total_cleaned_size += result['cleaned_size']
            
            print(f"  ✓ Original: {format_file_size(result['original_size'])}")
            print(f"  ✓ Cleaned:  {format_file_size(result['cleaned_size'])}")
            print(f"  ✓ Reduced:  {format_file_size(result['reduction'])} ({result['reduction_percentage']:.1f}%)")
        else:
            failed += 1
            print(f"  ✗ Error: {result['error']}")
        
        print()
    
    # Summary
    print("=" * 60)
    print("CLEANING COMPLETE!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total original size: {format_file_size(total_original_size)}")
    print(f"Total cleaned size:  {format_file_size(total_cleaned_size)}")
    
    if total_original_size > 0:
        total_reduction = total_original_size - total_cleaned_size
        total_reduction_percentage = (total_reduction / total_original_size) * 100
        print(f"Total space saved: {format_file_size(total_reduction)} ({total_reduction_percentage:.1f}%)")
    
    print(f"Files saved in: {output_folder}/")

def main():
    print("HTML File Cleaner")
    print("This script will clean HTML files by removing head, navbar, scripts, footer, and inline styles")
    print()
    
    # Check if input folder exists
    if not os.path.exists('html_files'):
        print("Error: html_files/ folder not found.")
        print("Please run html_fetcher.py first to download HTML files.")
        return
    
    # Start cleaning
    clean_all_html_files()

if __name__ == "__main__":
    main() 