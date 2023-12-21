import { AlgorithmStore } from '../algorithmStore.model';
import { BaseNode } from './node.model';
import { BaseOrganization } from './organization.model';
import { BaseTask } from './task.models';

export enum CollaborationLazyProperties {
  Organizations = 'organizations',
  Nodes = 'nodes',
  Tasks = 'tasks',
  AlgorithmStores = 'algorithm_stores'
}

export enum CollaborationSortProperties {
  ID = 'id',
  Name = 'name'
}

export interface GetCollaborationParameters {
  organization_id?: string;
  sort?: CollaborationSortProperties;
}

export interface BaseCollaboration {
  id: number;
  name: string;
  encrypted: boolean;
  organizations: string;
  nodes: string;
  tasks: string;
  algorithm_stores: string;
}

export interface Collaboration {
  id: number;
  name: string;
  encrypted: boolean;
  organizations: BaseOrganization[];
  nodes: BaseNode[];
  tasks: BaseTask[];
  algorithm_stores: AlgorithmStore[];
}

export interface CollaborationForm {
  name: string;
  encrypted: boolean;
  organization_ids: number[];
  registerNodes: boolean;
}

export type CollaborationCreate = Pick<CollaborationForm, 'name' | 'encrypted' | 'organization_ids'>;
