import { NgModule } from '@angular/core'
import { BrowserModule } from '@angular/platform-browser'
import { HttpClientModule } from '@angular/common/http'
import { FormsModule } from '@angular/forms'
import { RouterModule } from '@angular/router'

import { AppComponent } from './app.component'
import { HomeComponent } from './pages/home/home.component'
import { TopbarComponent } from './components/topbar/topbar.component'
import { SearchBarComponent } from './components/search-bar/search-bar.component'
import { CategoryGridComponent } from './components/category-grid/category-grid.component'
import { CategoryCardComponent } from './components/category-card/category-card.component'
import { RecentThumbnailsComponent } from './components/recent-thumbnails/recent-thumbnails.component'
import { FooterStatsComponent } from './components/footer-stats/footer-stats.component'
import { BrowseComponent } from './pages/browse/browse.component'

import { routes } from './app.routes'

@NgModule({
  declarations: [
    AppComponent,
    HomeComponent,
    TopbarComponent,
    SearchBarComponent,
    CategoryGridComponent,
    CategoryCardComponent,
    RecentThumbnailsComponent,
    FooterStatsComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    RouterModule.forRoot(routes),
    BrowseComponent
  ],
  bootstrap: [AppComponent]
})
export class AppModule {}