import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AnalyseResponse,
  CaptureAngle,
  Comparison,
  DamageClass,
  DashboardStats,
  Inspection,
  InspectionImage,
  InspectionStatus,
  InspectionSummary,
  InspectionType,
  ModelEvaluation,
  ModelInfo,
  Page,
  User,
  Vehicle,
  VehicleWithStats,
} from '../models/api.models';

export interface InspectionFilters {
  vehicle_id?: number;
  inspector_id?: number;
  inspection_type?: InspectionType;
  status?: InspectionStatus;
  rental_ref?: string;
  limit?: number;
  offset?: number;
}

export interface ComparisonQuery {
  vehicle_id?: number;
  rental_ref?: string;
  pre_inspection_id?: number;
  post_inspection_id?: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly base = environment.apiBase;

  constructor(private readonly http: HttpClient) {}

  // --- system ---------------------------------------------------------
  modelInfo(): Observable<ModelInfo> {
    return this.http.get<ModelInfo>(`${this.base}/model`);
  }

  reloadModel(): Observable<ModelInfo> {
    return this.http.post<ModelInfo>(`${this.base}/model/reload`, {});
  }

  /** Measured performance on the held-out test split; 404 when not yet run. */
  modelEvaluation(): Observable<ModelEvaluation> {
    return this.http.get<ModelEvaluation>(`${this.base}/model/evaluation`);
  }

  damageClasses(): Observable<{ classes: DamageClass[] }> {
    return this.http.get<{ classes: DamageClass[] }>(`${this.base}/damage-classes`);
  }

  // --- dashboard ------------------------------------------------------
  dashboardStats(): Observable<DashboardStats> {
    return this.http.get<DashboardStats>(`${this.base}/dashboard/stats`);
  }

  // --- vehicles -------------------------------------------------------
  listVehicles(search?: string, limit = 100, offset = 0): Observable<Page<VehicleWithStats>> {
    let params = new HttpParams().set('limit', limit).set('offset', offset);
    if (search?.trim()) params = params.set('search', search.trim());
    return this.http.get<Page<VehicleWithStats>>(`${this.base}/vehicles`, { params });
  }

  getVehicle(id: number): Observable<Vehicle> {
    return this.http.get<Vehicle>(`${this.base}/vehicles/${id}`);
  }

  createVehicle(payload: Partial<Vehicle>): Observable<Vehicle> {
    return this.http.post<Vehicle>(`${this.base}/vehicles`, payload);
  }

  updateVehicle(id: number, payload: Partial<Vehicle>): Observable<Vehicle> {
    return this.http.patch<Vehicle>(`${this.base}/vehicles/${id}`, payload);
  }

  deleteVehicle(id: number): Observable<{ detail: string }> {
    return this.http.delete<{ detail: string }>(`${this.base}/vehicles/${id}`);
  }

  // --- inspections ----------------------------------------------------
  listInspections(filters: InspectionFilters = {}): Observable<Page<InspectionSummary>> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    }
    return this.http.get<Page<InspectionSummary>>(`${this.base}/inspections`, { params });
  }

  getInspection(id: number): Observable<Inspection> {
    return this.http.get<Inspection>(`${this.base}/inspections/${id}`);
  }

  createInspection(payload: {
    vehicle_id: number;
    inspection_type: InspectionType;
    rental_ref?: string | null;
    odometer_km?: number | null;
    location?: string | null;
    notes?: string | null;
  }): Observable<Inspection> {
    return this.http.post<Inspection>(`${this.base}/inspections`, payload);
  }

  updateInspection(id: number, payload: Partial<Inspection>): Observable<Inspection> {
    return this.http.patch<Inspection>(`${this.base}/inspections/${id}`, payload);
  }

  deleteInspection(id: number): Observable<{ detail: string }> {
    return this.http.delete<{ detail: string }>(`${this.base}/inspections/${id}`);
  }

  uploadImages(
    inspectionId: number,
    files: File[],
    captureAngle: CaptureAngle,
    analyse = true,
  ): Observable<InspectionImage[]> {
    const form = new FormData();
    for (const file of files) form.append('files', file, file.name);
    form.append('capture_angle', captureAngle);
    form.append('analyse', String(analyse));
    return this.http.post<InspectionImage[]>(
      `${this.base}/inspections/${inspectionId}/images`,
      form,
    );
  }

  analyse(inspectionId: number, force = false): Observable<AnalyseResponse> {
    return this.http.post<AnalyseResponse>(
      `${this.base}/inspections/${inspectionId}/analyse`,
      { force },
    );
  }

  deleteImage(inspectionId: number, imageId: number): Observable<{ detail: string }> {
    return this.http.delete<{ detail: string }>(
      `${this.base}/inspections/${inspectionId}/images/${imageId}`,
    );
  }

  // --- comparison -----------------------------------------------------
  compare(query: ComparisonQuery): Observable<Comparison> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    }
    return this.http.get<Comparison>(`${this.base}/comparisons`, { params });
  }

  // --- reports (blobs) ------------------------------------------------
  inspectionReport(inspectionId: number): Observable<Blob> {
    return this.http.get(`${this.base}/inspections/${inspectionId}/report`, {
      responseType: 'blob',
    });
  }

  comparisonReport(query: ComparisonQuery): Observable<Blob> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    }
    return this.http.get(`${this.base}/comparisons/report`, { params, responseType: 'blob' });
  }

  // --- users ----------------------------------------------------------
  listUsers(): Observable<Page<User>> {
    return this.http.get<Page<User>>(`${this.base}/users`);
  }

  /**
   * Images are behind bearer auth, so an <img src> cannot fetch them directly.
   * Components use this to pull the bytes and bind an object URL.
   */
  fetchImageBlob(path: string): Observable<Blob> {
    const url = path.startsWith('http')
      ? path
      : `${this.base}${path.replace(/^\/api\/v1/, '')}`;
    return this.http.get(url, { responseType: 'blob' });
  }
}
