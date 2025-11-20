"""
React Streaming Client Example

This example shows how to consume the streaming API from a React application.
It demonstrates progressive rendering of scraping results as tokens arrive.

Installation:
    npm install react

Usage:
    Import this component into your React app and use:
    <StreamingScraper />
"""

import React, { useState } from 'react';

const StreamingScraper = () => {
  const [url, setUrl] = useState('https://example.com');
  const [prompt, setPrompt] = useState('What is this page about?');
  const [result, setResult] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);

  const handleStreamingScrape = async () => {
    setResult('');
    setError(null);
    setIsStreaming(true);

    try {
      const response = await fetch('http://localhost:8000/scrape/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: url,
          prompt: prompt,
          model: 'openai/gpt-4'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Read the stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        // Decode the chunk
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete message in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));

            // Handle different event types
            if (data.event === 'complete') {
              setIsStreaming(false);
              // Could show final result differently
              console.log('Complete result:', data.result);
            } else if (data.event === 'error') {
              setError(data.error);
              setIsStreaming(false);
            } else if (data.token) {
              // Append token to result
              setResult(prev => prev + data.token);
            }
          }
        }
      }

      setIsStreaming(false);
    } catch (err) {
      setError(err.message);
      setIsStreaming(false);
    }
  };

  const handleNonStreamingScrape = async () => {
    setResult('');
    setError(null);
    setIsStreaming(true);

    try {
      const response = await fetch('http://localhost:8000/scrape', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: url,
          prompt: prompt,
          model: 'openai/gpt-4'
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setResult(JSON.stringify(data.result, null, 2));
      setIsStreaming(false);
    } catch (err) {
      setError(err.message);
      setIsStreaming(false);
    }
  };

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
      <h1>🕷️ ScrapeGraphAI Streaming Demo</h1>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px' }}>
          URL to Scrape:
        </label>
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          style={{ width: '100%', padding: '8px', fontSize: '14px' }}
          placeholder="https://example.com"
        />
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'block', marginBottom: '5px' }}>
          Prompt:
        </label>
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ width: '100%', padding: '8px', fontSize: '14px' }}
          placeholder="What is this page about?"
        />
      </div>

      <div style={{ marginBottom: '20px', display: 'flex', gap: '10px' }}>
        <button
          onClick={handleStreamingScrape}
          disabled={isStreaming}
          style={{
            padding: '10px 20px',
            backgroundColor: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isStreaming ? 'not-allowed' : 'pointer',
            fontSize: '14px'
          }}
        >
          {isStreaming ? '🔄 Streaming...' : '▶️ Stream Results'}
        </button>

        <button
          onClick={handleNonStreamingScrape}
          disabled={isStreaming}
          style={{
            padding: '10px 20px',
            backgroundColor: '#2196F3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isStreaming ? 'not-allowed' : 'pointer',
            fontSize: '14px'
          }}
        >
          {isStreaming ? '⏳ Loading...' : '⚡ Get Results (No Stream)'}
        </button>
      </div>

      {error && (
        <div style={{
          padding: '15px',
          backgroundColor: '#ffebee',
          color: '#c62828',
          borderRadius: '4px',
          marginBottom: '20px'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <div style={{
        backgroundColor: '#f5f5f5',
        padding: '15px',
        borderRadius: '4px',
        minHeight: '200px',
        fontFamily: 'monospace',
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word'
      }}>
        <strong>Result:</strong>
        <div style={{ marginTop: '10px' }}>
          {result || (isStreaming ? 'Waiting for tokens...' : 'No results yet. Click a button to start.')}
          {isStreaming && <span className="cursor">▋</span>}
        </div>
      </div>

      <style jsx>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
        .cursor {
          animation: blink 1s infinite;
          color: #4CAF50;
        }
      `}</style>
    </div>
  );
};

export default StreamingScraper;
