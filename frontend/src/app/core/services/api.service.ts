import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

const API = 'http://localhost:8001';

export interface FileItem {
  id: number;
  original_filename: string;
  file_type: 'pdf' | 'audio' | 'video';
  uploaded_at: string;
}

export interface TranscriptSegment {
  id: number;
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

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  uploadPdf(file: File): Observable<FileItem> {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<FileItem>(`${API}/upload/pdf`, fd);
  }

  uploadAudio(file: File): Observable<FileItem> {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<FileItem>(`${API}/upload/audio`, fd);
  }

  getFiles(): Observable<FileItem[]> {
    return this.http.get<FileItem[]>(`${API}/upload/files`);
  }

  deleteFile(fileId: number): Observable<void> {
    return this.http.delete<void>(`${API}/upload/files/${fileId}`);
  }

  getSegments(fileId: number): Observable<TranscriptSegment[]> {
    return this.http.get<TranscriptSegment[]>(`${API}/upload/files/${fileId}/segments`);
  }

  getSummary(fileId: number): Observable<SummaryResponse> {
    return this.http.get<SummaryResponse>(`${API}/upload/files/${fileId}/summary`);
  }
}