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
    console.log('DashboardComponent initialized');
    this.loadFiles();
  }

  loadFiles(): void {
    console.log('loadFiles called');
    this.loading = true;
    this.error = '';
    this.cdr.detectChanges();

    this.api.getFiles().subscribe({
      next: (files) => {
        console.log('loadFiles success', files);
        this.files = files;
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('loadFiles error:', err);
        this.loading = false;
        this.error = err.status === 401
          ? 'Session not ready yet. Please try again.'
          : (err.error?.detail || 'Failed to load files');
        this.cdr.detectChanges();
      },
    });
  }

  onFileSelected(event: Event, type: 'pdf' | 'audio'): void {
    console.log('onFileSelected fired', type);

    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];

    if (!file) {
      console.warn('No file selected');
      return;
    }

    console.log('Selected file:', {
      name: file.name,
      type: file.type,
      size: file.size,
      uploadType: type,
    });

    this.uploading = true;
    this.error = '';
    this.cdr.detectChanges();

    const upload$ = type === 'pdf'
      ? this.api.uploadPdf(file)
      : this.api.uploadAudio(file);

    console.log('Starting upload request');

    upload$.subscribe({
      next: (res) => {
        console.log('Upload success:', res);
        this.uploading = false;
        this.cdr.detectChanges();
        this.loadFiles();
      },
      error: (err) => {
        console.error('Upload error:', err);
        this.uploading = false;
        this.error = err.error?.detail || 'Upload failed';
        this.cdr.detectChanges();
      },
      complete: () => {
        console.log('Upload observable completed');
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
      error: (err) => {
        console.error('summary error:', err);
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
      error: (err) => {
        console.error('delete error:', err);
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