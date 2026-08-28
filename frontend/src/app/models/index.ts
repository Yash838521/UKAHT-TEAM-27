// Image
export interface Image {
  id:                number
  filename:          string
  storage_url:       string
  uploaded_at:       string
  date_taken:        string
  camera_make:       string
  camera_model:      string
  scene_type:        string
  people_count:      number
  tags:              { tag: string; confidence: number }[]
  categories:        { category: string; confidence: number; is_primary: boolean }[]
  overall_score:     number
  is_best_in_group:  boolean
  cluster_id:        number | null
  is_representative: boolean
}

export interface ImagesResponse {
  total:  number
  page:   number
  limit:  number
  pages:  number
  images: Image[]
}

// Image detail (used on /images/:id page)
export interface ImageDetail {
  id:                number
  filename:          string
  storage_url:       string
  uploaded_at:       string
  date_taken:        string | null
  camera_make:       string | null
  camera_model:      string | null
  serial_number:     string | null
  lens_model:        string | null
  image_width:       number | null
  image_height:      number | null
  iso:               number | null
  flash:             string | null
  white_balance:     string | null
  orientation:       string | null
  software:          string | null
  gps_latitude:      number | null
  gps_longitude:     number | null
  scene_type:        string | null
  scene_confidence:  number | null
  people_count:      number | null
  people_confidence: number | null
  tags:              { tag: string; confidence: number }[]
  categories:        { category: string; confidence: number; is_primary: boolean }[]
  caption:           string | null
  model_name:        string | null
  is_verified:       boolean
  sharpness_score:   number | null
  exposure_score:    number | null
  overall_score:     number | null
  is_best_in_group:  boolean
  cluster_id:        number | null
  similarity_score:  number | null
  is_representative: boolean
  corrected_scene_type:   string | null
  corrected_people_count: string | null
  reviewer:               string | null
}

// Categories
export interface Category {
  category: string
  count:    number
}

export interface CategoriesResponse {
  categories:   Category[]
  total_images: number
  pending:      number
}

// Stats
export interface StatsResponse {
  total_images:  number
  per_year:      { year: number; count: number }[]
  cameras:       { camera_model: string; camera_make: string; count: number }[]
  scene_types:   { scene_type: string; count: number }[]
  people_dist:   { people_count: number; count: number }[]
  completeness:  {
    total:      number
    has_date:   number
    has_camera: number
    has_gps:    number
  }
  quality:       { high: number; medium: number; low: number }
  duplicates:    { total: number; in_clusters: number; total_clusters: number }
  categories:    { category: string; count: number }[]
  verification:  { total_tagged: number; verified: number }
}

// Tags
export interface TagCount {
  tag:   string
  count: number
}

// Filter state (browse page)
export interface FilterState {
  scene_type:    string
  people_min:    number | null
  quality_min:   number
  date_from:     string
  date_to:       string
  no_duplicates: boolean
  tags:          string[]
  category:      string
  sort:          string
  order:         string
  page:          number
  limit:         number
}

// Upload batch (upload history tab)
export interface UploadBatch {
  id:          number
  uploaded_by: string
  uploaded_at: string
  total_files: number
  success:     number
  failed:      number
}

export interface BatchDetail {
  batch:  UploadBatch
  images: {
    id:          number
    filename:    string
    storage_url: string
    uploaded_at: string
    processed:   boolean
  }[]
}

// Queue file (upload page internal state)
export type FileStatus = 'ready' | 'uploading' | 'done' | 'failed'

export interface QueueFile {
  file:     File
  status:   FileStatus
  progress: number
  error:    string
}
// ── ADD THESE INTERFACES TO THE BOTTOM OF src/app/models/index.ts ────────────

// Review queue — tag review
export interface QueueImage {
  id:                number
  filename:          string
  storage_url:       string
  scene_type:        string | null
  scene_confidence:  number | null
  people_count:      number | null
  people_confidence: number | null
  tags:              { tag: string; confidence: number }[]
  categories:        { category: string; confidence: number; is_primary: boolean }[]
  is_verified:       boolean
  model_name:        string | null
  uncertainty_score:   number | null
  uncertainty_reason:  string | null
  review_recommended:  boolean
}

export interface QueueResponse {
  total:  number
  page:   number
  images: QueueImage[]
}

// Duplicate review — clusters
export interface ClusterMember {
  id:               number
  filename:         string
  storage_url:      string
  scene_type:       string | null
  people_count:     number | null
  overall_score:    number | null
  similarity_score: number | null
  is_representative: boolean
}

export interface DuplicateCluster {
  cluster_id:        number
  member_count:      number
  representative_id: number
  members:           ClusterMember[]
}

export interface ClustersResponse {
  total:    number
  page:     number
  clusters: DuplicateCluster[]
}
export interface AccuracyResponse {
  total_corrections: number
  per_field:         { field_name: string; corrections: number }[]
  scene_accuracy:    { predicted: string; actual: string; count: number }[]
  people_mae:        number | null
}