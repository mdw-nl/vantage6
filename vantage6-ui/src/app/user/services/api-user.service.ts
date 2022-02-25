import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { Rule } from 'src/app/rule/interfaces/rule';
import { User } from 'src/app/user/interfaces/user';

import { environment } from 'src/environments/environment';
import { getIdsFromArray } from 'src/app/shared/utils';
import { ApiRoleService } from 'src/app/role/services/api-role.service';
import { ApiRuleService } from 'src/app/rule/services/api-rule.service';
import { ConvertJsonService } from 'src/app/shared/services/convert-json.service';
import { ApiService } from 'src/app/shared/services/api.service';
import { ResType } from 'src/app/shared/enum';
import { ModalService } from 'src/app/modal/modal.service';

// TODO this service is quite different from the other API services
// See to it that this is standardized somewhat, e.g. by obtaining the Rules
// from elsewhere
@Injectable({
  providedIn: 'root',
})
export class ApiUserService extends ApiService {
  all_rules: Rule[] = [];

  constructor(
    protected http: HttpClient,
    private roleService: ApiRoleService,
    private ruleService: ApiRuleService,
    private convertJsonService: ConvertJsonService,
    protected modalService: ModalService
  ) {
    super(ResType.USER, http, modalService);
    this.setup();
  }

  async setup(): Promise<void> {
    this.all_rules = await this.ruleService.getAllRules();
  }

  list(organization_id: number | null = null) {
    let params: any = {};
    if (organization_id !== null) {
      params['organization_id'] = organization_id;
    }
    return this.http.get(environment.api_url + '/user', { params: params });
  }

  get_data(user: User): any {
    let data: any = {
      username: user.username,
      email: user.email,
      firstname: user.first_name,
      lastname: user.last_name,
      organization_id: user.organization_id,
      roles: getIdsFromArray(user.roles),
      rules: getIdsFromArray(user.rules),
    };
    if (user.password) {
      data.password = user.password;
    }
    return data;
  }

  async getUserJson(id: number): Promise<any> {
    // TODO remove this func
    return await this.get(id).toPromise();
  }

  async getUser(id: number): Promise<User> {
    let user_json = await this.get(id).toPromise();

    let role_ids: number[] = [];
    if (user_json.roles) {
      role_ids = getIdsFromArray(user_json.roles);
    }
    let roles = await this.roleService.getRoles(role_ids);

    return this.convertJsonService.getUser(user_json, roles, this.all_rules);
  }
}
