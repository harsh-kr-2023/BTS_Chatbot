# Web Scraping Scripts

This repository contains nine Python scripts and a FastAPI service for scraping, cleaning, converting, analyzing, cataloging, retrieving, and answering questions about the Bengaluru Tech Summit website:

1. **URL Fetcher** - Extracts all URLs from the website
2. **HTML Fetcher** - Downloads HTML content from the extracted URLs
3. **HTML Cleaner** - Cleans HTML files by removing whitespace and unnecessary elements
4. **HTML to Markdown Converter** - Converts cleaned HTML files to Markdown format
5. **Token Counter** - Analyzes token counts in Markdown files
6. **Catalog Generator** - Creates metadata catalog from Markdown files
7. **Document Retriever** - Searches catalog and retrieves relevant documents
8. **Embeddings Generator** - Creates embeddings for semantic search
9. **Q&A API** - FastAPI service for answering questions using OpenAI GPT-3.5

## Scripts

### 1. URL Fetcher (`url_fetcher.py`)

Fetches all URLs from the Bengaluru Tech Summit website and saves them to a `urls.txt` file.

**Features:**

- Fetches URLs from anchor tags, script tags, link tags, and image tags
- Filters URLs to only include those from the same domain
- Saves all found URLs to `urls.txt`
- Handles relative and absolute URLs
- Includes error handling and user-friendly output

**Usage:**

```bash
python url_fetcher.py
```

### 2. HTML Fetcher (`html_fetcher.py`)

Downloads HTML content from all URLs in `urls.txt` and saves them as HTML files in a folder.

**Features:**

- Reads URLs from `urls.txt` file
- Downloads HTML content from each URL
- Saves HTML files with sanitized filenames
- Creates organized folder structure
- Includes progress tracking and error handling
- Respectful downloading with delays

**Usage:**

```bash
python html_fetcher.py
```

### 3. HTML Cleaner (`html_cleaner.py`)

Cleans HTML files by removing head section, navbar, scripts, footer, and inline styles to keep only the main content.

**Features:**

- Removes entire head section (meta, title, link, style tags)
- Removes all script tags
- Removes navbar and header elements
- Removes footer elements
- Removes cookie consent banners and notices
- Removes inline styles from all elements
- Removes empty newlines
- Shows file size reduction statistics
- Creates cleaned files in a separate folder

**Usage:**

```bash
python html_cleaner.py
```

### 4. HTML to Markdown Converter (`html_to_markdown.py`)

Converts cleaned HTML files to Markdown format while preserving all content, images, and links.

**Features:**

- Converts HTML structure to Markdown syntax
- Preserves all text content and formatting
- Handles images with alt text and URLs
- Maintains links and their descriptions
- Preserves headings, lists, and tables
- Creates clean, readable Markdown files
- Shows conversion progress and statistics

**Usage:**

```bash
python html_to_markdown.py
```

### 5. Token Counter (`token_counter.py`)

Analyzes token counts and statistics in Markdown files to understand content distribution.

**Features:**

- Counts words, characters, and lines
- Analyzes Markdown elements (headings, links, images)
- Provides file-by-file statistics
- Generates summary reports
- Saves detailed analysis to file
- Shows averages and extremes

**Usage:**

```bash
python token_counter.py
```

### 6. Catalog Generator (`generate_md_catalog.py`)

Creates a comprehensive metadata catalog from Markdown files to help identify content and topics.

**Features:**

- Extracts titles, sections, and headings from Markdown files
- Counts tokens using tiktoken (GPT-4 encoding)
- Generates intelligent summaries based on content
- Extracts keywords using TF-IDF approach
- Supports JSON and CSV output formats
- Provides detailed catalog statistics
- Command-line interface with customizable options

**Usage:**

```bash
# Basic usage (JSON output)
python generate_md_catalog.py

# Custom input folder and output file
python generate_md_catalog.py --input-folder ./markdown_files --output-file catalog.json

# CSV output format
python generate_md_catalog.py --format csv --output-file catalog.csv
```

### 7. Document Retriever (`retrieve_md_documents.py`)

Searches the catalog and retrieves relevant Markdown documents based on user queries using semantic similarity.

