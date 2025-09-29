import React, { useState, useRef, useEffect } from "react";
import "./ChatbotWidget.css";

const ChatbotWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      type: "bot",
      content:
        "👋 Welcome! I'm here to help you with information about the Bengaluru Tech Summit. Ask me anything about registration, schedules, speakers, or general information!",
      timestamp: new Date(),
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const API_BASE_URL = "http://localhost:8000";

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const toggleChatbot = () => {
    setIsOpen(!isOpen);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const sendMessage = async () => {
    const message = inputValue.trim();
    if (!message || isLoading) return;

    // Add user message
    const userMessage = {
      type: "user",
      content: message,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/ask_auto`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question: message }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Add bot response with details
      const botMessage = {
        type: "bot",
        content: data.answer,
        documents: data.top_documents || [],
        tokens: data.tokens_used || null,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error("Error:", error);
      const errorMessage = {
        type: "error",
        content: "Sorry, something went wrong. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTokenUsage = (tokens) => {
    if (!tokens) return null;
    return (
      <div className="token-usage">
        <strong>Token Usage:</strong>
        <br />
        Prompt: <span>{tokens.prompt_tokens}</span> | Completion:{" "}
        <span>{tokens.completion_tokens}</span> | Total:{" "}
        <span>{tokens.total_tokens}</span>
        <br />
        Cost: <span>${tokens.approx_cost_usd.toFixed(3)}</span>
      </div>
    );
  };

  const formatDocuments = (documents) => {
    if (!documents || documents.length === 0) return null;
    return (
      <div className="documents-used">
        <h4>📄 Relevant Documents Used:</h4>
        {documents.map((doc, index) => (
          <div key={index} className="document-item">
            {doc.filename} (score: {doc.similarity_score.toFixed(2)})
          </div>
        ))}
      </div>
    );
  };

  const renderMessage = (message, index) => {
    const isUser = message.type === "user";
    const isError = message.type === "error";

    return (
      <div key={index} className={`message ${message.type}`}>
        <div
          className={`message-content ${isError ? "error" : ""}`}
          dangerouslySetInnerHTML={{ __html: message.content }}
        />
        {message.documents && formatDocuments(message.documents)}
        {message.tokens && formatTokenUsage(message.tokens)}
      </div>
    );
  };

  return (
    <div className="chatbot-widget">
      <button className="chatbot-toggle" onClick={toggleChatbot}>
        💬
      </button>

      <div className={`chatbot-window ${isOpen ? "active" : ""}`}>
        <div className="chatbot-header">
          <h3>Bengaluru Tech Summit Assistant</h3>
          <button className="chatbot-close" onClick={toggleChatbot}>
            ×
          </button>
        </div>

        <div className="chatbot-messages">
          {messages.map(renderMessage)}

          {isLoading && (
            <div className="typing-indicator active">
              <div className="typing-dots">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="chatbot-input">
          <div className="input-container">
            <textarea
              ref={inputRef}
              className="message-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your question here..."
              rows="1"
              disabled={isLoading}
            />
            <button
              className="send-button"
              onClick={sendMessage}
              disabled={isLoading || !inputValue.trim()}
            >
              ➤
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatbotWidget;
