from dotenv import load_dotenv
import os
import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Any, Dict
import re
import json
from datetime import datetime, date, time, timedelta
from pymysql.cursors import DictCursor
import google.generativeai as genai
import markdown as md
from llm_layer import LLMManager  # Use LLMManager directly, avoid circular import
from rapidfuzz import process as rapidfuzz_process

# Load environment variables from .env file
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file or environment.")
genai.configure(api_key=GEMINI_API_KEY)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "chatbot")

app = FastAPI(
    title="BTS Structured Q&A API",
    description="Ask questions about speakers and sessions using LLM-generated SQL.",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static directory
app.mount("/", StaticFiles(directory=".", html=True), name="static")

class AskDBRequest(BaseModel):
    question: str

class AskDBResponse(BaseModel):
    answer: str
    sql: str
    rows_returned: int

SPEAKER_SCHEMA = """
Table: speakers
id (int, primary key)
name (varchar)
photo (varchar)
banner (varchar)
designation (varchar)
linkedin_profile (varchar)
speaker_order (int)
"""

SESSION_SCHEMA = """
Table: sessions
id (int, primary key)
day (int)
sector (varchar)
session_topic (varchar)
subtopic (varchar)
start_time (time)
end_time (time)
speaker_ids (varchar) → comma-separated speaker IDs
speaker_roles (varchar)
"""

MAX_ROWS = 10
LOG_FILE = 'chatbot_qa_log.jsonl'

def log_db_interaction(question, answer, sql, sql_result, tokens_sql, tokens_answer):
    try:
        # Use getattr for OpenAI usage objects (v1.x)
        def safe_usage(u, prefix=""):
            if not u:
                return {}
            return {
                f"{prefix}prompt_tokens": getattr(u, "prompt_tokens", 0),
                f"{prefix}completion_tokens": getattr(u, "completion_tokens", 0),
                f"{prefix}total_tokens": getattr(u, "total_tokens", 0),
                f"{prefix}approx_cost_usd": getattr(u, "approx_cost_usd", 0.0),
            }
        tokens_sql_dict = safe_usage(tokens_sql, "sql_")
        tokens_answer_dict = safe_usage(tokens_answer, "answer_")
        total_tokens = tokens_sql_dict.get("sql_total_tokens", 0) + tokens_answer_dict.get("answer_total_tokens", 0)
        approx_cost_usd = tokens_sql_dict.get("sql_approx_cost_usd", 0.0) + tokens_answer_dict.get("answer_approx_cost_usd", 0.0)
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'question': question,
            'answer': answer,
            'sql': sql,
            'sql_result_summary': str(sql_result)[:500],
            'tokens_used': {
                **tokens_sql_dict,
                **tokens_answer_dict,
                'total_tokens': total_tokens,
                'approx_cost_usd': approx_cost_usd
            }
        }
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print('[ERROR] Logging DB interaction failed:', e)

def call_llm_with_fallback_sql(prompt, llm_order=None, min_length=10, forbidden_phrases=None):
    if llm_order is None:
        llm_order = [os.getenv("DEFAULT_LLM", "gemini"), "openai", "perplexity"]
    forbidden_phrases = forbidden_phrases or ["[MOCK ANSWER]", "not available", "no gemini api key"]
    all_attempts = []
    llm = LLMManager()
    for model in llm_order:
        try:
            response = llm.generate_content(prompt, model=model)
            text = getattr(response, 'text', str(response))
            llm_details = {k: v for k, v in response.__dict__.items() if k != 'text'} if hasattr(response, '__dict__') else {}
            all_attempts.append({"llm": model, "text": text, "details": llm_details})
            if not text or len(text.strip()) < min_length:
                continue
            if any(phrase.lower() in text.lower() for phrase in forbidden_phrases):
                continue
            return text, model, llm_details, all_attempts
        except Exception as e:
            all_attempts.append({"llm": model, "error": str(e)})
            continue
    if all_attempts:
        last = all_attempts[-1]
        return last.get("text", "[No valid LLM answer]"), last.get("llm", "none"), last.get("details", {}), all_attempts
    return "[No valid LLM answer]", "none", {}, all_attempts

