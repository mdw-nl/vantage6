import { Component, OnInit } from '@angular/core';

import { AuthService } from '../services/auth.service';
// import { TokenStorageService } from '../services/token-storage.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss'],
})
export class LoginComponent implements OnInit {
  form: any = {
    username: null,
    password: null,
  };
  isLoggedIn = false;
  isLoginFailed = false;
  errorMessage = '';

  // TODO count number of times login failed?

  constructor(private authService: AuthService) {}

  ngOnInit(): void {
    this.authService.getErrorMessage().subscribe((msg: string) => {
      if (msg) {
        this.isLoginFailed = true;
      }
      this.errorMessage = msg;
    });

    if (this.authService.getToken()) {
      this.isLoggedIn = true;
    }
  }

  onSubmit(): void {
    const { username, password } = this.form;
    this.authService.login(username, password);
  }

  reloadPage(): void {
    window.location.reload();
  }
}
