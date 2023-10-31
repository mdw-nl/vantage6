import { Component, OnDestroy } from '@angular/core';
import { FormBuilder, Validators } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { MatDialog } from '@angular/material/dialog';

import { PASSWORD_VALIDATORS } from 'src/app/validators/passwordValidators';
import { createCompareValidator } from 'src/app/validators/compare.validator';
import { MessageDialog } from 'src/app/components/dialogs/message-dialog/message-dialog.component';
import { TranslateService } from '@ngx-translate/core';
import { Router } from '@angular/router';
import { routePaths } from 'src/app/routes';
import { AuthService } from 'src/app/services/auth.service';
import { createUnEqualValidator } from 'src/app/validators/unequal.validator';

@Component({
  selector: 'app-change-password',
  templateUrl: './change-password.component.html',
  styleUrls: ['./change-password.component.scss'],
  host: { '[class.card-container]': 'true' }
})
export class ChangePasswordComponent implements OnDestroy {
  destroy$ = new Subject();
  form = this.fb.nonNullable.group(
    {
      oldPassword: ['', [Validators.required]],
      newPassword: ['', [Validators.required, ...PASSWORD_VALIDATORS]],
      newPasswordRepeat: ['', [Validators.required]]
    },
    { validators: [createCompareValidator('newPassword', 'newPasswordRepeat'), createUnEqualValidator('oldPassword', 'newPassword')] }
  );

  constructor(
    private fb: FormBuilder,
    private router: Router,
    private dialog: MatDialog,
    private translateService: TranslateService,
    private authService: AuthService
  ) {}

  ngOnDestroy(): void {
    this.destroy$.next(true);
  }

  async handleSubmit(): Promise<void> {
    if (this.form.valid) {
      this.authService.changePassword(this.form.controls.oldPassword.value, this.form.controls.newPassword.value);

      const dialogRef = this.dialog.open(MessageDialog, {
        data: {
          title: this.translateService.instant('change-password.success-dialog.title'),
          content: this.translateService.instant('change-password.success-dialog.message'),
          confirmButtonText: this.translateService.instant('general.close'),
          confirmButtonType: 'primary'
        }
      });

      dialogRef
        .afterClosed()
        .pipe(takeUntil(this.destroy$))
        .subscribe(() => {
          this.goToPreviousPage();
        });
      // TODO handle errors
    }
  }

  handleCancel(): void {
    this.goToPreviousPage();
  }

  private goToPreviousPage(): void {
    //TODO: Navigate to profile page
    this.router.navigate([routePaths.start]);
  }
}