def get_llm_sql(question: str) -> tuple[str, dict, str, dict, list]:
    prompt = f"""
You are an expert MySQL assistant for the Bengaluru Tech Summit database.

Here are the relevant table schemas:

{SPEAKER_SCHEMA}
{SESSION_SCHEMA}

IMPORTANT:
- The speaker_ids column in the sessions table contains comma-separated **IDs** of speakers, not names.
- To find sessions for a specific speaker by name, you must join the speakers and sessions tables, and use FIND_IN_SET(speakers.id, sessions.speaker_ids).
- When filtering by speaker name, always use a case-insensitive partial match: WHERE LOWER(speakers.name) LIKE LOWER('%[name]%').
- Do NOT try to match a speaker's name in the speaker_ids column.
- Carefully analyze the user's question and infer their intent.
- Map names, topics, dates, and other details in the question to the appropriate columns.
- Only add filters to the SQL WHERE clause if the user clearly specifies them.
- If the question is broad or ambiguous, return the most relevant results with LIMIT 10.
- Always include LIMIT 10 unless the user requests more.
- Explain your reasoning in a SQL comment, then output only the SQL below it.

User question: "{question}"
"""
    try:
        print("[DEBUG] LLM SQL prompt:\n", prompt)
        text, llm_used, llm_details, all_attempts = call_llm_with_fallback_sql(prompt, min_length=10)
        sql = text.strip() if text else ""
        print(f"[DEBUG] LLM SQL response from {llm_used}:", sql)
        # Post-process: If the SQL tries to match a name in speaker_ids, rewrite it
        name_in_speaker_ids = re.search(r"speaker_ids\s+LIKE\s+['\"]%(.+?)%['\"]", sql, re.IGNORECASE)
        if name_in_speaker_ids:
            speaker_name = name_in_speaker_ids.group(1)
            # Rewrite the query to join speakers and sessions using FIND_IN_SET and LIKE
            fixed_sql = f"SELECT s.day, s.sector, s.session_topic, s.subtopic, s.start_time, s.end_time\nFROM sessions AS s\nJOIN speakers AS sp ON FIND_IN_SET(sp.id, s.speaker_ids)\nWHERE LOWER(sp.name) LIKE LOWER('%{speaker_name}%')\nLIMIT 10;"
            print(f"[DEBUG] Rewriting SQL to use speaker ID join and LIKE for name '{speaker_name}':\n{fixed_sql}")
            sql = fixed_sql
        # Also, replace any = 'name' with LIKE for speaker name
        sql = re.sub(r"sp.name\s*=\s*'([^']+)'", r"LOWER(sp.name) LIKE LOWER('%\1%')", sql)
        sql = re.sub(r"speakers.name\s*=\s*'([^']+)'", r"LOWER(speakers.name) LIKE LOWER('%\1%')", sql)
        return sql, llm_details, llm_used, llm_details, all_attempts
    except Exception as e:
        print("[ERROR] LLM SQL generation failed:", e)
        return "", {}, "none", {}, []

def strip_sql_comments(sql: str) -> str:
    # Remove block comments
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # Remove single-line comments
    sql = '\n'.join(line for line in sql.splitlines() if not line.strip().startswith('--'))
    return sql.strip()

def run_sql_query(sql: str) -> List[Dict[str, Any]]:
    # Strip comments before checking and executing
    sql_clean = strip_sql_comments(sql)
    if not sql_clean.lower().strip().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=DictCursor
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql_clean)
            rows = cursor.fetchall()
        if isinstance(rows, list):
            return rows
        return list(rows)
    except Exception as e:
        print(f"[ERROR] SQL execution failed: {e}")
        print(f"[ERROR] SQL: {sql_clean}")
        raise
    finally:
        connection.close()

def fetch_speakers_by_ids(speaker_ids: list) -> list:
    if not speaker_ids:
        return []
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=DictCursor
    )
    try:
        with connection.cursor() as cursor:
            format_strings = ','.join(['%s'] * len(speaker_ids))
            cursor.execute(f"SELECT * FROM speakers WHERE id IN ({format_strings})", tuple(speaker_ids))
            rows = cursor.fetchall()
            if isinstance(rows, list):
                return rows
            return list(rows)
    finally:
        connection.close()

