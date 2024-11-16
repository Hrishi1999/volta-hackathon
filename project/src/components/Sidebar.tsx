import React from 'react';
import { Boxes, GitBranch } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <div className="w-64 bg-gray-800 text-white h-full">
      <nav className="p-4">
        <button
          onClick={() => onTabChange('blocks')}
          className={`w-full flex items-center space-x-2 p-3 rounded-lg mb-2 ${
            activeTab === 'blocks' ? 'bg-blue-600' : 'hover:bg-gray-700'
          }`}
        >
          <Boxes className="w-5 h-5" />
          <span>Blocks</span>
        </button>
        <button
          onClick={() => onTabChange('flows')}
          className={`w-full flex items-center space-x-2 p-3 rounded-lg ${
            activeTab === 'flows' ? 'bg-blue-600' : 'hover:bg-gray-700'
          }`}
        >
          <GitBranch className="w-5 h-5" />
          <span>Flows</span>
        </button>
      </nav>
    </div>
  );
}