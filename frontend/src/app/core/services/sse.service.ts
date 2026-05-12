import { Injectable } from '@angular/core';
import { AuthService } from './auth.service';
import { Observable } from 'rxjs';

const API = 'http://localhost:8001';

export interface SSEEvent {
  type: 'session' | 'token' | 'timestamp' | 'done';
  content?: string;
  value?: number;
  session_id?: number;
}

@Injectable({ providedIn: 'root' })
export class SseService {
  constructor(private auth: AuthService) {}

  askQuestion(fileId: number, question: string, sessionId?: number): Observable<SSEEvent> {
    return new Observable((observer) => {
      const token = this.auth.getToken();
      let buffer = '';

      fetch(`${API}/chat/ask`, {
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
            observer.error(new Error(`HTTP ${response.status}`));
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
            }).catch((err) => observer.error(err));
          };
          read();
        })
        .catch((err) => observer.error(err));
    });
  }
}