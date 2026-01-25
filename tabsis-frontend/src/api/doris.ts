import axios from 'axios';

// Base API url: dev may be full URL, prod uses /api (via nginx proxy)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ExecuteRequest {
  action: string;
  table?: string;
  column?: string;
  params?: Record<string, any>;
}

export interface LLMConfigRequest {
  resource_name: string;
  provider_type: string;
  endpoint: string;
  model_name: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ProjectLLMConfig {
  provider_type: string;
  endpoint: string;
  model_name: string;
  api_key?: string;
  temperature?: number;
  max_tokens?: number;
}

export interface NaturalQueryRequest {
  query: string;
  api_key?: string;
  model?: string;
  base_url?: string;
  project_id?: number;
}

export const dorisApi = {
  // Health
  health: () => api.get('/health'),

  // Tables
  getTables: (projectId?: number) => api.get('/tables', { params: { project_id: projectId } }),
  getTableSchema: (tableName: string, projectId?: number) =>
    api.get(`/tables/${tableName}/schema`, { params: { project_id: projectId } }),

  // Actions
  execute: (data: ExecuteRequest) => api.post('/execute', data),

  // Excel
  previewExcel: (file: File, rows: number = 10) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('rows', rows.toString());
    return api.post('/upload/preview', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  uploadExcel: (file: File, tableName: string, columnMapping?: Record<string, string>, createTable: boolean = true) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('table_name', tableName);
    if (columnMapping) {
      formData.append('column_mapping', JSON.stringify(columnMapping));
    }
    formData.append('create_table', createTable.toString());
    return api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Doris LLM resources (global)
  llm: {
    create: (data: LLMConfigRequest) => api.post('/llm/config', data),
    list: () => api.get('/llm/config'),
    test: (resourceName: string) => api.post(`/llm/config/${resourceName}/test`),
    delete: (resourceName: string) => api.delete(`/llm/config/${resourceName}`),
  },

  // Project-scoped LLM config
  projectLlm: {
    get: (projectId: number) => api.get(`/projects/${projectId}/llm-config`),
    save: (projectId: number, data: ProjectLLMConfig) => api.put(`/projects/${projectId}/llm-config`, data),
    test: (projectId: number, data: ProjectLLMConfig) => api.post(`/projects/${projectId}/llm-config/test`, data),
    delete: (projectId: number) => api.delete(`/projects/${projectId}/llm-config`),
  },

  projectPrompt: {
    get: (projectId: number) => api.get(`/projects/${projectId}/agent-prompt`),
    save: (projectId: number, prompt: string) => api.put(`/projects/${projectId}/agent-prompt`, { prompt }),
    reset: (projectId: number) => api.delete(`/projects/${projectId}/agent-prompt`),
  },

  resetProjectDb: (projectId: number, clearUploads: boolean = true) =>
    api.post(`/projects/${projectId}/reset-db`, null, { params: { clear_uploads: clearUploads } }),

  // Natural language query
  naturalQuery: (data: NaturalQueryRequest) => api.post('/query/natural', data),
};
