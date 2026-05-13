import { Injectable } from '@angular/core';
import {
  HttpClient,
  HttpRequest,
  HttpEventType,
  HttpResponse,
} from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

// ── Shared interfaces exported for use in components ──────────────────────────

export interface FileItem {
  id: number;
  filename: string;
  original_filename: string;
  file_type: 'pdf' | 'audio' | 'video';
  uploaded_at: string;
}

export interface TranscriptSegment {
  id: number;
  file_id: number;
  text: string;
  start_seconds: number;
  end_seconds: number;
  segment_index: number;
}

export interface SummaryResponse {
  file_id: number;
  summary: string;
  cached: boolean;
}

export interface UploadProgress {
  percent: number;
  done: boolean;
  response?: FileItem;
}

// ─────────────────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // ── Auth ────────────────────────────────────────────────────────────────────
  login(email: string, password: string) {
    return this.http.post<{ access_token: string; refresh_token: string }>(
      `${this.api}/auth/login`,
      { email, password }
    );
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
    return this.http.post<{ access_token: string; refresh_token: string }>(
      `${this.api}/auth/refresh`,
      { user_id: userId, refresh_token: refreshToken }
    );
  }

  // ── Files ───────────────────────────────────────────────────────────────────
  getFiles(limit = 50, offset = 0): Observable<FileItem[]> {
    return this.http.get<FileItem[]>(
      `${this.api}/upload/files?limit=${limit}&offset=${offset}`
    );
  }

  deleteFile(fileId: number) {
    return this.http.delete(`${this.api}/upload/files/${fileId}`);
  }

  // Alias used by dashboard.component
  getSummary(fileId: number): Observable<SummaryResponse> {
    return this.http.get<SummaryResponse>(
      `${this.api}/upload/files/${fileId}/summary`
    );
  }

  // Alias used by chat.component
  getSegments(fileId: number): Observable<TranscriptSegment[]> {
    return this.http.get<TranscriptSegment[]>(
      `${this.api}/upload/files/${fileId}/segments`
    );
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
            observer.next({
              percent: 100,
              done: true,
              response: event.body as FileItem,
            });
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