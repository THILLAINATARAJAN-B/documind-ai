import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

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
  private readonly api = environment.apiUrl;

  constructor(private http: HttpClient) {}

  uploadPdf(file: File): Observable<FileItem> {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<FileItem>(`${this.api}/upload/pdf`, fd);
  }

  uploadAudio(file: File): Observable<FileItem> {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<FileItem>(`${this.api}/upload/audio`, fd);
  }

  getFiles(): Observable<FileItem[]> {
    return this.http.get<FileItem[]>(`${this.api}/upload/files`);
  }

  deleteFile(fileId: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/upload/files/${fileId}`);
  }

  getSegments(fileId: number): Observable<TranscriptSegment[]> {
    return this.http.get<TranscriptSegment[]>(`${this.api}/upload/files/${fileId}/segments`);
  }

  getSummary(fileId: number): Observable<SummaryResponse> {
    return this.http.get<SummaryResponse>(`${this.api}/upload/files/${fileId}/summary`);
  }
}
