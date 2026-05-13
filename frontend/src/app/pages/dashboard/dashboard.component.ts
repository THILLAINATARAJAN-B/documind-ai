import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import {
  ApiService,
  FileItem,
  UploadProgress,
} from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  files: FileItem[] = [];
  loading = false;
  uploading = false;
  uploadProgress = 0;
  error = '';
  summaries: Record<number, string> = {};
  summaryLoading: Record<number, boolean> = {};

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadFiles();
  }

  loadFiles(): void {
    this.loading = true;
    this.error = '';
    this.cdr.detectChanges();

    this.api.getFiles().subscribe({
      next: (files: FileItem[]) => {
        this.files = files;
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        this.loading = false;
        this.error =
          err.status === 401
            ? 'Session expired. Please log in again.'
            : err.error?.detail || 'Failed to load files';
        this.cdr.detectChanges();
      },
    });
  }

  onFileSelected(event: Event, type: 'pdf' | 'audio'): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    this.uploading = true;
    this.uploadProgress = 0;
    this.error = '';
    this.cdr.detectChanges();

    const upload$ =
      type === 'pdf' ? this.api.uploadPdf(file) : this.api.uploadAudio(file);

    upload$.subscribe({
      next: (progress: UploadProgress) => {
        this.uploadProgress = progress.percent;
        this.cdr.detectChanges();

        if (progress.done) {
          this.uploading = false;
          this.uploadProgress = 0;
          this.cdr.detectChanges();
          this.loadFiles();
        }
      },
      error: (err: any) => {
        this.uploading = false;
        this.uploadProgress = 0;
        this.error = err.error?.detail || 'Upload failed';
        this.cdr.detectChanges();
      },
    });

    input.value = '';
  }

  openChat(fileId: number): void {
    this.router.navigate(['/chat', fileId]);
  }

  getSummary(fileId: number): void {
    this.summaryLoading[fileId] = true;
    this.cdr.detectChanges();

    this.api.getSummary(fileId).subscribe({
      next: (res) => {
        this.summaries[fileId] = res.summary;
        this.summaryLoading[fileId] = false;
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        console.error('Summary error:', err);
        this.summaryLoading[fileId] = false;
        this.error = err.error?.detail || 'Failed to load summary';
        this.cdr.detectChanges();
      },
    });
  }

  deleteFile(fileId: number): void {
    if (!confirm('Delete this file and all its data?')) return;

    this.api.deleteFile(fileId).subscribe({
      next: () => {
        this.files = this.files.filter((f) => f.id !== fileId);
        delete this.summaries[fileId];
        this.cdr.detectChanges();
      },
      error: (err: any) => {
        this.error = err.error?.detail || 'Delete failed';
        this.cdr.detectChanges();
      },
    });
  }

  logout(): void {
    this.auth.logout();
  }

  getFileIcon(type: string): string {
    return type === 'pdf' ? '📄' : '🎵';
  }
}