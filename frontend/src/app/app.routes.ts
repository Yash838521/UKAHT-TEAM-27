import { Routes } from '@angular/router'
import { HomeComponent } from './pages/home/home.component'
import { BrowseComponent } from './pages/browse/browse.component'
import { ImageDetailComponent } from './pages/image-detail/image-detail.component'

export const routes: Routes = [
  { path: '',             component: HomeComponent        },
  { path: 'results',      component: BrowseComponent      },
  { path: 'images/:id',   component: ImageDetailComponent },
  { path: '**',           redirectTo: ''                  }
]