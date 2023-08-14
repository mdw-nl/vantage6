import { Injectable } from '@angular/core';
import { ApiService } from './api.service';
import { Pagination } from '../models/api/pagination.model';
import { BaseOrganization } from '../models/api/organization.model';
import { BaseCollaboration, Collaboration, CollaborationLazyProperties } from '../models/api/Collaboration.model';

@Injectable({
  providedIn: 'root'
})
export class CollaborationService {
  constructor(private apiService: ApiService) {}

  async getCollaborations(): Promise<BaseCollaboration[]> {
    const result = await this.apiService.getForApi<Pagination<BaseCollaboration>>('/collaboration');
    return result.data;
  }

  async getCollaboration(id: string, lazyProperties: CollaborationLazyProperties[] = []): Promise<Collaboration> {
    const result = await this.apiService.getForApi<BaseCollaboration>(`/collaboration/${id}`);

    const collaboration: Collaboration = { ...result, organizations: [] };

    lazyProperties.forEach(async (lazyProperty) => {
      const resultProperty = await this.apiService.getForApi<Pagination<BaseOrganization>>(result[lazyProperty]);
      collaboration[lazyProperty] = resultProperty.data;
    });

    return collaboration;
  }
}