**Features:**

- Two-stage retrieval: catalog matching + semantic similarity
- Uses sentence transformers for semantic understanding
- Weighted scoring combining metadata and content similarity
- Detailed breakdown of matches (title, section, keyword)
- Fallback to basic similarity if embeddings fail
- Command-line interface with customizable parameters
- Saves results to JSON for auditing

**Usage:**

```bash
# Basic usage
python retrieve_md_documents.py --query "startup booth tariff"

# Custom parameters
python retrieve_md_documents.py --catalog catalog.json --md-folder ./markdown_files --query "speaker registration" --top-k 5

# Different model
python retrieve_md_documents.py --query "conference agenda" --model all-mpnet-base-v2
```

### 8. Embeddings Generator (`generate_embeddings.py`)

Generates embeddings for all Markdown files to enable fast semantic search in the Q&A API.

**Features:**

- Uses sentence transformers for high-quality embeddings
- Processes all markdown files in batch
- Saves embeddings to pickle file for fast loading
- Provides progress tracking and statistics
- Optimized for the Q&A API performance

**Usage:**

```bash
python generate_embeddings.py
```

### 9. Q&A API (`qa_api.py`)

FastAPI service that combines document retrieval with OpenAI GPT-3.5 for intelligent question answering.

**Features:**

- Semantic document retrieval using embeddings
- OpenAI GPT-3.5 integration for intelligent answers
- Similarity threshold filtering (>0.5)
- Token usage tracking and cost estimation
- Comprehensive logging and auditing
- Fallback retrieval methods
- Health check and statistics endpoints
- CORS support for web frontend

**Usage:**

```bash
# Set OpenAI API key in .env file
echo "OPENAI_API_KEY=your-api-key-here" > .env

# Generate embeddings first
python generate_embeddings.py

# Start the API server
python -m uvicorn qa_api:app --host 0.0.0.0 --port 8000 --reload
```

**API Endpoints:**

- `POST /ask` - Ask a question and get an answer
- `GET /health` - Health check
- `GET /stats` - Service statistics
- `GET /docs` - Interactive API documentation

**Example Request:**

```bash
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "What is the startup booth tariff for BTS 2025?"}'
```

### 10. Chatbot UI

Two versions of the modern web-based chatbot interface that connects to the Q&A API:

#### HTML Version (`chatbot.html`)

**Features:**

- Floating chat widget with modern design
- Real-time conversation interface
- Displays relevant documents used for answers
- Shows token usage and cost information
- Responsive design for mobile and desktop
- Typing indicators and error handling
- Clean, professional UI similar to Intercom/Crisp
- Standalone HTML/CSS/JS - no framework required

**Usage:**

