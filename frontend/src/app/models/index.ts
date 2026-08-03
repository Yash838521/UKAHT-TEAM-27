export interface Category {
  category: string
  count: number
}

export interface CategoriesResponse {
  categories: Category[]
  total_images: number
  pending: number
}

export interface Image {
  id: number
  filename: string
  storage_url: string
  date_taken: string
  camera_make: string
  camera_model: string
  scene_type: string
  people_count: number
  tags: { tag: string; confidence: number }[]
  categories: { category: string; confidence: number; is_primary: boolean }[]
  overall_score: number
  is_best_in_group: boolean
  cluster_id: number | null
  is_representative: boolean
}

export interface StatsResponse {
  total_images: number
  per_year: { year: number; count: number }[]
  scene_types: { scene_type: string; count: number }[]
  duplicates: { total: number; in_clusters: number; total_clusters: number }
}

export interface ImagesResponse {
  total:  number
  page:   number
  limit:  number
  pages:  number
  images: Image[]
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

