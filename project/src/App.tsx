import React, { useState } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import BlockList from './components/BlockList';
import FlowList from './components/FlowList';

function App() {
  const [activeTab, setActiveTab] = useState('blocks');

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
        <main className="flex-1 overflow-auto">
          {activeTab === 'blocks' ? <BlockList /> : <FlowList />}
        </main>
      </div>
    </div>
  );
}

export default App;