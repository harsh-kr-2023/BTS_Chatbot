import sys
import os
import json
import pickle
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv
import requests
import ask_db_api
import asyncio
from rapidfuzz import process
from llm_layer import LLMManager

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Markdown Q&A API",
    description="API for answering questions using local Markdown documents and Gemini Pro",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the ask_db_api FastAPI app inside the main app so /ask_db is available on the same server.
app.mount("/ask_db", ask_db_api.app)

# In-memory conversation context (for demo; use Redis or DB for production)
conversation_context = {}

# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    session_id: str = None  # Optional session/user ID for context tracking

class DocumentInfo(BaseModel):
    filename: str
    similarity_score: float

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    approx_cost_usd: float

class QuestionResponse(BaseModel):
    answer: str
    top_documents: List[DocumentInfo]
    tokens_used: TokenUsage

def correct_typos_in_query(query: str) -> str:
    # Only correct obvious typos, do not change or add words unless they are clear misspellings
    canonical_terms = [
        "speaker", "speakers", "session", "sessions", "conference", "schedule", "panelist", "agenda", "talk", "panel", "day"
    ]
    words = query.split()
    corrected_words = []
    for word in words:
        match, score, _ = process.extractOne(word, canonical_terms)
        # Only correct if the word is a very close typo (score >= 95), otherwise leave unchanged
        if score >= 95:
            corrected_words.append(match)
        else:
            corrected_words.append(word)
    return " ".join(corrected_words)

