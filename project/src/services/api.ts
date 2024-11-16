import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Block {
  id: string;
  name: string;
  url: string;
  actions: string;
}

export interface Flow {
  id: string;
  name: string;
  description: string;
  status?: string;
  actions: string;
  messages?: Message[];
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export interface ApiError {
  message: string;
  status: number;
}

const handleApiError = (error: unknown): never => {
  if (axios.isAxiosError(error)) {
    const apiError: ApiError = {
      message: error.response?.data?.detail || 'An error occurred',
      status: error.response?.status || 500,
    };
    throw apiError;
  }
  throw new Error('An unexpected error occurred');
};

export const blocksApi = {
  create: async (data: { name: string; url: string; actions: string }) => {
    try {
      const response = await api.post('/blocks/', data);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  list: async () => {
    try {
      const response = await api.get('/blocks/');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  get: async (id: string) => {
    try {
      const response = await api.get(`/blocks/${id}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};

export const flowsApi = {
  create: async (data: { name: string; description: string; action_configs: string }) => {
    try {
      const response = await api.post('/flows/', data);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  list: async () => {
    try {
      const response = await api.get('/flows/');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  get: async (id: string) => {
    try {
      const response = await api.get(`/flows/${id}`);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  createFromPrompt: async (prompt: string, initialInputs?: Record<string, any>) => {
    try {
      const response = await api.post('/flows/new/from-prompt/execute', {
        prompt,
        initial_inputs: initialInputs,
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  execute: async (flowId: string, initialInputs: Record<string, any>) => {
    try {
      const response = await api.post(`/flows/${flowId}/execute`, {
        initial_inputs: initialInputs,
      });
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  getPending: async () => {
    try {
      const response = await api.get('/flows/pending');
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
  
  continue: async (flowId: string, inputs: Record<string, any>) => {
    try {
      const response = await api.post(`/flows/${flowId}/continue`, inputs);
      return response.data;
    } catch (error) {
      handleApiError(error);
    }
  },
};