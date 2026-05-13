import { Injectable } from '@angular/core';
import {
  HttpClient,
  HttpRequest,
  HttpEventType,
  HttpResponse,
} from '@angular/common/http';
import { Observable, Subject } from 'rxjs';
import { filter, map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface UploadProgress {
  percent: number;
  done: boolean;
  response?: any;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // ── Auth ────────────────────────────────────────────────────────────────────
  login(email: string, password: string) {
    return this.http.post(`${this.api}/auth/login`, { email, password });
  }

  register(email: string, password: string) {
    return this.http.post(`${this.api}/auth/register`, { email, password });
  }

  logout(userId: number, refreshToken: string) {
    return this.http.post(`${this.api}/auth/logout`, {
      user_id: userId,
      refresh_token: refreshToken,
    });
  }

  refreshToken(userId: number, refreshToken: string) {
    return this.http.post(`${this.api}/auth/refresh`, {
      user_id: userId,
      refresh_token: refreshToken,
    });
  }

  // ── Files ───────────────────────────────────────────────────────────────────
  getFiles(limit = 50, offset = 0) {
    return this.http.get(
      `${this.api}/upload/files?limit=${limit}&offset=${offset}`
    );
  }

  deleteFile(fileId: number) {
    return this.http.delete(`${this.api}/upload/files/${fileId}`);
  }

  getFileSummary(fileId: number) {
    return this.http.get(`${this.api}/upload/files/${fileId}/summary`);
  }

  getTranscriptSegments(fileId: number) {
    return this.http.get(`${this.api}/upload/files/${fileId}/segments`);
  }

  // ── Upload with progress ────────────────────────────────────────────────────
  uploadPdf(file: File): Observable<UploadProgress> {
    return this._uploadWithProgress('/upload/pdf', file);
  }

  uploadAudio(file: File): Observable<UploadProgress> {
    return this._uploadWithProgress('/upload/audio', file);
  }

  private _uploadWithProgress(
    endpoint: string,
    file: File
  ): Observable<UploadProgress> {
    const formData = new FormData();
    formData.append('file', file);

    const req = new HttpRequest('POST', `${this.api}${endpoint}`, formData, {
      reportProgress: true,
    });

    return new Observable<UploadProgress>((observer) => {
      this.http.request(req).subscribe({
        next: (event) => {
          if (event.type === HttpEventType.UploadProgress) {
            const percent = event.total
              ? Math.round((100 * event.loaded) / event.total)
              : 0;
            observer.next({ percent, done: false });
          } else if (event instanceof HttpResponse) {
            observer.next({ percent: 100, done: true, response: event.body });
            observer.complete();
          }
        },
        error: (err) => observer.error(err),
      });
    });
  }

  // ── Chat ────────────────────────────────────────────────────────────────────
  askQuestion(fileId: number, question: string, sessionId?: number) {
    return this.http.post(`${this.api}/chat/ask`, {
      file_id: fileId,
      question,
      session_id: sessionId,
    });
  }
}