class QAService:
    def __init__(self):
        self.catalog_file = 'catalog.json'
        self.md_folder = 'markdown_files'
        self.log_file = 'chatbot_qa_log.jsonl'
        self.catalog = []
        self.db_info = {}
        self.llm = LLMManager()
        self.max_context_tokens = 12000
        self.initialize_service()

    def initialize_service(self):
        try:
            self.load_catalog()
            logger.info("QA Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize QA service: {e}")
            raise

    def load_catalog(self):
        try:
            if os.path.exists(self.catalog_file):
                with open(self.catalog_file, 'r', encoding='utf-8') as f:
                    catalog_obj = json.load(f)
                self.db_info = catalog_obj.get('db_info', {})
                self.catalog = catalog_obj.get('pages', [])
                logger.info(f"Loaded catalog with {len(self.catalog)} pages and db_info.")
            else:
                logger.warning(f"Catalog file {self.catalog_file} not found")
                self.catalog = []
                self.db_info = {}
        except Exception as e:
            logger.error(f"Error loading catalog: {e}")
            self.catalog = []
            self.db_info = {}

    def call_llm_with_fallback(self, prompt, llm_order=None, min_length=30, forbidden_phrases=None, **kwargs):
        """
        Try LLMs in order, fallback if answer is unsatisfactory (error, mock, too short, or forbidden phrase).
        Returns: (answer_text, llm_used, llm_details, all_attempts)
        """
        if llm_order is None:
            llm_order = [self.llm.default_llm, "openai", "perplexity"]
        forbidden_phrases = forbidden_phrases or ["[MOCK ANSWER]", "not available", "no gemini api key"]
        all_attempts = []
        for model in llm_order:
            try:
                response = self.llm.generate_content(prompt, model=model)
                text = getattr(response, 'text', str(response))
                llm_details = {k: v for k, v in response.__dict__.items() if k != 'text'} if hasattr(response, '__dict__') else {}
                all_attempts.append({"llm": model, "text": text, "details": llm_details})
                # Check for forbidden phrases or too short/empty
                if not text or len(text.strip()) < min_length:
                    continue
                if any(phrase.lower() in text.lower() for phrase in forbidden_phrases):
                    continue
                return text, model, llm_details, all_attempts
            except Exception as e:
                all_attempts.append({"llm": model, "error": str(e)})
                continue
        # If all fail, return last attempt (or a fallback message)
        if all_attempts:
            last = all_attempts[-1]
            return last.get("text", "[No valid LLM answer]"), last.get("llm", "none"), last.get("details", {}), all_attempts
        return "[No valid LLM answer]", "none", {}, all_attempts

    def llm_select_top_pages(self, question: str, top_k: int = 3, prev_user: str = None, prev_bot: str = None) -> dict:
        try:
            context_intro = ""
            if prev_user and prev_bot:
                context_intro = f"Previous user message: {prev_user}\nPrevious system answer: {prev_bot}\nCurrent user message: {question}\n"
            pages_str = json.dumps(self.catalog, ensure_ascii=False, indent=2)
            llm_prompt = f"""
You are an expert assistant for the Bengaluru Tech Summit Q&A system.
{context_intro}
Here is a catalog of pages, each with a filename and a summary:
{pages_str}

User question: "{question}"

Instructions:
- Return the top {top_k} most relevant page filenames for the user's question.
- Set db_call_needed to true only if the question is about speakers or sessions at the event. Otherwise, set it to false.
- Handle typos, fuzzy words, and synonyms naturally.

Return your answer as a JSON object with two fields:
- top_filenames: a list of the top {top_k} filenames (strings)
- db_call_needed: true or false
"""
            text, llm_used, llm_details, all_attempts = self.call_llm_with_fallback(llm_prompt, min_length=10)
            import re
            import ast
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                json_str = match.group(0)
                try:
                    result = json.loads(json_str)
                except Exception:
                    result = ast.literal_eval(json_str)
                if "top_filenames" in result and "db_call_needed" in result:
                    result["llm_used"] = llm_used
                    result["llm_details"] = llm_details
                    result["llm_attempts"] = all_attempts
                    return result
            try:
                result = ast.literal_eval(text)
                if "top_filenames" in result and "db_call_needed" in result:
                    result["llm_used"] = llm_used
                    result["llm_details"] = llm_details
                    result["llm_attempts"] = all_attempts
                    return result
            except Exception:
                pass
            logger.warning("LLM did not return valid JSON, using fallback.")
            return {"top_filenames": [entry['filename'] for entry in self.catalog[:top_k]], "db_call_needed": False, "llm_used": llm_used, "llm_details": llm_details, "llm_attempts": all_attempts}
        except Exception as e:
            logger.error(f"Error in LLM-based catalog selection: {e}")
            return {"top_filenames": [entry['filename'] for entry in self.catalog[:top_k]], "db_call_needed": False, "llm_used": "none", "llm_details": {}, "llm_attempts": []}

    def load_document_content(self, filename: str) -> str:
        try:
            file_path = os.path.join(self.md_folder, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return ""

    def truncate_context(self, documents: List[Dict[str, Any]]) -> str:
        context_parts = []
        total_tokens = 0
        for doc in documents:
            content = doc.get('content', '')
            if not content:
                content = self.load_document_content(doc['filename'])
            estimated_tokens = len(content) // 4
            if total_tokens + estimated_tokens <= self.max_context_tokens:
                context_parts.append(f"--- {doc['filename']} ---\n{content}\n")
                total_tokens += estimated_tokens
            else:
                remaining_tokens = self.max_context_tokens - total_tokens
                max_chars = remaining_tokens * 4
                truncated_content = content[:max_chars] + "..."
                context_parts.append(f"--- {doc['filename']} (truncated) ---\n{truncated_content}\n")
                break
        return "\n".join(context_parts)

    def call_gemini(self, question: str, context: str, prev_user: str = None, prev_bot: str = None, llm_model: str = None) -> Dict[str, Any]:
        try:
            context_intro = ""
            if prev_user and prev_bot:
                context_intro = f"Previous user message: {prev_user}\nPrevious system answer: {prev_bot}\nCurrent user message: {question}\n"
            prompt = f"""You are a helpful assistant for the Bengaluru Tech Summit.\n{context_intro}\nAnswer the user's question in a natural, conversational way using the information provided below.\n\nCRITICAL INSTRUCTIONS:\n- Always start your answer with a brief, friendly introduction or summary before presenting any lists or bullet points.\n- After the list, add a short, helpful note or explanation if appropriate.\n- Provide human-like, conversational responses - NOT raw markdown content\n- Match the question to the relevant information in the context\n- Format your answer in a clean, readable way that's easy to understand\n- Use HTML formatting for better readability:\n  * Use <ul><li> for bullet points and lists\n  * For any structured data (such as price lists, tariffs, or tables), use <ul><li> with <strong> for labels and values, or use <div> blocks for clarity\n  * Align values and labels clearly, and avoid plain text for structured data\n  * Use <strong> for emphasis on important information\n  * Use <br> for line breaks when needed\n  * Use <p> for paragraphs\n- Avoid complex markdown tables - use simple HTML formatting instead\n- Do NOT include ANY URLs, links, or website references\n- Do NOT include registration links or external website mentions\n- Do NOT mention \"context\", \"provided documents\", or \"based on the information\"\n- If information is not available, clearly state what you don't know\n- Keep responses concise but informative\n\nAvailable Information:\n{context}\n\nQuestion: {question}\n\nPlease provide a natural, conversational answer with proper HTML formatting, especially for any structured or tabular data:"""
            text, llm_used, llm_details, all_attempts = self.call_llm_with_fallback(prompt, min_length=30)
            return {
                'answer': text,
                'prompt_tokens': llm_details.get('prompt_tokens', 0),
                'completion_tokens': llm_details.get('completion_tokens', 0),
                'total_tokens': llm_details.get('total_tokens', 0),
                'approx_cost_usd': llm_details.get('approx_cost_usd', 0.0),
                'llm_used': llm_used,
                'llm_details': llm_details,
                'llm_attempts': all_attempts
            }
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return self.get_mock_response(question, context)

    def get_mock_response(self, question: str, context: str) -> Dict[str, Any]:
        return {
            'answer': f"[MOCK ANSWER] No Gemini API key set. Question: {question}",
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_tokens': 0,
            'approx_cost_usd': 0.0
        }

    def log_interaction(self, question: str, answer: str, documents: List, tokens: Dict, llm_used: str = None, llm_details: dict = None):
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'question': question,
                'answer': answer,
                'documents': [doc['filename'] for doc in documents],
                'tokens_used': tokens,
                'llm_used': llm_used,
                'llm_details': llm_details or {}
            }
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")

    async def answer_question(self, question: str, session_id: str = None, llm_model: str = None) -> QuestionResponse:
        corrected_question = correct_typos_in_query(question)
        try:
            logger.info(f"Processing question: {question} (corrected: {corrected_question})")
            prev_user = None
            prev_bot = None
            if session_id and session_id in conversation_context:
                prev_user = conversation_context[session_id].get('user')
                prev_bot = conversation_context[session_id].get('bot')
            # Step 1: Use LLM to select top pages and DB call decision
            logger.info("Step 1: LLM-based catalog selection...")
            llm_result = self.llm_select_top_pages(corrected_question, top_k=3, prev_user=prev_user, prev_bot=prev_bot)
            top_filenames = llm_result.get("top_filenames", [])
            db_call_needed = llm_result.get("db_call_needed", False)
            llm_used = llm_result.get("llm_used", "none")
            llm_details = llm_result.get("llm_details", {})
            llm_attempts = llm_result.get("llm_attempts", [])
            logger.info(f"LLM selected files: {top_filenames}, db_call_needed: {db_call_needed}, LLM used: {llm_used}")
            if db_call_needed:
                logger.info("Routing to database Q&A as per LLM decision.")
                import ask_db_api
                db_req = ask_db_api.AskDBRequest(question=corrected_question)
                db_resp = await ask_db_api.ask_db(db_req)
                # Save context for follow-up
                if session_id:
                    conversation_context[session_id] = {'user': corrected_question, 'bot': str(db_resp)}
                # Log DB interaction as well
                self.log_interaction(
                    corrected_question,
                    str(db_resp.answer),
                    [],
                    {},
                    llm_used='database',
                    llm_details={'source': 'ask_db_api'}
                )
                return db_resp
            # Step 2: Load content for top files
            logger.info("Step 2: Loading document content...")
            documents = []
            for fname in top_filenames:
                content = self.load_document_content(fname)
                documents.append({
                    'filename': fname,
                    'similarity_score': 1.0,
                    'content': content
                })
            # Step 3: Create context
            logger.info("Step 3: Creating context...")
            context = self.truncate_context(documents)
            logger.info(f"Context created, length: {len(context)} characters")
            # Step 4: Call LLM
            logger.info("Step 4: Calling LLM API...")
            model = llm_model or self.llm.default_llm
            import time
            start_time = time.time()
            llm_response = self.call_gemini(corrected_question, context, prev_user=prev_user, prev_bot=prev_bot, llm_model=model)
            elapsed = time.time() - start_time
            logger.info("LLM API call completed")
            # Step 5: Prepare response
            logger.info("Step 5: Preparing response...")
            response = QuestionResponse(
                answer=llm_response['answer'],
                top_documents=[
                    DocumentInfo(
                        filename=doc['filename'],
                        similarity_score=doc['similarity_score']
                    )
                    for doc in documents
                ],
                tokens_used=TokenUsage(
                    prompt_tokens=llm_response.get('prompt_tokens', 0),
                    completion_tokens=llm_response.get('completion_tokens', 0),
                    total_tokens=llm_response.get('total_tokens', 0),
                    approx_cost_usd=llm_response.get('approx_cost_usd', 0.0)
                )
            )
            # Step 6: Log interaction
            logger.info("Step 6: Logging interaction...")
            self.log_interaction(
                corrected_question, 
                llm_response['answer'],
                documents, 
                {
                    'prompt_tokens': llm_response.get('prompt_tokens', 0),
                    'completion_tokens': llm_response.get('completion_tokens', 0),
                    'total_tokens': llm_response.get('total_tokens', 0),
                    'approx_cost_usd': llm_response.get('approx_cost_usd', 0.0)
                },
                llm_used=llm_used,
                llm_details={
                    'elapsed_time_sec': round(elapsed, 2),
                    'llm_response_meta': {k: v for k, v in llm_response.items() if k != 'answer'},
                    'llm_attempts': llm_attempts
                }
            )
            if session_id:
                conversation_context[session_id] = {'user': corrected_question, 'bot': llm_response['answer']}
            logger.info(f"Successfully answered question. Used {len(documents)} documents.")
            return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Initialize QA service