def fetch_speakers_for_sessions(sessions: list) -> list:
    # For each session, fetch all speakers for its speaker_ids
    session_speaker_data = []
    for session in sessions:
        speaker_ids = session.get('speaker_ids', '')
        ids = [str(i).strip() for i in speaker_ids.split(',') if i.strip().isdigit()]
        speakers = fetch_speakers_by_ids(ids) if ids else []
        session_speaker_data.append({
            'session': session,
            'speakers': speakers
        })
    return session_speaker_data

def get_daywise_speakers_sql():
    # Returns up to 6 speakers per day
    return """
    SELECT s.day, sp.name, sp.designation, sp.linkedin_profile
    FROM sessions AS s
    JOIN speakers AS sp ON FIND_IN_SET(sp.id, s.speaker_ids)
    ORDER BY s.day, sp.name
    """

def format_html_answer(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p>No results found for your question.</p>"
    # Group speakers by day
    from collections import defaultdict
    day_speakers = defaultdict(list)
    for row in rows:
        day = row.get('day', 'N/A')
        day_speakers[day].append(row)
    # If all days are N/A, just show a flat list
    if set(day_speakers.keys()) == {'N/A', None, ''} or all((d is None or d == 'N/A' or d == '') for d in day_speakers.keys()):
        html = "<ul>"
        for row in rows:
            html += "<li><strong>Name:</strong> {}<br></li>".format(row.get("name", "N/A"))
        html += "</ul>"
        html += "<p><em>Here are the speakers for your query. Let me know if you want details about a specific person!</em></p>"
        return html
    html = ""
    for day, speakers in sorted(day_speakers.items()):
        if day is None or day == 'N/A' or day == '':
            continue
        html += f"<h4>Day {day} Speakers</h4><ul>"
        for i, row in enumerate(speakers):
            if i >= 6:
                break
            html += "<li>"
            html += "<strong>Name:</strong> {}<br>".format(row.get("name", "N/A"))
            if row.get("designation"):
                html += "<strong>Designation:</strong> {}<br>".format(row["designation"])
            if row.get("linkedin_profile"):
                html += '<strong>LinkedIn:</strong> <a href="{}" target="_blank">Profile</a><br>'.format(row["linkedin_profile"])
            html += "</li>"
        html += "</ul>"
    html += "<p><em>Here are the speakers for each day. Let me know if you want details about a specific person!</em></p>"
    return html

def format_session_html_answer(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "<p>No sessions found for your query.</p>"
    html = "<ul>"
    for row in rows:
        html += "<li>"
        if row.get("session_topic"):
            html += f"<strong>Session:</strong> {row['session_topic']}<br>"
        if row.get("day"):
            html += f"<strong>Day:</strong> {row['day']}<br>"
        if row.get("sector"):
            html += f"<strong>Sector:</strong> {row['sector']}<br>"
        if row.get("start_time") and row.get("end_time"):
            html += f"<strong>Time:</strong> {row['start_time']} - {row['end_time']}<br>"
        if row.get("subtopic"):
            html += f"<strong>Subtopic:</strong> {row['subtopic']}<br>"
        html += "</li>"
    html += "</ul>"
    html += "<p><em>Here are the sessions for your query. Let me know if you want details about a specific session!</em></p>"
    return html

def make_json_safe(obj):
    if isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(v) for v in obj]
    elif isinstance(obj, (datetime, date, time, timedelta)):
        return str(obj)
    else:
        return obj

def get_llm_friendly_answer(question: str, session_speaker_data: list) -> tuple[str, dict]:
    # Always send the full structure to the LLM for session queries
    safe_data = make_json_safe(session_speaker_data)
    prompt = f"""
You are an expert assistant for the Bengaluru Tech Summit.
Given the following user question and session data, generate a friendly, detailed HTML answer.

Formatting instructions:
- Use only one <strong> or <p> for the main title/introduction (e.g., <p><strong>Bengaluru Tech Summit Sessions - Day 1</strong></p>).
- For each session, use <p><strong>Session: [session name]</strong></p> (no headers like <h2>, <h3>, <h4>).
- List session details and speakers using <ul>/<li>.
- Use <strong> for session titles, speaker names, and roles, but not for every detail.
- Avoid using any <h2>, <h3>, <h4> tags.
- Keep the output visually clean, minimal, and not overwhelming.
- Do NOT show any session or speaker IDs in your answer.
- If a truncation note is present, add a friendly message at the end inviting the user to ask for more details or visit the official website.

User question: {question}
Session data (JSON):
{json.dumps(safe_data, indent=2)}
"""
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        answer = response.text.strip() if hasattr(response, 'text') and response.text else ""
        usage = {}
        return answer, usage
    except Exception as e:
        print("[ERROR] Gemini answer generation failed:", e)
        return "<p>Sorry, there was a problem generating a friendly answer. Here is the raw result:</p><pre>" + str(session_speaker_data) + "</pre>", {}

# Add helper to fetch full session(s) by session_topic or id

def fetch_sessions_by_ids(session_ids: list) -> list:
    if not session_ids:
        return []
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=DictCursor
    )
    try:
        with connection.cursor() as cursor:
            format_strings = ','.join(['%s'] * len(session_ids))
            cursor.execute(f"SELECT * FROM sessions WHERE id IN ({format_strings})", tuple(session_ids))
            rows = cursor.fetchall()
            if isinstance(rows, list):
                return rows
            return list(rows)
    finally:
        connection.close()

