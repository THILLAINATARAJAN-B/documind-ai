import { Injectable, signal, PLATFORM_ID, Inject } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap, switchMap, catchError } from 'rxjs/operators';
import { Observable, throwError } from 'rxjs';
import { environment } from '../../../../environments/environment';

const TOKEN_KEY = 'dm_token';
const REFRESH_KEY = 'dm_refresh';
const USER_ID_KEY = 'dm_uid';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private token: string | null = null;
  private refreshToken: string | null = null;
  private userId: number | null = null;
  private isBrowser: boolean;
  isAuthenticated = signal(false);

  private readonly api = environment.apiUrl;

  constructor(
    private http: HttpClient,
    private router: Router,
    @Inject(PLATFORM_ID) platformId: Object
  ) {
    this.isBrowser = isPlatformBrowser(platformId);
    if (this.isBrowser) {
      this.token = localStorage.getItem(TOKEN_KEY);
<<<<<<< HEAD
=======
      this.refreshToken = localStorage.getItem(REFRESH_KEY);
      const uid = localStorage.getItem(USER_ID_KEY);
      this.userId = uid ? parseInt(uid, 10) : null;
>>>>>>> d20bcba172a84f2cb5eaaa17ef4e95f318c509b0
      this.isAuthenticated.set(!!this.token);
    }
  }

  register(email: string, password: string): Observable<any> {
    return this.http.post(`${this.api}/auth/register`, { email, password });
  }

  login(email: string, password: string): Observable<any> {
    return this.http
      .post<{ access_token: string; refresh_token?: string; id?: number }>(
        `${this.api}/auth/login`,
        { email, password }
      )
      .pipe(
        tap((res) => {
          this.token = res.access_token;
          if (this.isBrowser) {
            localStorage.setItem(TOKEN_KEY, this.token);
<<<<<<< HEAD
=======
            if (res.refresh_token) {
              this.refreshToken = res.refresh_token;
              localStorage.setItem(REFRESH_KEY, res.refresh_token);
            }
>>>>>>> d20bcba172a84f2cb5eaaa17ef4e95f318c509b0
          }
          this.isAuthenticated.set(true);
        })
      );
  }

  /**
   * Use the stored refresh token to get a new access token.
   * Called automatically by the auth interceptor on 401 responses.
   */
  refreshAccessToken(): Observable<string> {
    if (!this.refreshToken || !this.userId) {
      return throwError(() => new Error('No refresh token available'));
    }
    return this.http
      .post<{ access_token: string; refresh_token: string }>(
        `${this.api}/auth/refresh`,
        { user_id: this.userId, refresh_token: this.refreshToken }
      )
      .pipe(
        tap((res) => {
          this.token = res.access_token;
          this.refreshToken = res.refresh_token;
          if (this.isBrowser) {
            localStorage.setItem(TOKEN_KEY, res.access_token);
            localStorage.setItem(REFRESH_KEY, res.refresh_token);
          }
        }),
        switchMap((res) => [res.access_token]),
        catchError((err) => {
          this.logout();
          return throwError(() => err);
        })
      );
  }

  logout(): void {
    // Best-effort: revoke refresh token on server
    if (this.refreshToken && this.userId) {
      this.http
        .post(`${this.api}/auth/logout`, {
          user_id: this.userId,
          refresh_token: this.refreshToken,
        })
        .subscribe({ error: () => {} });
    }
    this.token = null;
    this.refreshToken = null;
    this.userId = null;
    if (this.isBrowser) {
      localStorage.removeItem(TOKEN_KEY);
<<<<<<< HEAD
=======
      localStorage.removeItem(REFRESH_KEY);
      localStorage.removeItem(USER_ID_KEY);
>>>>>>> d20bcba172a84f2cb5eaaa17ef4e95f318c509b0
    }
    this.isAuthenticated.set(false);
    this.router.navigate(['/login']);
  }

  getToken(): string | null {
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

  getUserId(): number | null {
    return this.userId;
  }
}
