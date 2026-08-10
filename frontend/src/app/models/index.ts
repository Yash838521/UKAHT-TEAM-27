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

export interface Category {
  category: string
  count:    number
}

export interface CategoriesResponse {
  categories:   Category[]
  total_images: number
  pending:      number
}

export interface StatsResponse {
  total_images: number
  per_year:     { year: number; count: number }[]
  scene_types:  { scene_type: string; count: number }[]
  duplicates:   { total: number; in_clusters: number; total_clusters: number }
  categories:   { category: string; count: number }[]
}

export interface TagCount {
  tag:   string
  count: number
}

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

// ── Image detail (used on /images/:id page) ───────────
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