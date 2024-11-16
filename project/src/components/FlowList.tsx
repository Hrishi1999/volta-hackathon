import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { Plus, GitBranch } from 'lucide-react';
import { flowsApi, Flow } from '../services/api';
import ChatPrompt from './ChatPrompt';

export default function FlowList() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [selectedFlow, setSelectedFlow] = useState<Flow | null>(null);
  const queryClient = useQueryClient();

  const { data: flows = [], isLoading } = useQuery<Flow[]>('flows', flowsApi.list);

  const createFlowMutation = useMutation(
    (prompt: string) => flowsApi.createFromPrompt(prompt),
    {
      onSuccess: (newFlow) => {
        queryClient.invalidateQueries('flows');
        setSelectedFlow(newFlow);
      },
    }
  );

  const handleChatSubmit = async (prompt: string) => {
    createFlowMutation.mutate(prompt);
  };

  const handleFlowSelect = (flow: Flow) => {
    setSelectedFlow(flow);
    setIsChatOpen(false);
  };

  // Poll for pending flows
  useEffect(() => {
    const interval = setInterval(async () => {
      if (selectedFlow?.status === 'pending_input') {
        const updatedFlow = await flowsApi.get(selectedFlow.id);
        setSelectedFlow(updatedFlow);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [selectedFlow]);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-500">Loading flows...</div>
      </div>
    );
  }

  return (
    <div className="h-full flex">
      {/* Main content area for output */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 p-6 overflow-auto">
          {selectedFlow ? (
            <div className="space-y-4">
              {selectedFlow.messages?.map((message, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg ${
                    message.role === 'user'
                      ? 'bg-gray-800 ml-12'
                      : 'bg-gray-700 mr-12'
                  }`}
                >
                  <div className="flex items-center space-x-2 mb-2">
                    <span className="text-xs font-medium text-gray-400">
                      {message.role === 'user' ? 'You' : 'Assistant'}
                    </span>
                  </div>
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                </div>
              ))}
              {selectedFlow.status === 'pending_input' && (
                <div className="bg-yellow-900 p-4 rounded-lg">
                  <p className="text-yellow-200">Waiting for additional input...</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-gray-500 mt-8">
              Select a flow to view the conversation or create a new one
            </div>
          )}
        </div>
        
        {/* Chat prompt at bottom */}
        <div className="mt-auto">
          {isChatOpen ? (
            <ChatPrompt
              onSubmit={handleChatSubmit}
              onClose={() => setIsChatOpen(false)}
              isLoading={createFlowMutation.isLoading}
            />
          ) : (
            <div className="p-4 border-t border-gray-700">
              <button
                onClick={() => setIsChatOpen(true)}
                className="w-full p-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center space-x-2"
                disabled={createFlowMutation.isLoading}
              >
                <Plus className="w-5 h-5" />
                <span>New Flow</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Right panel for flow list */}
      <div className="w-80 border-l border-gray-700 bg-gray-800 overflow-auto">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-xl font-semibold">Flows</h2>
        </div>
        <div className="p-4 space-y-3">
          {flows.map((flow) => (
            <div
              key={flow.id}
              onClick={() => handleFlowSelect(flow)}
              className={`p-3 rounded-lg border ${
                selectedFlow?.id === flow.id
                  ? 'bg-blue-600 border-blue-500'
                  : 'bg-gray-900 border-gray-700 hover:border-blue-500'
              } transition-colors cursor-pointer`}
            >
              <div className="flex items-center space-x-2 mb-1">
                <GitBranch className="w-4 h-4 text-blue-400" />
                <h3 className="font-semibold">{flow.name}</h3>
              </div>
              <p className="text-sm text-gray-400">{flow.description}</p>
              {flow.status === 'pending_input' && (
                <span className="inline-block px-2 py-1 mt-2 text-xs rounded-full bg-yellow-600 text-yellow-100">
                  Waiting for input
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}