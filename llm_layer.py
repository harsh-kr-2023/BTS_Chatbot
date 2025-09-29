import os
from dotenv import load_dotenv
import logging

load_dotenv()

# Gemini
try:
    import google.generativeai as genai
except ImportError:
    genai = None

# OpenAI
try:
    import openai
except ImportError:
    openai = None

# Perplexity (uses OpenAI-compatible API)
try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

class LLMManager:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        self.default_llm = os.getenv("DEFAULT_LLM", "gemini")
        self.llm_threshold = float(os.getenv("LLM_THRESHOLD", "0.7"))
        self._init_clients()

    def _init_clients(self):
        self.gemini_model = None
        if self.gemini_api_key and genai:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        if self.openai_api_key and openai:
            openai.api_key = self.openai_api_key
        # Perplexity uses OpenAI-compatible API endpoint
        # Add other LLMs here as needed

    def generate_content(self, prompt, model=None, **kwargs):
        model = model or self.default_llm
        if model == "gemini":
            return self._call_gemini(prompt, **kwargs)
        elif model == "openai":
            return self._call_openai(prompt, **kwargs)
        elif model == "perplexity":
            return self._call_perplexity(prompt, **kwargs)
        # Add more elifs for other LLMs
        else:
            raise ValueError(f"Unknown LLM model: {model}")

    def _call_gemini(self, prompt, **kwargs):
        if not self.gemini_model:
            logger.warning("Gemini model not initialized or API key missing.")
            return type('Obj', (object,), {'text': '[Gemini not available]'})()
        response = self.gemini_model.generate_content(prompt)
        return response

    def _call_openai(self, prompt, **kwargs):
        if not openai or not self.openai_api_key:
            logger.warning("OpenAI not available or API key missing.")
            return type('Obj', (object,), {'text': '[OpenAI not available]'})()
        # Default to gpt-3.5-turbo
        model_name = kwargs.get('openai_model', 'gpt-3.5-turbo')
        completion = openai.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get('temperature', 0.7),
            max_tokens=kwargs.get('max_tokens', 1024)
        )
        # Mimic Gemini's .text
        return type('Obj', (object,), {'text': completion.choices[0].message.content})()

    def _call_perplexity(self, prompt, **kwargs):
        if not httpx or not self.perplexity_api_key:
            logger.warning("Perplexity not available or API key missing.")
            return type('Obj', (object,), {'text': '[Perplexity not available]'})()
        # Perplexity API is OpenAI-compatible, but uses a different endpoint
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.perplexity_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": kwargs.get('perplexity_model', 'pplx-70b-online'),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get('temperature', 0.7),
            "max_tokens": kwargs.get('max_tokens', 1024)
        }
        try:
            resp = httpx.post(url, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            return type('Obj', (object,), {'text': result['choices'][0]['message']['content']})()
        except Exception as e:
            logger.warning(f"Perplexity API error: {e}")
            return type('Obj', (object,), {'text': '[Perplexity error]'})()

    # Stub for future LLMs
    def _call_anthropic(self, prompt, **kwargs):
        # Add Anthropic/Claude support here
        return type('Obj', (object,), {'text': '[Anthropic not implemented]'})()

    def _call_mistral(self, prompt, **kwargs):
        # Add Mistral support here
        return type('Obj', (object,), {'text': '[Mistral not implemented]'})()

class LLMProvider:
    def ask(self, prompt):
        raise NotImplementedError

class OpenAIProvider(LLMProvider):
    def ask(self, prompt):
        # Implement OpenAI API call here
        return "OpenAI response (mock)"

class LocalModelProvider(LLMProvider):
    def ask(self, prompt):
        # Implement local model inference here
        return "Local model response (mock)"

def get_llm_provider():
    provider = os.getenv("LLM_PROVIDER", "openai")
    if provider == "openai":
        return OpenAIProvider()
    elif provider == "local":
        return LocalModelProvider()
    else:
        raise ValueError("Unknown LLM provider")

# Example usage:
# llm = get_llm_provider()
# answer = llm.ask("Your question here")