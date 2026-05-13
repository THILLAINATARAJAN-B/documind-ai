import {
  Component, OnInit, OnDestroy, ViewChild, ElementRef,
  AfterViewChecked, ChangeDetectorRef
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService, TranscriptSegment, FileItem } from '../../core/services/api.service';
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
export class ChatComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('messagesEnd') messagesEnd!: ElementRef;
  @ViewChild('mediaPlayer') mediaPlayer!: ElementRef<HTMLAudioElement | HTMLVideoElement>;

  fileId!: number;
  fileInfo: FileItem | null = null;
  segments: TranscriptSegment[] = [];
  messages: Message[] = [];
  question = '';
  sessionId: number | null = null;
  isStreaming = false;
  error = '';
  private sub?: Subscription;
  private shouldScroll = false;

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
    this.api.getFiles().subscribe((files) => {
      this.fileInfo = files.find((f) => f.id === this.fileId) || null;
      this.cdr.detectChanges();
      if (this.fileInfo && this.fileInfo.file_type !== 'pdf') {
        this.api.getSegments(this.fileId).subscribe((segs) => {
          this.segments = segs;
          this.cdr.detectChanges();
        });
      }
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScroll) {
      this.messagesEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' });
      this.shouldScroll = false;
    }
  }

  sendMessage(): void {
    if (!this.question.trim() || this.isStreaming) return;

    const userMsg: Message = { role: 'user', content: this.question };
    this.messages.push(userMsg);

    const assistantMsg: Message = { role: 'assistant', content: '', streaming: true };
    this.messages.push(assistantMsg);

    this.isStreaming = true;
    this.shouldScroll = true;
    const q = this.question;
    this.question = '';
    this.cdr.detectChanges();

    this.sub = this.sse.askQuestion(this.fileId, q, this.sessionId ?? undefined).subscribe({
      next: (event) => {
        if (event.type === 'session' && event.session_id) {
          this.sessionId = event.session_id;
        } else if (event.type === 'token' && event.content) {
          assistantMsg.content += event.content;
          this.shouldScroll = true;
          this.cdr.detectChanges();
        } else if (event.type === 'timestamp' && event.value !== undefined) {
          assistantMsg.timestamp_ref = event.value;
          this.cdr.detectChanges();
        } else if (event.type === 'error') {
          assistantMsg.content = event.message || 'Something went wrong. Please try again.';
          assistantMsg.isError = true;
          assistantMsg.streaming = false;
          this.isStreaming = false;
          this.cdr.detectChanges();
        } else if (event.type === 'done') {
          assistantMsg.streaming = false;
          this.isStreaming = false;
          this.cdr.detectChanges();
        }
      },
      error: () => {
        assistantMsg.content = 'Something went wrong. Please try again.';
        assistantMsg.streaming = false;
        this.isStreaming = false;
        this.cdr.detectChanges();
      },
    });
  }

  playTimestamp(seconds: number): void {
    const el = this.mediaPlayer?.nativeElement;
    if (el) {
      el.currentTime = seconds;
      (el as HTMLAudioElement).play();
    }
  }

  formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  isMediaFile(): boolean {
    return this.fileInfo?.file_type !== 'pdf';
  }

  getMediaSrc(): string {
    const token = this.auth.getToken();
    return `${environment.apiUrl}/upload/files/${this.fileId}/stream?token=${token}`;
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