1. Start the FastAPI server:

   ```bash
   python -m uvicorn qa_api:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Open `chatbot.html` in your web browser

3. Click the chat button (💬) to start a conversation

#### React Version (`ChatbotWidget.jsx`)

**Features:**

- Same features as HTML version
- React component for easy integration
- State management with hooks
- Reusable component design
- TypeScript-friendly structure

**Usage:**

1. Install React dependencies:

   ```bash
   npm install react react-dom
   ```

2. Import and use the component:

   ```jsx
   import ChatbotWidget from "./ChatbotWidget";
   import "./ChatbotWidget.css";

   function App() {
     return (
       <div>
         <h1>Your App</h1>
         <ChatbotWidget />
       </div>
     );
   }
   ```

3. Start the FastAPI server and your React app

### 11. Setup Script (`setup_chatbot.py`)

Automated setup script to configure the chatbot environment.

**Features:**

- Checks Python version compatibility
- Installs missing dependencies
- Creates and configures .env file
- Validates data files existence
- Starts the server automatically

**Usage:**

```bash
python setup_chatbot.py
```

### 12. Dashboard (`dashboard.html`)

Comprehensive monitoring dashboard for chatbot interactions and analytics.

**Features:**

- **Real-time Statistics**: Total interactions, tokens used, costs, response times
- **Interaction History**: Complete log of all Q&A interactions with details
- **Token Usage Analytics**: Visual charts showing daily token consumption
- **Cost Tracking**: Monitor OpenAI API costs over time
- **Document Usage**: See which documents are most frequently referenced
- **Advanced Filtering**: Filter by date range, token count, cost thresholds
- **Auto-refresh**: Updates every 30 seconds automatically
- **Responsive Design**: Works on desktop and mobile devices

**Usage:**

1. Start the FastAPI server:

   ```bash
   python -m uvicorn qa_api:app --host 0.0.0.0 --port 8000 --reload
   ```

2. Open the dashboard:

   ```bash
   python launch_dashboard.py
   ```

   Or manually open `dashboard.html` in your browser

**Dashboard Sections:**

- **Statistics Cards**: Overview of key metrics
- **Recent Interactions**: Detailed view of all Q&A sessions
- **Token Usage Chart**: Visual trend of daily token consumption
- **Filters Panel**: Advanced filtering options

**API Endpoints Used:**

- `GET /stats` - Overall statistics
- `GET /interactions` - Interaction history with pagination
- `GET /analytics` - Detailed analytics data

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Complete Workflow

1. **Extract URLs:**

   ```bash
   python url_fetcher.py
   ```

   This creates `urls.txt` with all website URLs.

2. **Download HTML Files:**

   ```bash
   python html_fetcher.py
   ```

   This downloads all HTML content to the `html_files/` folder.

3. **Clean HTML Files:**

   ```bash
   python html_cleaner.py
   ```

   This cleans the HTML files and saves them to the `cleaned_html_files/` folder.

4. **Convert to Markdown:**

   ```bash
   python html_to_markdown.py
   ```

   This converts cleaned HTML files to Markdown format and saves them to the `markdown_files/` folder.

5. **Analyze Token Counts:**

   ```bash
   python token_counter.py
   ```

   This analyzes token counts and generates statistics for all Markdown files.

6. **Generate Content Catalog:**

   ```bash
   python generate_md_catalog.py
   ```

   This creates a metadata catalog to help identify content and topics across all files.

7. **Retrieve Relevant Documents:**

   ```bash
   python retrieve_md_documents.py --query "your search query"
   ```

   This searches the catalog and retrieves the most relevant documents for your query.

8. **Generate Embeddings:**

   ```bash
   python generate_embeddings.py
   ```

   This creates embeddings for fast semantic search in the Q&A API.

9. **Start Q&A API:**

   ```bash
   # Set OpenAI API key in .env file
   echo "OPENAI_API_KEY=your-api-key" > .env

   # Start the API server
   python -m uvicorn qa_api:app --host 0.0.0.0 --port 8000 --reload
   ```

   This starts the FastAPI service for intelligent question answering.

10. **Use the Chatbot UI:**

    - Open `chatbot.html` in your web browser
    - Click the chat button to start a conversation
    - Ask questions about the Bengaluru Tech Summit

11. **Monitor with Dashboard:**
    - Run `python launch_dashboard.py` to open the dashboard
    - Monitor interactions, token usage, and costs
    - Analyze performance and document usage patterns

## Output

- `urls.txt` - Contains all URLs found on the website
- `html_files/` - Folder containing all downloaded HTML files
- `cleaned_html_files/` - Folder containing cleaned HTML files
- `markdown_files/` - Folder containing converted Markdown files
- `token_analysis_report.txt` - Detailed token analysis report
- `catalog.json` - Metadata catalog of all Markdown files
- `retrieval_results.json` - Search results from document retrieval
- `markdown_embeddings.pkl` - Pre-computed embeddings for semantic search
- `chatbot_qa_log.jsonl` - Q&A interaction logs for auditing
- `chatbot.html` - Modern web chatbot interface
- `setup_chatbot.py` - Automated setup script
- `dashboard.html` - Comprehensive monitoring dashboard
- `launch_dashboard.py` - Dashboard launcher script

## Example Output

**urls.txt:**

```
https://bengalurutechsummit.com/BTS-Demo-2025/index.php
https://bengalurutechsummit.com/BTS-Demo-2025/about.php
https://bengalurutechsummit.com/BTS-Demo-2025/contact.php
...
```

**html_files/ folder:**

```
html_files/
├── index.html
├── about.html
├── contact.html
└── ...
```
 