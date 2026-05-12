import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { ApiService, FileItem } from '../../core/services/api.service';
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
    this.api.getFiles().subscribe({
      next: (files) => {
        this.files = files;
        this.loading = false;
        this.cdr.detectChanges();  // ← force re-render
      },
      error: (err) => {
        console.error('loadFiles error:', err);
        this.loading = false;
        this.cdr.detectChanges();
        if (err.status === 401) this.auth.logout();
      },
    });
  }

  onFileSelected(event: Event, type: 'pdf' | 'audio'): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.uploading = true;
    this.error = '';
    const upload$ = type === 'pdf' ? this.api.uploadPdf(file) : this.api.uploadAudio(file);
    upload$.subscribe({
      next: (newFile) => {
        this.files.unshift(newFile);
        this.uploading = false;
        this.cdr.detectChanges();  // ← force re-render after upload
      },
      error: (err) => {
        this.error = err.error?.detail || 'Upload failed';
        this.uploading = false;
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
    this.api.getSummary(fileId).subscribe({
      next: (res) => {
        this.summaries[fileId] = res.summary;
        this.summaryLoading[fileId] = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.summaryLoading[fileId] = false;
        this.cdr.detectChanges();
      },
    });
  }

  deleteFile(fileId: number): void {
    if (!confirm('Delete this file and all its data?')) return;
    this.api.deleteFile(fileId).subscribe({
      next: () => {
        this.files = this.files.filter((f) => f.id !== fileId);
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