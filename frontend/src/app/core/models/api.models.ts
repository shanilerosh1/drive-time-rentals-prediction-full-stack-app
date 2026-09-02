/** Mirrors the FastAPI schemas in backend/app/schemas. */

export type UserRole = 'admin' | 'inspector';
export type InspectionType = 'pre_rental' | 'post_rental';
export type InspectionStatus = 'draft' | 'analysing' | 'completed' | 'failed' | 'cancelled';
export type ImageStatus = 'pending' | 'analysed' | 'failed';
export type DamageOutcome = 'new' | 'pre_existing' | 'resolved';
export type SeverityHint = 'none' | 'minor' | 'moderate' | 'severe';

export type CaptureAngle =
  | 'front' | 'front_left' | 'front_right'
  | 'left' | 'right'
  | 'rear' | 'rear_left' | 'rear_right'
  | 'roof' | 'detail' | 'other';

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Vehicle {
  id: number;
  registration: string;
  make: string;
  model: string;
  year: number | null;
  colour: string | null;
  body_type: string | null;
  notes: string | null;
  created_at: string;
}

export interface VehicleWithStats extends Vehicle {
  inspection_count: number;
  last_inspected_at: string | null;
}

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Detection {
  id: number;
  class_name: string;
  confidence: number;
  threshold: number;
  is_positive: boolean;
  severity_hint: SeverityHint;
  /** Null for image-level classification; populated by the YOLOv8 backend. */
  bbox: BoundingBox | null;
}

export interface InspectionImage {
  id: number;
  inspection_id: number;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  width: number;
  height: number;
  sha256: string;
  capture_angle: CaptureAngle;
  status: ImageStatus;
  error_message: string | null;
  model_name: string | null;
  model_version: string | null;
  predictor_backend: string | null;
  inference_ms: number | null;
  created_at: string;
  detections: Detection[];
  file_url: string;
  thumbnail_url: string;
  positive_classes: string[];
}

export interface InspectionSummary {
  id: number;
  vehicle_id: number;
  inspector_id: number;
  inspection_type: InspectionType;
  status: InspectionStatus;
  rental_ref: string | null;
  odometer_km: number | null;
  location: string | null;
  notes: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  vehicle: Vehicle | null;
  inspector: User | null;
  image_count: number;
  damage_classes: string[];
}

export interface Inspection extends InspectionSummary {
  images: InspectionImage[];
}

export interface AnalyseResponse {
  inspection_id: number;
  analysed: number;
  skipped: number;
  failed: number;
  status: InspectionStatus;
  backend: string;
  is_real_model: boolean;
  total_ms: number;
}

export interface ComparisonRow {
  class_name: string;
  outcome: DamageOutcome;
  pre_confidence: number | null;
  post_confidence: number | null;
  pre_image_ids: number[];
  post_image_ids: number[];
  severity_hint: SeverityHint;
}

export interface Comparison {
  vehicle: Vehicle;
  rental_ref: string | null;
  pre_inspection: Inspection | null;
  post_inspection: Inspection | null;
  rows: ComparisonRow[];
  new_damage_classes: string[];
  pre_existing_classes: string[];
  resolved_classes: string[];
  is_complete: boolean;
  uses_real_model: boolean;
  note: string | null;
}

export interface DashboardStats {
  total_vehicles: number;
  total_inspections: number;
  inspections_last_7_days: number;
  images_analysed: number;
  completed_inspections: number;
  draft_inspections: number;
  damage_class_counts: Record<string, number>;
  mean_inference_ms: number | null;
  backend: string;
  is_real_model: boolean;
  recent_inspections: InspectionSummary[];
}

export interface DamageClass {
  name: string;
  label: string;
  colour: string;
  default_threshold: number;
  test_metrics: { roc_auc?: number; average_precision?: number; f1?: number };
}

export interface ModelInfo {
  backend: string;
  model_name: string;
  model_version: string;
  is_real: boolean;
  classes: string[];
  produces_bounding_boxes: boolean;
  configured_backend: string;
  classifier_weights_present: boolean;
  detector_weights_present: boolean;
  warning?: string;
  last_load_error?: string;
  device?: string;
  thresholds?: Record<string, number>;
  test_metrics?: Record<string, { roc_auc: number; average_precision: number; f1: number }>;
}

// --- model evaluation (measured on the held-out test split) ---------------

export interface ClassMetrics {
  support: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number;
  recall: number;
  f1: number;
  roc_auc?: number;
  average_precision?: number;
}

export interface EvaluationExample {
  file_name: string;
  truth: string[];
  predicted: string[];
  scores: Record<string, number>;
  correct: boolean;
}

export interface ModelEvaluation {
  split: string;
  images: number;
  backend: string;
  model_name: string;
  model_version: string;
  per_class: Record<string, ClassMetrics>;
  macro: { precision: number; recall: number; f1: number; roc_auc: number; average_precision: number };
  micro: { precision: number; recall: number; f1: number };
  exact_match_ratio: number;
  any_damage_accuracy: number;
  /** Present only when undamaged cars were included in the test set. */
  clean_images?: number;
  false_alarms?: number;
  false_alarm_rate?: number;
  clean_correct_rate?: number;
  thresholds: Record<string, number>;
  latency_ms: { mean: number; p50: number; p95: number };
  evaluated_at: string;
  wall_seconds: number;
  examples?: EvaluationExample[];
  example_count?: number;
}
