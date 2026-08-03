import { Component, OnInit } from '@angular/core'
import { Router } from '@angular/router'
import { CategoriesService } from '../../services/categories.service'
import { ImagesService } from '../../services/images.service'
import { Category, Image } from '../../models'
import { FooterStatsComponent } from '../../components/footer-stats/footer-stats.component';
import { RecentThumbnailsComponent } from '../../components/recent-thumbnails/recent-thumbnails.component'
import { CategoryGridComponent } from '../../components/category-grid/category-grid.component'
import { SearchBarComponent } from '../../components/search-bar/search-bar.component'
import { TopbarComponent } from '../../components/topbar/topbar.component'
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    FooterStatsComponent,
    RecentThumbnailsComponent,
    CategoryGridComponent,
    SearchBarComponent,
    TopbarComponent
  ],
})
export class HomeComponent implements OnInit {
  categories: Category[] = []
  recentImages: Image[]  = []
  totalImages: number    = 0
  uniqueImages: number   = 0
  pending: number        = 0
  dateRange: string      = ''
  loading: boolean       = true
  error: string          = ''

  constructor(
    private categoriesService: CategoriesService,
    private imagesService:     ImagesService,
    private router:            Router
  ) {}

  ngOnInit() {
    this.loadCategories()
    this.loadRecentImages()
    this.loadStats()
  }

  loadCategories() {
    this.categoriesService.getCategories().subscribe({
      next: (res) => {
        this.categories  = res.categories
        this.totalImages = res.total_images
        this.pending     = res.pending
        this.loading     = false
      },
      error: (err) => {
        this.error   = 'Failed to load categories'
        this.loading = false
        console.error(err)
      }
    })
  }

  loadRecentImages() {
    this.imagesService.getRecent(10).subscribe({
      next:  (images) => { this.recentImages = images },
      error: (err)    => console.error(err)
    })
  }

  loadStats() {
    this.categoriesService.getStats().subscribe({
      next: (stats) => {
        this.uniqueImages = stats.total_images - stats.duplicates.in_clusters
        if (stats.per_year.length > 0) {
          const years      = stats.per_year.map(y => y.year)
          const minYear    = Math.min(...years)
          const maxYear    = Math.max(...years)
          this.dateRange   = `${minYear}–${maxYear}`
        }
      },
      error: (err) => console.error(err)
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
