import { Binary } from 'lucide-react';

export default function Header() {
  return (
    <header className="bg-gray-900 text-white p-4 border-b border-gray-700">
      <div className="flex items-center space-x-2">
        <Binary className="w-6 h-6 text-blue-400" />
        <h1 className="text-xl font-bold">DoIt</h1>
      </div>
    </header>
  );
}