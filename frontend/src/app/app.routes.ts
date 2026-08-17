// ── ADD TO src/app/app.routes.ts ─────────────────────────────────────────────

// Add this import at the top:
// import { ReviewQueueComponent } from './pages/review-queue/review-queue.component'

// Add this route to the routes array:
// { path: 'admin/corrections', component: ReviewQueueComponent }

// Full updated routes array:
import { Routes } from '@angular/router'
import { HomeComponent } from './pages/home/home.component'
import { BrowseComponent } from './pages/browse/browse.component'
import { ImageDetailComponent } from './pages/image-detail/image-detail.component'
import { UploadComponent } from './pages/upload/upload.component'
import { ReviewQueueComponent } from './pages/review-queue/review-queue.component'

export const routes: Routes = [
  { path: '',                 component: HomeComponent        },
  { path: 'results',          component: BrowseComponent      },
  { path: 'images/:id',       component: ImageDetailComponent },
  { path: 'upload',           component: UploadComponent      },
  { path: 'admin/corrections', component: ReviewQueueComponent },
  { path: '**',               redirectTo: ''                  }
]