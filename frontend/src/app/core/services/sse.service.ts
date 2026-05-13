import { Injectable } from '@angular/core';
import { AuthService } from './auth.service';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface SSEEvent {
  type: 'session' | 'token' | 'timestamp' | 'done' | 'error';
  content?: string;
  value?: number;
  session_id?: number;
  message?: string;
}

@Injectable({ providedIn: 'root' })
export class SseService {
  private readonly api = environment.apiUrl;

  constructor(private auth: AuthService) {}

  askQuestion(fileId: number, question: string, sessionId?: number): Observable<SSEEvent> {
    return new Observable((observer) => {
      const token = this.auth.getToken();
      let buffer = '';

      fetch(`${this.api}/chat/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          file_id: fileId,
          question,
          session_id: sessionId ?? null,
        }),
      })
        .then((response) => {
          if (!response.ok) {
            // Emit a structured error event so the UI can display a message
            observer.next({
              type: 'error',
              message:
                response.status === 429
                  ? 'Rate limit reached. Please wait a minute before asking again.'
                  : response.status === 401
                  ? 'Session expired. Please log in again.'
                  : `Server error (${response.status}). Please try again.`,
            });
            observer.complete();
            return;
          }
          const reader = response.body!.getReader();
          const decoder = new TextDecoder();

          const read = () => {
            reader.read().then(({ done, value }) => {
              if (done) {
                observer.complete();
                return;
              }

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() ?? '';

              for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data:')) continue;
                const jsonStr = trimmed.slice(5).trim();
                if (!jsonStr) continue;
                try {
                  const data: SSEEvent = JSON.parse(jsonStr);
                  observer.next(data);
                  if (data.type === 'done') {
                    observer.complete();
                    return;
                  }
                } catch (e) {
                  console.warn('SSE parse error:', jsonStr, e);
                }
              }
              read();
            }).catch((err) => {
              observer.next({ type: 'error', message: 'Connection lost. Please try again.' });
              observer.complete();
            });
          };
          read();
        })
        .catch((err) => {
          observer.next({ type: 'error', message: 'Could not reach the server. Please check your connection.' });
          observer.complete();
        });
    });
  }
}
