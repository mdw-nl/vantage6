import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { Organization } from 'src/app/models/api/organization.model';
import { RoleForm } from 'src/app/models/api/role.model';
import { Rule, Rule_ } from 'src/app/models/api/rule.model';

@Component({
  selector: 'app-role-form',
  templateUrl: './role-form.component.html',
  styleUrls: ['./role-form.component.scss']
})
export class RoleFormComponent {
  @Input() selectableRules: Rule[] = [];
  @Input() organizations: Organization[] = [];
  @Output() cancelled: EventEmitter<void> = new EventEmitter();
  @Output() submitted: EventEmitter<RoleForm> = new EventEmitter();

  constructor(private fb: FormBuilder) {}

  form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    description: '',
    organization_id: [0, [Validators.required]]
  });

  selectedRules: number[] = [];

  handleSubmit() {
    if (this.form.valid) {
      this.submitted.emit({ ...this.form.getRawValue(), rules: this.selectedRules });
    }
  }

  handleCancel() {
    this.cancelled.emit();
  }

  handleChangedSelection(rules: Rule_[]): void {
    // we know that these are vantage6 server rules, not store rules here
    rules = rules as Rule[];
    this.selectedRules = rules ? rules.map((rule) => rule.id) : [];
  }

  get submitDisabled(): boolean {
    return this.selectedRules?.length === 0;
  }
}
