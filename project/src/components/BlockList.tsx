import { Box, Plus } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { blocksApi } from "../services/api";
import NewBlockDialog from "./NewBlockDialog";

interface BlockType {
  _id: string;
  name: string;
  type: string;
  url: string;
  created_at: string;
  updated_at: string;
  _highlights?: {
    url: string;
  }[];
  _score?: number;
}

export default function BlockList() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: blocks = [], isLoading } = useQuery<BlockType[]>(
    "blocks",
    blocksApi.list
  );

  const createBlockMutation = useMutation(blocksApi.create, {
    onSuccess: () => {
      queryClient.invalidateQueries("blocks");
      setIsDialogOpen(false);
    },
  });

  const handleSaveBlock = (block: {
    name: string;
    url: string;
    actions: string;
  }) => {
    createBlockMutation.mutate({
      name: block.name,
      url: block.url,
      actions: block.actions,
    });
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-gray-500">Loading blocks...</div>
      </div>
    );
  }

  return (
    <div className="h-full relative">
      <div className="flex justify-between items-center p-4 border-b border-gray-700">
        <h2 className="text-xl font-semibold">Blocks</h2>
        <button
          onClick={() => setIsDialogOpen(true)}
          className="p-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white flex items-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span>New Block</span>
        </button>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {blocks.map((block) => (
          <div
            key={block._id}
            className="p-4 rounded-lg bg-gray-800 border border-gray-700 hover:border-blue-500 transition-colors"
          >
            <div className="flex items-center space-x-2 mb-2">
              <Box className="w-5 h-5 text-blue-400" />
              <h3 className="font-semibold">{block.name}</h3>
            </div>
            <p className="text-sm text-gray-400 mb-2">{block.url}</p>
            <div className="flex flex-wrap gap-2">
              <span className="px-2 py-1 text-xs rounded-full bg-gray-700 text-gray-300">
                {block.type}
              </span>
            </div>
          </div>
        ))}
      </div>

      <NewBlockDialog
        isOpen={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onSave={handleSaveBlock}
        isLoading={createBlockMutation.isLoading}
      />
    </div>
  );
}
