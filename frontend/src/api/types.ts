// Mirrors backend/api response shapes. Kept in one place so a backend field
// rename surfaces as a single TypeScript error here, not a silent runtime bug.

export interface User {
  id: number;
  email: string;
  name: string;
}

export type RoomType = "living_room" | "bedroom" | "office" | "study_room" | "other";
export type SessionStatus = "draft" | "analyzing" | "ready" | "error";
// FR-3 style categories, exactly as named in the report.
export type Style = "Modern" | "Minimalist" | "Contemporary" | "Traditional" | "Industrial" | "Scandinavian";

export interface DesignSession {
  id: number;
  room_type: RoomType | null;
  title: string | null;
  status: SessionStatus;
  preferred_style: Style | null;
  preferred_colors: string[] | null;
  budget: number | null;
  currency: string;
  created_at: string;
  updated_at: string;
}

export type JobStage =
  | "preprocess"
  | "room_analysis"
  | "style_recognition"
  | "recommendation"
  | "layout_optimization"
  | "visualization"
  | "generate_design";
export type JobStatus = "queued" | "running" | "done" | "failed";

export interface Job {
  id: number;
  session_id: number;
  stage: JobStage;
  status: JobStatus;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface RoomImage {
  id: number;
  width: number;
  height: number;
}

export interface CatalogItem {
  id: number;
  name: string;
  category: string;
  color: string;
  price: number;
  currency: string;
  width_cm: number;
  depth_cm: number;
  height_cm: number;
  image_url: string;
  data_source: string; // always "MOCK" — see brief PART 6 / PLAN.md
}

export interface RecommendationItem {
  id: number;
  action: "add" | "keep" | "remove" | "replace";
  score_breakdown: {
    style_match: number;
    color_match: number;
    budget_fit: number;
    space_fit: number;
    principle_citations: string[];
  };
  rationale: string;
  quantity: number;
  catalog_item: CatalogItem;
}

export interface Recommendation {
  id: number;
  iteration: number;
  total_cost: number;
  budget: number;
  within_budget: boolean;
  palette: { preferred_colors: string[]; chosen_item_colors: string[] };
  created_at: string;
  items: RecommendationItem[];
  is_sample_room: boolean;
}

export interface LayoutObject {
  label: string;
  x_cm: number;
  y_cm: number;
  width_cm: number;
  depth_cm: number;
  rotation_deg: number;
  is_existing: boolean;
  catalog_item_id: number | null;
}

export interface VisualizationInfo {
  id: number;
  provider: string;
  structure_preserving: boolean;
  cache_hit: boolean;
  image_url: string;
}

export interface Layout {
  id: number;
  layout_score: number;
  score_breakdown: {
    space_utilization: number;
    accessibility: number;
    movement_flow: number;
    visual_balance: number;
    functionality: number;
  };
  constraints_satisfied: Record<string, boolean>;
  algorithm: string;
  iterations: number;
  objects: LayoutObject[];
  is_sample_room: boolean;
  floorplan_svg: string | null;
  visualization: VisualizationInfo | null;
}

export interface IterationSummary {
  iteration: number;
  created_at: string;
  total_cost: number;
  within_budget: boolean;
  layout_score: number | null;
  item_count: number;
}

export interface FeedbackEntry {
  id: number;
  raw_text: string;
  structured_deltas: {
    keep_item_ids: number[];
    remove_item_ids: number[];
    style_shift: Style | null;
    budget_delta: number | null;
    crowding_shift: "less" | "more" | null;
    notes: string;
  };
  rating: number | null;
  created_at?: string;
}
