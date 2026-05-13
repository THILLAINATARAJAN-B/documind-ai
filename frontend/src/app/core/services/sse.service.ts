import { Injectable } from '@angular/core';
import { AuthService } from './auth.service';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SSEEvent {
  type: 'session' | 'token' | 'timestamp' | 'done' | 'error';
  content?: string;
  value?: number;
  session_id?: number;
  message?: string;
}

const SSE_TIMEOUT_MS = 60_000; // 60 seconds — abort if no response starts

@Injectable({ providedIn: 'root' })
export class SseService {
  private readonly api = environment.apiUrl;

  constructor(private auth: AuthService) {}

  askQuestion(
    fileId: number,
    question: string,
    sessionId?: number
  ): Observable<SSEEvent> {
    return new Observable((observer) => {
      const token = this.auth.getToken();
      let buffer = '';

      // AbortController lets us cancel the fetch on timeout or unsubscribe
      const controller = new AbortController();

      // 60s timeout — if backend never responds, cancel and show error
      const timeoutId = setTimeout(() => {
        controller.abort();
        observer.next({
          type: 'error',
          message: 'Request timed out. The server took too long to respond.',
        });
        observer.next({ type: 'done' });
        observer.complete();
      }, SSE_TIMEOUT_MS);

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
        signal: controller.signal,
      })
        .then((response) => {
          clearTimeout(timeoutId); // response started — cancel timeout

          if (!response.ok) {
            const msg =
              response.status === 429
                ? 'Rate limit reached. Please wait a minute before asking again.'
                : response.status === 401
                ? 'Session expired. Please log in again.'
                : response.status === 422
                ? 'Invalid request. Please check your question.'
                : `Server error (${response.status}). Please try again.`;

            observer.next({ type: 'error', message: msg });
            observer.next({ type: 'done' });
            observer.complete();
            return;
          }

          const reader = response.body!.getReader();
          const decoder = new TextDecoder();

          const read = () => {
            reader
              .read()
              .then(({ done, value }) => {
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
              })
              .catch((err) => {
                if (err?.name === 'AbortError') return; // already handled above
                observer.next({
                  type: 'error',
                  message: 'Connection lost. Please try again.',
                });
                observer.next({ type: 'done' });
                observer.complete();
              });
          };

          read();
        })
        .catch((err) => {
          clearTimeout(timeoutId);
          if (err?.name === 'AbortError') return; // timeout already emitted
          observer.next({
            type: 'error',
            message:
              'Could not reach the server. Please check your connection.',
          });
          observer.next({ type: 'done' });
          observer.complete();
        });

      // Teardown: called when Angular unsubscribes (e.g. component destroyed)
      return () => {
        clearTimeout(timeoutId);
        controller.abort();
      };
    });
  }
}