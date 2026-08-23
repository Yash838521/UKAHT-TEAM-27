import { Routes } from '@angular/router'
import { HomeComponent } from './pages/home/home.component'
import { BrowseComponent } from './pages/browse/browse.component'
import { ImageDetailComponent } from './pages/image-detail/image-detail.component'
import { UploadComponent } from './pages/upload/upload.component'
import { ReviewQueueComponent } from './pages/review-queue/review-queue.component'
import { StatsComponent } from './pages/stats/stats.component'

export const routes: Routes = [
  { path: '',                  component: HomeComponent        },
  { path: 'results',           component: BrowseComponent      },
  { path: 'images/:id',        component: ImageDetailComponent },
  { path: 'upload',            component: UploadComponent      },
  { path: 'admin/corrections', component: ReviewQueueComponent },
  { path: 'analytics/stats',   component: StatsComponent       },
  { path: '**',                redirectTo: ''                  }
]