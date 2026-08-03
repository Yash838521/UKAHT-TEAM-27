import { Routes } from '@angular/router'
import { HomeComponent } from './pages/home/home.component'
import { BrowseComponent } from './pages/browse/browse.component'

export const routes: Routes = [
  { path: '',        component: HomeComponent   },
  { path: 'results', component: BrowseComponent },
  { path: '**',      redirectTo: ''             }
]
