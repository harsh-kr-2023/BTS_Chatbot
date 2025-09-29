import os
import re
from bs4 import BeautifulSoup, Tag
from pathlib import Path
import glob

def count_tokens_in_text(text):
    """
    Count different types of tokens in text
    """
    # Remove markdown formatting for word counting
    clean_text = re.sub(r'[#*_`~\[\]()!]', '', text)
    
    # Count words (split by whitespace)
    words = clean_text.split()
    word_count = len(words)
    
    # Count characters (including spaces)
    char_count = len(text)
    
    # Count characters (excluding spaces)
    char_count_no_spaces = len(text.replace(' ', ''))
    
    # Count lines
    line_count = len(text.split('\n'))
    
    # Count non-empty lines
    non_empty_lines = [line.strip() for line in text.split('\n') if line.strip()]
    non_empty_line_count = len(non_empty_lines)
    
    # Count markdown elements
    headings = len(re.findall(r'^#{1,6}\s', text, re.MULTILINE))
    links = len(re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text))
    images = len(re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', text))
    bold_text = len(re.findall(r'\*\*([^*]+)\*\*', text))
    italic_text = len(re.findall(r'\*([^*]+)\*', text))
    code_blocks = len(re.findall(r'```[\s\S]*?```', text))
    inline_code = len(re.findall(r'`([^`]+)`', text))
    lists = len(re.findall(r'^[\s]*[-*+]\s', text, re.MULTILINE))
    numbered_lists = len(re.findall(r'^[\s]*\d+\.\s', text, re.MULTILINE))
    
    return {
        'words': word_count,
        'characters': char_count,
        'characters_no_spaces': char_count_no_spaces,
        'lines': line_count,
        'non_empty_lines': non_empty_line_count,
        'headings': headings,
        'links': links,
        'images': images,
        'bold_text': bold_text,
        'italic_text': italic_text,
        'code_blocks': code_blocks,
        'inline_code': inline_code,
        'lists': lists,
        'numbered_lists': numbered_lists
    }

def count_words_in_cleaned_html(html_content):
    """
    Count words in cleaned HTML content (excluding header, footer, style, js, navbar, inline styles)
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        unwanted_elements = ['header', 'footer', 'nav', 'script', 'style', 'link', 'meta', 'title']
        for element in soup.find_all(unwanted_elements):
            element.extract()
        
        # Remove elements with navigation/footer related classes
        for element in soup.find_all(class_=re.compile(r'(nav|header|footer|menu|sidebar)', re.I)):
            element.extract()
        
        # Remove elements with navigation/footer related IDs
        for element in soup.find_all(id=re.compile(r'(nav|header|footer|menu|sidebar)', re.I)):
            element.extract()
        
        # Remove inline styles
        for element in soup.find_all():
            if isinstance(element, Tag) and 'style' in element.attrs:
                del element.attrs['style']
        
        # Get clean text content
        clean_text = soup.get_text()
        
        # Clean up whitespace and count words
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        words = clean_text.split()
        
        return len(words)
        
    except Exception as e:
        print(f"Error processing HTML: {e}")
        return 0

def analyze_markdown_file(file_path):
    """
    Analyze a single Markdown file and return token counts
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        file_size = os.path.getsize(file_path)
        tokens = count_tokens_in_text(content)
        
        # Get corresponding HTML file for comparison
        html_file_path = file_path.replace('markdown_files', 'cleaned_html_files').replace('.md', '.html')
        html_word_count = 0
        
        if os.path.exists(html_file_path):
            try:
                with open(html_file_path, 'r', encoding='utf-8') as html_file:
                    html_content = html_file.read()
                html_word_count = count_words_in_cleaned_html(html_content)
            except Exception as e:
                print(f"Warning: Could not read HTML file {html_file_path}: {e}")
        
        return {
            'success': True,
            'file_size': file_size,
            'tokens': tokens,
            'html_words': html_word_count
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

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

def analyze_all_markdown_files(input_folder='markdown_files'):
    """
    Analyze all Markdown files in the input folder
    """
    # Find all Markdown files
    md_files = glob.glob(os.path.join(input_folder, '*.md'))
    
    if not md_files:
        print(f"No Markdown files found in {input_folder}/")
        return
    
    print(f"Found {len(md_files)} Markdown files to analyze")
    print("=" * 80)
    
    all_results = []
    successful = 0
    failed = 0
    
    for i, file_path in enumerate(md_files, 1):
        filename = os.path.basename(file_path)
        
        print(f"[{i}/{len(md_files)}] Analyzing: {filename}")
        
        result = analyze_markdown_file(file_path)
        
        if result['success']:
            successful += 1
            all_results.append({
                'filename': filename,
                'file_size': result['file_size'],
                'tokens': result['tokens'],
                'html_words': result['html_words']
            })
            
            tokens = result['tokens']
            print(f"  ✓ File size: {format_file_size(result['file_size'])}")
            print(f"  ✓ Markdown Words: {tokens['words']:,}")
            print(f"  ✓ HTML Words: {result['html_words']:,}")
            print(f"  ✓ Characters: {tokens['characters']:,}")
            print(f"  ✓ Lines: {tokens['lines']:,} (non-empty: {tokens['non_empty_lines']:,})")
            print(f"  ✓ Elements: {tokens['headings']} headings, {tokens['links']} links, {tokens['images']} images")
        else:
            failed += 1
            print(f"  ✗ Error: {result['error']}")
        
        print()
    
    # Generate summary statistics
    if all_results:
        generate_summary_report(all_results)
    
    # Summary
    print("=" * 80)
    print("ANALYSIS COMPLETE!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

def generate_summary_report(results):
    """
    Generate a comprehensive summary report
    """
    print("=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    
    # Calculate totals
    total_files = len(results)
    total_md_words = sum(r['tokens']['words'] for r in results)
    total_html_words = sum(r['html_words'] for r in results)
    total_chars = sum(r['tokens']['characters'] for r in results)
    total_lines = sum(r['tokens']['lines'] for r in results)
    total_file_size = sum(r['file_size'] for r in results)
    
    # Calculate averages
    avg_md_words = total_md_words / total_files if total_files > 0 else 0
    avg_html_words = total_html_words / total_files if total_files > 0 else 0
    avg_chars = total_chars / total_files if total_files > 0 else 0
    avg_lines = total_lines / total_files if total_files > 0 else 0
    
    # Find min/max
    max_words_file = max(results, key=lambda x: x['tokens']['words'])
    min_words_file = min(results, key=lambda x: x['tokens']['words'])
    
    print(f"Total Files: {total_files}")
    print(f"Total Markdown Words: {total_md_words:,}")
    print(f"Total HTML Words: {total_html_words:,}")
    print(f"Total Characters: {total_chars:,}")
    print(f"Total Lines: {total_lines:,}")
    print(f"Total File Size: {format_file_size(total_file_size)}")
    print()
    
    print(f"Average Markdown Words per File: {avg_md_words:.1f}")
    print(f"Average HTML Words per File: {avg_html_words:.1f}")
    print(f"Average Characters per File: {avg_chars:.1f}")
    print(f"Average Lines per File: {avg_lines:.1f}")
    print()
    
    print(f"Largest File (by words): {max_words_file['filename']} ({max_words_file['tokens']['words']:,} words)")
    print(f"Smallest File (by words): {min_words_file['filename']} ({min_words_file['tokens']['words']:,} words)")
    print()
    
    # Element counts
    total_headings = sum(r['tokens']['headings'] for r in results)
    total_links = sum(r['tokens']['links'] for r in results)
    total_images = sum(r['tokens']['images'] for r in results)
    total_code_blocks = sum(r['tokens']['code_blocks'] for r in results)
    
    print("ELEMENT TOTALS:")
    print(f"  Headings: {total_headings}")
    print(f"  Links: {total_links}")
    print(f"  Images: {total_images}")
    print(f"  Code Blocks: {total_code_blocks}")
    print()
    
    # Save detailed report to file
    save_detailed_report(results)

def save_detailed_report(results):
    """
    Save detailed token analysis to a file
    """
    report_file = 'token_analysis_report.txt'
    
    try:
        with open(report_file, 'w', encoding='utf-8') as file:
            file.write("DETAILED TOKEN ANALYSIS REPORT\n")
            file.write("=" * 50 + "\n\n")
            
            for result in results:
                file.write(f"File: {result['filename']}\n")
                file.write(f"Size: {format_file_size(result['file_size'])}\n")
                file.write(f"Markdown Words: {result['tokens']['words']:,}\n")
                file.write(f"HTML Words: {result['html_words']:,}\n")
                file.write(f"Markdown Characters: {result['tokens']['characters']:,}\n")
                file.write(f"Markdown Characters (no spaces): {result['tokens']['characters_no_spaces']:,}\n")
                file.write(f"Markdown Lines: {result['tokens']['lines']:,}\n")
                file.write(f"Markdown Non-empty lines: {result['tokens']['non_empty_lines']:,}\n")
                file.write(f"Markdown Headings: {result['tokens']['headings']}\n")
                file.write(f"Markdown Links: {result['tokens']['links']}\n")
                file.write(f"Markdown Images: {result['tokens']['images']}\n")
                file.write(f"Markdown Bold text: {result['tokens']['bold_text']}\n")
                file.write(f"Markdown Italic text: {result['tokens']['italic_text']}\n")
                file.write(f"Markdown Code blocks: {result['tokens']['code_blocks']}\n")
                file.write(f"Markdown Inline code: {result['tokens']['inline_code']}\n")
                file.write(f"Markdown Lists: {result['tokens']['lists']}\n")
                file.write(f"Markdown Numbered lists: {result['tokens']['numbered_lists']}\n")
                file.write("-" * 30 + "\n\n")
        
        print(f"Detailed report saved to: {report_file}")
        
    except Exception as e:
        print(f"Error saving report: {e}")

def main():
    print("Markdown Token Counter")
    print("This script analyzes token counts in Markdown files")
    print()
    
    # Check if input folder exists
    if not os.path.exists('markdown_files'):
        print("Error: markdown_files/ folder not found.")
        print("Please run html_to_markdown.py first to create Markdown files.")
        return
    
    # Start analysis
    analyze_all_markdown_files()

if __name__ == "__main__":
    main() 