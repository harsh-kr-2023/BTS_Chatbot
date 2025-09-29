import React from "react";
import ChatbotWidget from "./ChatbotWidget";
import "./App.css";

function App() {
  return (
    <div className="App">
      <div className="demo-container">
        <h1>Bengaluru Tech Summit</h1>
        <p>
          Ask me anything about the event! Click the chat button to get started.
        </p>
      </div>

      <ChatbotWidget />
    </div>
  );
}

export default App;
