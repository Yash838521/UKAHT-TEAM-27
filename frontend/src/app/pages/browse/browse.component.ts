import { Component, OnInit, OnDestroy } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { Router, ActivatedRoute, RouterModule } from '@angular/router'
import { forkJoin, of, Subject } from 'rxjs'
import { catchError, switchMap, takeUntil } from 'rxjs/operators'
import { ImagesService } from '../../services/images.service'
import { CategoriesService, StatsResponse } from '../../services/categories.service'
import { FilterState, Image, TagCount } from '../../models'
import { SidebarFiltersComponent } from '../../components/sidebar-filters/sidebar-filters.component'
import { ActiveChipsComponent } from '../../components/active-chips/active-chips.component'
import { SortBarComponent } from '../../components/sort-bar/sort-bar.component'
import { ImageGridComponent } from '../../components/image-grid/image-grid.component'

const DEFAULT_FILTERS: FilterState = {
  scene_type:    '',
  people_min:    null,
  quality_min:   0,
  date_from:     '',
  date_to:       '',
  no_duplicates: false,
  tags:          [],
  category:      '',
  sort:          'overall_score',
  order:         'DESC',
  page:          1,
  limit:         24
}

const FALLBACK_TAGS: TagCount[] = [
  { tag: 'tent',         count: 142 },
  { tag: 'sledge',       count: 98  },
  { tag: 'equipment',    count: 87  },
  { tag: 'hut',          count: 76  },
  { tag: 'flag',         count: 64  },
  { tag: 'fuel drum',    count: 51  },
  { tag: 'snow vehicle', count: 43  },
  { tag: 'antenna',      count: 38  },
  { tag: 'rope',         count: 29  },
]

@Component({
  selector: 'app-browse',
  templateUrl: './browse.component.html',
  styleUrls: ['./browse.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    SidebarFiltersComponent,
    ActiveChipsComponent,
    SortBarComponent,
    ImageGridComponent
  ]
})
export class BrowseComponent implements OnInit, OnDestroy {
  filters:      FilterState = { ...DEFAULT_FILTERS }
  images:       Image[]     = []
  tags:         TagCount[]  = []
  total:        number      = 0
  pages:        number      = 0
  minYear:      number      = 2010
  maxYear:      number      = 2023
  similarities: Record<number, number> = {}

  sidebarReady: boolean = false
  showSidebar:  boolean = true
  gridLoading:  boolean = false
  searchMode:   boolean = false
  searchQuery:  string  = ''

  private loadSubject = new Subject<void>()
  private destroy$    = new Subject<void>()

  constructor(
    private imagesService:     ImagesService,
    private categoriesService: CategoriesService,
    private route:             ActivatedRoute,
    private router:            Router
  ) {}

  ngOnInit() {
    this.loadSubject.pipe(
      switchMap(() => {
        this.gridLoading = true
        this.images      = []

        if (this.searchMode && this.searchQuery) {
          const searchFilters: Record<string, any> = {}
          if (this.filters.scene_type)          searchFilters['scene_type']  = this.filters.scene_type
          if (this.filters.people_min !== null) searchFilters['people_min']  = this.filters.people_min
          if (this.filters.quality_min)         searchFilters['quality_min'] = this.filters.quality_min

          return this.imagesService.search(this.searchQuery, searchFilters).pipe(
            catchError(() => of({ results: [] }))
          )
        }

        const params: Record<string, any> = {
          page:  this.filters.page,
          limit: this.filters.limit,
          sort:  this.filters.sort,
          order: this.filters.order
        }

        if (this.filters.scene_type)          params['scene_type']    = this.filters.scene_type
        if (this.filters.people_min !== null) params['people_min']    = this.filters.people_min
        if (this.filters.quality_min)         params['quality_min']   = this.filters.quality_min
        if (this.filters.date_from)           params['date_from']     = this.filters.date_from
        if (this.filters.date_to)             params['date_to']       = this.filters.date_to
        if (this.filters.no_duplicates)       params['no_duplicates'] = true
        if (this.filters.tags.length)         params['tag']           = this.filters.tags[0]
        if (this.filters.category)            params['category']      = this.filters.category

        return this.imagesService.getImages(params).pipe(
          catchError(() => of({ images: [], total: 0, pages: 0 }))
        )
      }),
      takeUntil(this.destroy$)
    ).subscribe((res: any) => {
      if (this.searchMode) {
        this.images       = res.results ?? []
        this.total        = this.images.length
        this.pages        = 1
        this.similarities = {}
        this.images.forEach((img: any) => {
          if (img.similarity) this.similarities[img.id] = img.similarity
        })
      } else {
        this.images = res.images ?? []
        this.total  = res.total  ?? 0
        this.pages  = res.pages  ?? 0
      }
      this.gridLoading = false
    })

    this.loadSidebarData()
  }

  loadSidebarData() {
    forkJoin({
      stats: this.categoriesService.getStats().pipe(
        catchError(() => of(null))
      ),
      tags: this.imagesService.getTagCounts().pipe(
        catchError(() => of(FALLBACK_TAGS))
      )
    }).subscribe(({ stats, tags }) => {
      if (stats !== null && stats !== undefined) {
        const perYear = (stats as StatsResponse).per_year
        if (perYear && perYear.length > 0) {
          const years  = perYear.map((y: any) => y.year)
          this.minYear = Math.min(...years)
          this.maxYear = Math.max(...years)
        }
      }
      this.tags         = tags ?? FALLBACK_TAGS
      this.sidebarReady = true

      // Read query params after sidebar data is ready
      this.route.queryParams.subscribe(params => {

        // Category card clicked on home page
        if (params['category']) {
          this.filters = { ...DEFAULT_FILTERS, category: params['category'] }
        }

        // Search from home page search bar
        if (params['mode'] === 'search' && params['q']) {
          this.searchMode  = true
          this.searchQuery = params['q']
          this.filters     = { ...this.filters, sort: 'relevance' }
        }

        this.loadImages()
      })
    })
  }

  loadImages() {
    this.loadSubject.next()
  }

  onApplyFilters(filters: FilterState) {
    // Sidebar apply clears category — sidebar doesn't know about category
    this.filters = { ...DEFAULT_FILTERS, ...filters, category: '', page: 1 }
    this.loadImages()
  }

  onClearFilters() {
    this.filters     = { ...DEFAULT_FILTERS }
    this.searchMode  = false
    this.searchQuery = ''
    this.showSidebar = false
    setTimeout(() => { this.showSidebar = true }, 0)
    this.loadImages()
  }

  onRemoveFilter(event: { key: string; value: any }) {
    if (event.key === 'tag') {
      this.filters = {
        ...this.filters,
        tags: this.filters.tags.filter(t => t !== event.value),
        page: 1
      }
    } else {
      this.filters = { ...this.filters, [event.key]: event.value, page: 1 }
    }
    this.loadImages()
  }

  onSortChange(sort: string) {
    this.filters = {
      ...this.filters,
      sort,
      order: sort === 'date_taken_asc' ? 'ASC' : 'DESC',
      page:  1
    }
    this.loadImages()
  }

  onImageClick(image: Image) {
    this.router.navigate(['/images', image.id])
  }

  onPageChange(page: number) {
    this.filters = { ...this.filters, page }
    this.loadImages()
    window.scrollTo(0, 0)
  }

  onSearch(query: string) {
    if (!query.trim()) return
    this.searchMode  = true
    this.searchQuery = query.trim()
    this.filters     = { ...this.filters, page: 1 }
    this.loadImages()
  }

  ngOnDestroy() {
    this.destroy$.next()
    this.destroy$.complete()
  }
}
