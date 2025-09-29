import os
import json
import argparse
import re
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

class DocumentRetriever:
    def __init__(self, catalog_path: str, md_folder: str, model_name: str = 'all-MiniLM-L6-v2'):
        """
        Initialize the document retriever
        """
        self.catalog_path = catalog_path
        self.md_folder = md_folder
        self.model_name = model_name
        
        # Load catalog
        self.catalog = self.load_catalog()
        
        # Initialize sentence transformer model
        try:
            self.model = SentenceTransformer(model_name)
            print(f"✓ Loaded model: {model_name}")
        except Exception as e:
            print(f"Warning: Could not load {model_name}, using basic similarity: {e}")
            self.model = None
    
    def load_catalog(self) -> List[Dict[str, Any]]:
        """
        Load the catalog from JSON file
        """
        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as file:
                catalog = json.load(file)
            print(f"✓ Loaded catalog with {len(catalog)} entries")
            return catalog
        except Exception as e:
            print(f"Error loading catalog: {e}")
            return []
    
    def compute_catalog_match_score(self, query: str, entry: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        """
        Compute a match score based on catalog metadata
        """
        query_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
        
        # Extract text from catalog entry
        title_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', entry.get('title', '').lower()))
        section_terms = set()
        for section in entry.get('sections', []):
            section_terms.update(re.findall(r'\b[a-zA-Z]{3,}\b', section.lower()))
        
        # Handle keywords properly - split multi-word keywords
        keyword_terms = set()
        for keyword in entry.get('keywords', []):
            if keyword:
                # Split multi-word keywords into individual terms
                keyword_words = re.findall(r'\b[a-zA-Z]{3,}\b', keyword.lower())
                keyword_terms.update(keyword_words)
        
        # Calculate overlaps
        title_overlap = len(query_terms & title_terms)
        section_overlap = len(query_terms & section_terms)
        keyword_overlap = len(query_terms & keyword_terms)
        
        # Check for exact phrase matches in sections (more important)
        exact_section_matches = 0
        for section in entry.get('sections', []):
            if section and isinstance(section, str):  # Ensure section is not None and is string
                section_lower = section.lower()
                if any(term in section_lower for term in query_terms):
                    exact_section_matches += 1
        
        # Check for exact keyword matches (very important)
        exact_keyword_matches = 0
        for keyword in entry.get('keywords', []):
            if keyword and isinstance(keyword, str):
                keyword_lower = keyword.lower()
                if any(term in keyword_lower for term in query_terms):
                    exact_keyword_matches += 1
        
        # Weighted scoring with improved logic - prioritize specific matches
        title_score = title_overlap * 5.0  # Title matches are most important
        section_score = section_overlap * 4.0  # Section matches are very important
        keyword_score = keyword_overlap * 1.0  # Keyword matches are less important
        exact_section_bonus = exact_section_matches * 6.0  # Exact section matches get highest bonus
        exact_keyword_bonus = exact_keyword_matches * 8.0  # Exact keyword matches get highest bonus
        
        total_score = title_score + section_score + keyword_score + exact_section_bonus + exact_keyword_bonus
        
        # Penalize if only partial matches (e.g., only "list" but not "speakers")
        if len(query_terms) > 1:
            match_ratio = (title_overlap + section_overlap + keyword_overlap) / len(query_terms)
            if match_ratio < 0.5:  # If less than half the query terms match
                total_score *= 0.3  # Apply penalty
        
        # Normalize by query length
        if len(query_terms) > 0:
            total_score = total_score / len(query_terms)
        
        # Create breakdown for logging
        breakdown = {
            'title_matches': list(query_terms & title_terms),
            'section_matches': list(query_terms & section_terms),
            'keyword_matches': list(query_terms & keyword_terms),
            'exact_section_matches': exact_section_matches,
            'exact_keyword_matches': exact_keyword_matches,
            'title_score': title_score,
            'section_score': section_score,
            'keyword_score': keyword_score,
            'exact_section_bonus': exact_section_bonus,
            'exact_keyword_bonus': exact_keyword_bonus,
            'total_score': total_score
        }
        
        return total_score, breakdown
    
    def select_top_catalog_matches(self, query: str, top_k: int = 5) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Select top N files from catalog based on metadata matching
        """
        matches = []
        
        for entry in self.catalog:
            filename = entry['filename']
            score, breakdown = self.compute_catalog_match_score(query, entry)
            
            if score > 0:  # Only include files with some match
                matches.append((filename, score, breakdown))
        
        # Sort by score and return top K
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:top_k]
    
    def load_markdown_content(self, filename: str) -> str:
        """
        Load the full content of a markdown file
        """
        file_path = os.path.join(self.md_folder, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            return content
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return ""
    
    def compute_semantic_similarity(self, query: str, content: str) -> float:
        """
        Compute semantic similarity between query and content using embeddings
        """
        if self.model is None:
            # Fallback to basic text similarity
            return self.compute_basic_similarity(query, content)
        
        try:
            # Generate embeddings
            query_embedding = self.model.encode([query])
            content_embedding = self.model.encode([content])
            
            # Compute cosine similarity
            similarity = cosine_similarity(query_embedding, content_embedding)[0][0]
            return float(similarity)
            
        except Exception as e:
            print(f"Error computing semantic similarity: {e}")
            return self.compute_basic_similarity(query, content)
    
    def compute_basic_similarity(self, query: str, content: str) -> float:
        """
        Fallback similarity computation using word overlap
        """
        query_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', query.lower()))
        content_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', content.lower()))
        
        if len(query_terms) == 0:
            return 0.0
        
        overlap = len(query_terms & content_terms)
        return overlap / len(query_terms)
    
    def retrieve_documents(self, query: str, top_k: int = 3, catalog_top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Main retrieval function
        """
        print(f"Query: '{query}'")
        print(f"Retrieving top {top_k} documents from catalog top {catalog_top_k}")
        print("=" * 60)
        
        # Step 1: Select top matches from catalog
        catalog_matches = self.select_top_catalog_matches(query, catalog_top_k)
        
        if not catalog_matches:
            print("No catalog matches found!")
            return []
        
        print(f"Top {len(catalog_matches)} catalog matches:")
        for i, (filename, score, breakdown) in enumerate(catalog_matches, 1):
            print(f"{i}. {filename} (score: {score:.3f})")
            if breakdown['title_matches']:
                print(f"   Title matches: {breakdown['title_matches']}")
            if breakdown['section_matches']:
                print(f"   Section matches: {breakdown['section_matches']}")
            if breakdown['keyword_matches']:
                print(f"   Keyword matches: {breakdown['keyword_matches']}")
            if breakdown.get('exact_section_matches', 0) > 0:
                print(f"   Exact section matches: {breakdown['exact_section_matches']}")
            if breakdown.get('exact_keyword_matches', 0) > 0:
                print(f"   Exact keyword matches: {breakdown['exact_keyword_matches']}")
            print()
        
        # Step 2: Load content and compute semantic similarity
        results = []
        
        print("Computing semantic similarity...")
        for filename, catalog_score, breakdown in catalog_matches:
            print(f"Processing: {filename}")
            
            # Load content
            content = self.load_markdown_content(filename)
            if not content:
                continue
            
            # Compute semantic similarity
            semantic_score = self.compute_semantic_similarity(query, content)
            
            # Combine scores (weighted average)
            combined_score = (catalog_score * 0.3) + (semantic_score * 0.7)
            
            results.append({
                'filename': filename,
                'catalog_score': catalog_score,
                'semantic_score': semantic_score,
                'similarity_score': combined_score,
                'content': content,
                'catalog_breakdown': breakdown
            })
        
        # Step 3: Sort by combined score and return top K
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:top_k]
    
    def save_results(self, results: List[Dict[str, Any]], output_file: str = None):
        """
        Save results to JSON file
        """
        if not output_file:
            output_file = 'retrieval_results.json'
        
        # Prepare output (exclude full content for readability)
        output_results = []
        for result in results:
            output_result = {
                'filename': result['filename'],
                'similarity_score': result['similarity_score'],
                'catalog_score': result['catalog_score'],
                'semantic_score': result['semantic_score'],
                'content_preview': result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                'catalog_breakdown': result['catalog_breakdown']
            }
            output_results.append(output_result)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(output_results, file, indent=2, ensure_ascii=False)
            print(f"Results saved to: {output_file}")
        except Exception as e:
            print(f"Error saving results: {e}")

