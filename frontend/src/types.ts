export interface DefinitionParam {
  name: string;
  type: string;
  required?: boolean;
  default?: any;
  description?: string | null;
}

export interface DefinitionItem {
  category: string;
  type: string;
  summary: string;
  params?: DefinitionParam[];
}

export interface Run {
  id: string;
  name: string;
  status: string;
  progress?: number;
  message?: string | null;
  updated_at?: string;
}