def fetch_sessions_by_topic(topics: list) -> list:
    if not topics:
        return []
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=DictCursor
    )
    try:
        with connection.cursor() as cursor:
            format_strings = ' OR '.join(['session_topic = %s'] * len(topics))
            sql = f"SELECT * FROM sessions WHERE {format_strings}"
            cursor.execute(sql, tuple(topics))
            rows = cursor.fetchall()
            if isinstance(rows, list):
                return rows
            return list(rows)
    finally:
        connection.close()

# Add intent detection helper

def detect_intent(question: str) -> str:
    q = question.lower()
    if ("speaker" in q or "panelist" in q) and ("session" in q or "talk" in q or "which" in q or "who" in q):
        return "speaker_session"  # mapping or specific speaker in session
    elif "speaker" in q or "panelist" in q:
        return "speaker"
    elif "session" in q or "talk" in q or "agenda" in q or "schedule" in q:
        return "session"
    else:
        return "unknown"

def clean_llm_answer(answer: str) -> str:
    import re
    # Extract content from code block if present
    code_block_match = re.search(r'```[a-zA-Z]*\s*([\s\S]*?)```', answer)
    if code_block_match:
        answer = code_block_match.group(1)
    # Remove any remaining code block markers
    answer = re.sub(r'^```[a-zA-Z]*\s*', '', answer.strip())
    answer = re.sub(r'```$', '', answer.strip())
    # Remove markdown bold (**text**) and italic (*text*)
    answer = re.sub(r'\*\*([^*]+)\*\*', r'\1', answer)
    answer = re.sub(r'\*([^*]+)\*', r'\1', answer)
    # Remove stray asterisks
    answer = re.sub(r'\*', '', answer)
    return answer.strip()

def markdown_to_html(text: str) -> str:
    return md.markdown(text, extensions=['extra', 'sane_lists'])

def fetch_all_speaker_names() -> list:
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=DictCursor
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM speakers")
            rows = cursor.fetchall()
            return [row['name'] for row in rows]
    finally:
        connection.close()

