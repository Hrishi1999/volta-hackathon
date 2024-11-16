import React, { useState } from 'react';
import { Send, X } from 'lucide-react';

interface ChatPromptProps {
  onSubmit: (prompt: string) => void;
  onClose: () => void;
}

export default function ChatPrompt({ onSubmit, onClose }: ChatPromptProps) {
  const [prompt, setPrompt] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (prompt.trim()) {
      onSubmit(prompt);
      setPrompt('');
    }
  };

  return (
    <div className="border-t border-gray-700 bg-gray-800 p-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-sm font-medium">New Flow Prompt</h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
      <form onSubmit={handleSubmit} className="flex space-x-2">
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter your prompt..."
          className="flex-1 p-2 rounded-lg bg-gray-700 border border-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          autoFocus
        />
        <button
          type="submit"
          className="p-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white"
        >
          <Send className="w-5 h-5" />
        </button>
      </form>
    </div>
  );
}