def main():
    parser = argparse.ArgumentParser(description='Retrieve relevant Markdown documents based on query')
    parser.add_argument('--catalog', default='catalog.json', 
                       help='Path to catalog.json file (default: catalog.json)')
    parser.add_argument('--md-folder', default='markdown_files',
                       help='Folder containing markdown files (default: markdown_files)')
    parser.add_argument('--query', required=True,
                       help='User query string')
    parser.add_argument('--top-k', type=int, default=3,
                       help='Number of top documents to return (default: 3)')
    parser.add_argument('--catalog-top-k', type=int, default=5,
                       help='Number of top catalog matches to consider (default: 5)')
    parser.add_argument('--output', default='retrieval_results.json',
                       help='Output JSON file (default: retrieval_results.json)')
    parser.add_argument('--model', default='all-MiniLM-L6-v2',
                       help='Sentence transformer model name (default: all-MiniLM-L6-v2)')
    parser.add_argument('--debug', action='store_true',
                       help='Show debug information about catalog entries')
    
    args = parser.parse_args()
    
    print("Markdown Document Retriever")
    print("This script searches catalog and retrieves relevant documents")
    print()
    
    # Check if files exist
    if not os.path.exists(args.catalog):
        print(f"Error: Catalog file {args.catalog} not found.")
        print("Please run generate_md_catalog.py first to create the catalog.")
        return
    
    if not os.path.exists(args.md_folder):
        print(f"Error: Markdown folder {args.md_folder} not found.")
        print("Please run html_to_markdown.py first to create markdown files.")
        return
    
    # Initialize retriever
    retriever = DocumentRetriever(args.catalog, args.md_folder, args.model)
    
    # Debug mode: show catalog entries
    if args.debug:
        print("\nDEBUG: Catalog entries containing query terms:")
        query_terms = set(re.findall(r'\b[a-zA-Z]{3,}\b', args.query.lower()))
        for entry in retriever.catalog:
            filename = entry['filename']
            title = entry.get('title', '')
            sections = entry.get('sections', [])
            keywords = entry.get('keywords', [])
            
            # Check for matches
            title_match = any(term in title.lower() for term in query_terms)
            section_matches = [s for s in sections if any(term in s.lower() for term in query_terms)]
            keyword_matches = [k for k in keywords if any(term in k.lower() for term in query_terms)]
            
            if title_match or section_matches or keyword_matches:
                print(f"\n{filename}:")
                if title_match:
                    print(f"  Title: {title}")
                if section_matches:
                    print(f"  Sections: {section_matches}")
                if keyword_matches:
                    print(f"  Keywords: {keyword_matches}")
        print("\n" + "="*60 + "\n")
    
    # Retrieve documents
    results = retriever.retrieve_documents(args.query, args.top_k, args.catalog_top_k)
    
    if not results:
        print("No relevant documents found!")
        return
    
    # Display results
    print("=" * 60)
    print("RETRIEVAL RESULTS")
    print("=" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result['filename']}")
        print(f"   Similarity Score: {result['similarity_score']:.3f}")
        print(f"   Catalog Score: {result['catalog_score']:.3f}")
        print(f"   Semantic Score: {result['semantic_score']:.3f}")
        print(f"   Content Preview: {result['content'][:200]}...")
        print()
    
    # Save results
    retriever.save_results(results, args.output)
    
    print("Retrieval complete!")

if __name__ == "__main__":
    main() 