import { Component, EventEmitter, Output } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'

@Component({
  selector: 'app-search-bar',
  templateUrl: './search-bar.component.html',
  styleUrls: ['./search-bar.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule]
})
export class SearchBarComponent {
  @Output() search = new EventEmitter<string>()

  query = ''

  onSearch() {
    if (this.query.trim()) {
      this.search.emit(this.query.trim())
    }
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      this.onSearch()
    }
  }
}
