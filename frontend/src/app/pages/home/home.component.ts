import { Component, OnInit } from '@angular/core'
import { CommonModule } from '@angular/common'
import { Router } from '@angular/router'
import { forkJoin, of } from 'rxjs'
import { catchError } from 'rxjs/operators'
import { CategoriesService } from '../../services/categories.service'
import { ImagesService } from '../../services/images.service'
import { Category, Image } from '../../models'
import { TopbarComponent } from '../../components/topbar/topbar.component'
import { SearchBarComponent } from '../../components/search-bar/search-bar.component'
import { CategoryGridComponent } from '../../components/category-grid/category-grid.component'
import { RecentThumbnailsComponent } from '../../components/recent-thumbnails/recent-thumbnails.component'
import { FooterStatsComponent } from '../../components/footer-stats/footer-stats.component'

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    TopbarComponent,
    SearchBarComponent,
    CategoryGridComponent,
    RecentThumbnailsComponent,
    FooterStatsComponent
  ]
})
export class HomeComponent implements OnInit {
  categories:   Category[] = []
  recentImages: Image[]    = []
  totalImages:  number     = 0
  uniqueImages: number     = 0
  pending:      number     = 0
  dateRange:    string     = ''
  loading:      boolean    = true
  error:        string     = ''

  constructor(
    private categoriesService: CategoriesService,
    private imagesService:     ImagesService,
    private router:            Router
  ) {}

  ngOnInit() {
    // Load all home page data in parallel
    forkJoin({
      categories: this.categoriesService.getCategories().pipe(
        catchError(() => of(null))
      ),
      recent: this.imagesService.getRecent(10).pipe(
        catchError(() => of([]))
      ),
      stats: this.categoriesService.getStats().pipe(
        catchError(() => of(null))
      )
    }).subscribe(({ categories, recent, stats }) => {

      if (categories) {
        this.categories  = categories.categories
        this.totalImages = categories.total_images
        this.pending     = categories.pending
      }

      this.recentImages = recent ?? []

      if (stats) {
        // Unique = total minus images that are duplicates
        this.uniqueImages = stats.total_images - (stats.duplicates?.in_clusters ?? 0)

        // Date range from actual data
        if (stats.per_year && stats.per_year.length > 0) {
          const years      = stats.per_year.map(y => y.year)
          const minYear    = Math.min(...years)
          const maxYear    = Math.max(...years)
          this.dateRange   = `${minYear}–${maxYear}`
        }
      }

      this.loading = false
    })
  }

  onSearch(query: string) {
    this.router.navigate(['/results'], {
      queryParams: { mode: 'search', q: query }
    })
  }

  onCategoryClick(category: string) {
    this.router.navigate(['/results'], {
      queryParams: { category }
    })
  }
}