@app.post("/ask_db", response_model=AskDBResponse)
async def ask_db(request: AskDBRequest):
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        # Force use of day-wise speakers SQL for relevant questions
        if "day wise speaker" in question.lower() or "day-wise speaker" in question.lower() or ("speakers" in question.lower() and "day" in question.lower()):
            sql = get_daywise_speakers_sql()
            usage_sql = {}
            llm_used = "manual_rule"
            llm_details = {}
            llm_attempts = []
        else:
            sql, usage_sql, llm_used, llm_details, llm_attempts = get_llm_sql(question)
    except Exception as e:
        print(f"[ERROR] SQL generation failed: {e}")
        return AskDBResponse(
            answer="<p>Sorry, there was a problem generating the SQL query. Please try again later.</p>",
            sql="",
            rows_returned=0
        )
    if "NO_SQL_POSSIBLE" in (sql or ""):
        doc_response = await LLMManager().answer_question(question)
        return AskDBResponse(
            answer=doc_response.answer,
            sql="NO_SQL_POSSIBLE",
            rows_returned=0
        )
    try:
        sql_clean = re.sub(r'^```sql|```$', '', sql or '', flags=re.MULTILINE)
        if sql_clean is not None:
            sql_clean = sql_clean.strip()
        else:
            sql_clean = ""
        sql_statements = [stmt.strip() for stmt in sql_clean.split(';') if stmt.strip()]
        if not sql_statements:
            raise ValueError("No valid SQL statement found.")
        first_sql = sql_statements[0]
        print(f"[DEBUG] Executing SQL: {first_sql}")
        rows = run_sql_query(first_sql)

        # Intent detection
        intent = detect_intent(question)

        # --- Speaker only ---
        if intent == "speaker":
            if rows:
                html = format_html_answer(rows)
                html = clean_llm_answer(html)
                html = markdown_to_html(html)
                log_db_interaction(question, html, first_sql, rows, usage_sql, {})
                return AskDBResponse(
                    answer=html,
                    sql=first_sql,
                    rows_returned=len(rows)
                )
            else:
                # Fuzzy match: try to find the closest speaker name
                all_names = fetch_all_speaker_names()
                from rapidfuzz import fuzz
                user_name = None
                # Try to extract the name from the SQL or question
                name_match = re.search(r"LIKE LOWER\('%(.+?)%\)'", first_sql)
                if name_match:
                    user_name = name_match.group(1)
                else:
                    # Fallback: try to extract from question
                    qwords = request.question.split()
                    for w in qwords:
                        if len(w) > 3:
                            user_name = w
                            break
                if user_name:
                    best_match, score, _ = rapidfuzz_process.extractOne(user_name, all_names, scorer=fuzz.ratio)
                    if score >= 80:
                        # Rerun the query for the best match
                        fixed_sql = re.sub(r"LIKE LOWER\('%(.+?)%\)'", f"LIKE LOWER('%{best_match}%')", first_sql)
                        print(f"[DEBUG] Fuzzy match rerun for '{user_name}' → '{best_match}' (score {score}): {fixed_sql}")
                        rows = run_sql_query(fixed_sql)
                        if rows:
                            html = format_html_answer(rows)
                            html = clean_llm_answer(html)
                            html = markdown_to_html(html)
                            log_db_interaction(request.question, html, fixed_sql, rows, usage_sql, {})
                            return AskDBResponse(
                                answer=f"<p>Did you mean: <strong>{best_match}</strong>?</p>" + html,
                                sql=fixed_sql,
                                rows_returned=len(rows)
                            )
                return AskDBResponse(
                    answer="<p>No speakers found for your query.</p>",
                    sql=first_sql,
                    rows_returned=0
                )
        # --- Session only ---
        elif intent == "session":
            if rows:
                html = format_session_html_answer(rows)
                html = clean_llm_answer(html)
                html = markdown_to_html(html)
                log_db_interaction(question, html, first_sql, rows, usage_sql, {})
                return AskDBResponse(
                    answer=html,
                    sql=first_sql,
                    rows_returned=len(rows)
                )
            else:
                return AskDBResponse(
                    answer="<p>No sessions found for your query.</p>",
                    sql=first_sql,
                    rows_returned=0
                )
        # --- General fallback ---
        if rows:
            # If the result contains session_topic, use session formatting
            if any("session_topic" in row for row in rows):
                html = format_session_html_answer(rows)
            else:
                html = format_html_answer(rows)
            html = clean_llm_answer(html)
            html = markdown_to_html(html)
            log_db_interaction(question, html, first_sql, rows, usage_sql, {})
            return AskDBResponse(
                answer=html,
                sql=first_sql,
                rows_returned=len(rows)
            )
        else:
            return AskDBResponse(
                answer="<p>No results found for your query.</p>",
                sql=first_sql,
                rows_returned=0
            )
    except Exception as e:
        print(f"[ERROR] Exception in ask_db: {e}")
        print(f"[ERROR] SQL: {sql}")
        return AskDBResponse(
            answer="<p>Sorry, there was a problem executing the SQL query. Please try again later.</p>",
            sql=sql,
            rows_returned=0
        ) 