import { Injectable, signal, PLATFORM_ID, Inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { Observable } from 'rxjs';

const API = 'http://localhost:8001';
const TOKEN_KEY = 'dm_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private token: string | null = null;
  private isBrowser: boolean;
  isAuthenticated = signal(false);

  constructor(
    private http: HttpClient,
    private router: Router,
    @Inject(PLATFORM_ID) platformId: Object
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
    if (this.isBrowser) {
      this.token = localStorage.getItem(TOKEN_KEY);  // ← localStorage persists refresh
      this.isAuthenticated.set(!!this.token);
    }
  }

  register(email: string, password: string): Observable<any> {
    return this.http.post(`${API}/auth/register`, { email, password });
  }

  login(email: string, password: string): Observable<any> {
    return this.http
      .post<{ access_token: string }>(`${API}/auth/login`, { email, password })
      .pipe(
        tap((res) => {
          this.token = res.access_token;
          if (this.isBrowser) {
            localStorage.setItem(TOKEN_KEY, this.token);  // ← localStorage
          }
          this.isAuthenticated.set(true);
        })
      );
  }

  logout(): void {
    this.token = null;
    if (this.isBrowser) {
      localStorage.removeItem(TOKEN_KEY);  // ← localStorage
    }
    this.isAuthenticated.set(false);
    this.router.navigate(['/login']);
  }

  getToken(): string | null {
    // Re-read from localStorage in case token was set in another tab
    if (this.isBrowser && !this.token) {
      this.token = localStorage.getItem(TOKEN_KEY);
    }
    return this.token;
  }

  isLoggedIn(): boolean {
    if (this.isBrowser && !this.token) {
      this.token = localStorage.getItem(TOKEN_KEY);
    }
    return !!this.token;
  }
}