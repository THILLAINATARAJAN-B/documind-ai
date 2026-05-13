import {
  Component,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  AfterViewChecked,
  ChangeDetectorRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  ApiService,
  TranscriptSegment,
  FileItem,
} from '../../core/services/api.service';
import { SseService } from '../../core/services/sse.service';
import { AuthService } from '../../core/services/auth.service';
import { Subscription } from 'rxjs';
import { environment } from '../../../environments/environment';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp_ref?: number;
  streaming?: boolean;
  isError?: boolean;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.scss',
})
export class ChatComponent
  implements OnInit, OnDestroy, AfterViewChecked
{
  @ViewChild('messagesEnd') messagesEnd!: ElementRef;
  @ViewChild('mediaPlayer') mediaPlayer!: ElementRef<HTMLAudioElement>;

  fileId!: number;
  fileInfo: FileItem | null = null;
  segments: TranscriptSegment[] = [];
  messages: Message[] = [];
  question = '';
  sessionId: number | null = null;
  isStreaming = false;
  error = '';
  audioSrc = '';

  private sub?: Subscription;
  private shouldScroll = false;
  private streamWatchdog?: ReturnType<typeof setTimeout>;
  // Holds the last question so retry can resend it
  private lastQuestion = '';

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private api: ApiService,
    private sse: SseService,
    private auth: AuthService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.fileId = Number(this.route.snapshot.paramMap.get('fileId'));

    const token = this.auth.getToken();
    this.audioSrc = `${environment.apiUrl}/upload/files/${this.fileId}/stream?token=${token}`;

    this.api.getFiles().subscribe((files: FileItem[]) => {
      this.fileInfo = files.find((f) => f.id === this.fileId) || null;
      this.cdr.detectChanges();
      if (this.fileInfo && this.fileInfo.file_type !== 'pdf') {
        this.api.getSegments(this.fileId).subscribe((segs: TranscriptSegment[]) => {
          this.segments = segs;
          this.cdr.detectChanges();
        });
      }
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this._clearWatchdog();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      this.messagesEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' });
      this.shouldScroll = false;
    }
  }

  sendMessage(): void {
    if (!this.question.trim() || this.isStreaming) return;
    this._sendQuestion(this.question.trim());
  }

  // Called by the retry button in the template
  retryLastQuestion(): void {
    if (!this.lastQuestion || this.isStreaming) return;
    // Remove the last failed assistant message before retrying
    if (
      this.messages.length > 0 &&
      this.messages[this.messages.length - 1].isError
    ) {
      this.messages.pop();
      // Also remove the user message that preceded it
      if (
        this.messages.length > 0 &&
        this.messages[this.messages.length - 1].role === 'user'
      ) {
        this.messages.pop();
      }
    }
    this._sendQuestion(this.lastQuestion);
  }

  private _sendQuestion(q: string): void {
    this.lastQuestion = q;

    const userMsg: Message = { role: 'user', content: q };
    this.messages.push(userMsg);

    const assistantMsg: Message = {
      role: 'assistant',
      content: '',
      streaming: true,
    };
    this.messages.push(assistantMsg);

    this.isStreaming = true;
    this.shouldScroll = true;
    this.question = '';
    this.cdr.detectChanges();

    // 30s watchdog — if no token arrives, mark as error
    this._clearWatchdog();
    this.streamWatchdog = setTimeout(() => {
      if (assistantMsg.streaming && !assistantMsg.content) {
        assistantMsg.content =
          'No response received. The server may be overloaded. Please try again.';
        assistantMsg.isError = true;
        assistantMsg.streaming = false;
        this.isStreaming = false;
        this.sub?.unsubscribe();
        this.cdr.detectChanges();
      }
    }, 30_000);

    this.sub = this.sse
      .askQuestion(this.fileId, q, this.sessionId ?? undefined)
      .subscribe({
        next: (event: any) => {
          if (event.type === 'session' && event.session_id) {
            this.sessionId = event.session_id;

          } else if (event.type === 'token' && event.content) {
            // First token received — cancel the watchdog
            this._clearWatchdog();
            assistantMsg.content += event.content;
            this.shouldScroll = true;
            this.cdr.detectChanges();

          } else if (
            event.type === 'timestamp' &&
            event.value !== undefined
          ) {
            assistantMsg.timestamp_ref = event.value;
            this.cdr.detectChanges();

          } else if (event.type === 'error') {
            this._clearWatchdog();
            // Backend sends 'content', SSE HTTP errors send 'message'
            assistantMsg.content =
              event.content ||
              event.message ||
              'Something went wrong. Please try again.';
            assistantMsg.isError = true;
            assistantMsg.streaming = false;
            this.isStreaming = false;
            this.cdr.detectChanges();

          } else if (event.type === 'done') {
            this._clearWatchdog();
            assistantMsg.streaming = false;
            this.isStreaming = false;
            this.cdr.detectChanges();
          }
        },
        error: () => {
          this._clearWatchdog();
          assistantMsg.content =
            'Connection failed. Please check your network and try again.';
          assistantMsg.isError = true;
          assistantMsg.streaming = false;
          this.isStreaming = false;
          this.cdr.detectChanges();
        },
      });
  }

  private _clearWatchdog(): void {
    if (this.streamWatchdog) {
      clearTimeout(this.streamWatchdog);
      this.streamWatchdog = undefined;
    }
  }

  playTimestamp(seconds: number): void {
    const el = this.mediaPlayer?.nativeElement;
    if (!el) {
      console.warn('mediaPlayer ViewChild not found');
      return;
    }
    el.currentTime = seconds;
    el.play().catch((err) => console.error('Audio play() failed:', err));
  }

  formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  isMediaFile(): boolean {
    return this.fileInfo?.file_type !== 'pdf';
  }

  goBack(): void {
    this.router.navigate(['/dashboard']);
  }

  onEnter(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
}