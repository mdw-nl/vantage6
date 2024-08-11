import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { routePaths } from 'src/app/routes';
import { CHOSEN_COLLABORATION, IS_CHOSEN_COLLAB_ENCRYPTED, CHOSEN_COLLAB_PRIVATE_KEY } from 'src/app/models/constants/sessionStorage';

export function chosenCollaborationGuard(): CanActivateFn {
  return async () => {
    const router: Router = inject(Router);

    const chosenCollaboration = sessionStorage.getItem(CHOSEN_COLLABORATION);
    if (!chosenCollaboration) {
      router.navigate([routePaths.chooseCollaboration]);
      return false;
    }
    const encryptionStatus = sessionStorage.getItem(IS_CHOSEN_COLLAB_ENCRYPTED);
    const privateKey = sessionStorage.getItem(CHOSEN_COLLAB_PRIVATE_KEY);
    if (encryptionStatus === 'true' && !privateKey) {
      router.navigate([routePaths.keyUpload]);
      return false;
    }
    return true;
  };
}
