import os
import re
from bs4 import BeautifulSoup, Tag
from pathlib import Path
import glob
import html2text

def preprocess_partner_cards(html_content):
    """
    Pre-process partner cards to preserve partner category and name information
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'lxml')
    # Find all <li> elements that contain partner cards
    for li in soup.find_all('li'):
        partner_card = li.find('div', class_='partner-card')
        if partner_card:
            # Robustly extract category from any descendant with class 'partner-header'
            category = "Partner"
            for desc in partner_card.descendants:
                if getattr(desc, 'name', None) == 'div' and 'partner-header' in desc.get('class', []):
                    category = desc.get_text(strip=True)
                    break
            # Extract name from img alt and URL from link
            link = li.find('a', href=True)
            img = partner_card.find('img', alt=True)
            name = img['alt'].strip() if img and img.has_attr('alt') else 'Unknown'
            url = link['href'].strip() if link and link.has_attr('href') else ''
            # Replace the entire <li> content with plain text
            li.clear()
            li.string = f"{category}: {name} - {url}"
    return str(soup)

def convert_html_to_markdown(html_content):
    """
    Convert HTML content to Markdown format
    """
    # Pre-process partner cards to preserve partner information
    html_content = preprocess_partner_cards(html_content)
    
    # Configure html2text for better conversion
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = False
    h.ignore_emphasis = False
    h.ignore_tables = False
    h.body_width = 0  # No line wrapping
    h.unicode_snake = False
    h.escape_snob = True
    h.mark_code = True
    h.wrap_links = False
    
    # Convert HTML to Markdown
    markdown_content = h.handle(html_content)
    
    # Clean up the markdown
    markdown_content = clean_markdown_content(markdown_content)
    
    return markdown_content

def clean_markdown_content(markdown_content):
    """
    Clean and improve the markdown content
    """
    # Remove excessive blank lines
    markdown_content = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown_content)
    
    # Fix image links to preserve alt text and URLs
    markdown_content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'![\1](\2)', markdown_content)
    
    # Fix link formatting
    markdown_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'[\1](\2)', markdown_content)
    
    # Remove leading/trailing whitespace
    markdown_content = markdown_content.strip()
    
    return markdown_content

def extract_images_with_alt(html_content):
    """
    Extract images with their alt text and URLs for better handling
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    images = []
    
    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '')
        title = img.get('title', '')
        
        if src:
            images.append({
                'src': src,
                'alt': alt or title or 'Image',
                'title': title
            })
    
    return images

def enhance_markdown_with_images(markdown_content, images):
    """
    Enhance markdown content with better image handling
    """
    # Replace basic image references with enhanced ones
    for img in images:
        # Create enhanced image markdown
        enhanced_img = f"![{img['alt']}]({img['src']})"
        if img['title']:
            enhanced_img += f" *{img['title']}*"
        
        # Try to replace basic image references
        basic_img_pattern = rf"!\[.*?\]\({re.escape(img['src'])}\)"
        markdown_content = re.sub(basic_img_pattern, enhanced_img, markdown_content)
    
    return markdown_content

def convert_html_file(input_file, output_file):
    """
    Convert a single HTML file to Markdown
    """
    try:
        # Read HTML file
        with open(input_file, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        # Extract images for better handling
        images = extract_images_with_alt(html_content)
        
        # Convert to Markdown
        markdown_content = convert_html_to_markdown(html_content)
        
        # Enhance with better image handling
        markdown_content = enhance_markdown_with_images(markdown_content, images)
        
        # Write Markdown file
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(markdown_content)
        
        return {
            'success': True,
            'images_found': len(images)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def convert_all_html_files(input_folder='cleaned_html_files', output_folder='markdown_files'):
    """
    Convert all HTML files in the input folder to Markdown
    """
    # Create output folder
    Path(output_folder).mkdir(exist_ok=True)
    
    # Find all HTML files
    html_files = glob.glob(os.path.join(input_folder, '*.html'))
    
    if not html_files:
        print(f"No HTML files found in {input_folder}/")
        return
    
    print(f"Found {len(html_files)} HTML files to convert")
    print(f"Output folder: {output_folder}/")
    print("=" * 60)
    
    successful = 0
    failed = 0
    total_images = 0
    
    for i, input_file in enumerate(html_files, 1):
        filename = os.path.basename(input_file)
        # Change extension from .html to .md
        md_filename = filename.replace('.html', '.md')
        output_file = os.path.join(output_folder, md_filename)
        
        print(f"[{i}/{len(html_files)}] Converting: {filename}")
        
        result = convert_html_file(input_file, output_file)
        
        if result['success']:
            successful += 1
            total_images += result['images_found']
            print(f"  ✓ Saved: {md_filename}")
            print(f"  ✓ Images: {result['images_found']}")
        else:
            failed += 1
            print(f"  ✗ Error: {result['error']}")
        
        print()
    
    # Summary
    print("=" * 60)
    print("CONVERSION COMPLETE!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total images processed: {total_images}")
    print(f"Files saved in: {output_folder}/")

def main():
    print("HTML to Markdown Converter")
    print("This script converts cleaned HTML files to Markdown format")
    print()
    
    # Check if input folder exists
    if not os.path.exists('cleaned_html_files'):
        print("Error: cleaned_html_files/ folder not found.")
        print("Please run html_cleaner.py first to create cleaned HTML files.")
        return
    
    # Start conversion
    convert_all_html_files()

if __name__ == "__main__":
    main() 