qa_service = QAService()

@app.post("/ask_auto")
async def ask_auto(request: QuestionRequest):
    """
    Automatically route questions to appropriate Q&A system using LLM-based decision
    """
    try:
        logger.info(f"Processing auto-routed question: {request.question}")
        response = await qa_service.answer_question(request.question, session_id=request.session_id)
        logger.info("Auto Q&A completed successfully")
        return response
    except Exception as e:
        logger.error(f"Unexpected error in ask_auto: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    Answer a question using local markdown documents and Gemini Pro
    """
    try:
        logger.info(f"Processing direct question: {request.question}")
        response = await qa_service.answer_question(request.question, session_id=request.session_id)
        logger.info("Direct Q&A completed successfully")
        return response
    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "catalog_loaded": len(qa_service.catalog) > 0,
        "gemini_configured": qa_service.llm.default_llm is not None
    }

@app.get("/stats")
async def get_stats():
    try:
        stats = {
            "total_interactions": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_response_time": 0.0
        }
        if os.path.exists(qa_service.log_file):
            with open(qa_service.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                stats["total_interactions"] = len(lines)
                for line in lines:
                    try:
                        data = json.loads(line.strip())
                        tokens = data.get('tokens_used', {})
                        stats["total_tokens"] += tokens.get('total_tokens', 0)
                        stats["total_cost"] += tokens.get('approx_cost_usd', 0.0)
                    except json.JSONDecodeError:
                        continue
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

@app.get("/interactions")
async def get_interactions(limit: int = 50, offset: int = 0):
    try:
        interactions = []
        if os.path.exists(qa_service.log_file):
            with open(qa_service.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()[offset:offset+limit]
                for line in lines:
                    try:
                        data = json.loads(line.strip())
                        interactions.append(data)
                    except json.JSONDecodeError:
                        continue
        return {"interactions": interactions}
    except Exception as e:
        logger.error(f"Error getting interactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get interactions") 