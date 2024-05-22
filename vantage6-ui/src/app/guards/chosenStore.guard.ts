import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { routePaths } from '../routes';
import { CHOSEN_ALGORITHM_STORE } from '../models/constants/sessionStorage';

export function chosenStoreGuard(): CanActivateFn {
  return async () => {
    const router: Router = inject(Router);

    const chosenStore = sessionStorage.getItem(CHOSEN_ALGORITHM_STORE);
    if (!chosenStore) {
      router.navigate([routePaths.stores]);
      return false;
    }
    return true;
  };
}
