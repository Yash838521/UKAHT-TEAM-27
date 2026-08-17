import { Component, Input, Output, EventEmitter } from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'

@Component({
  selector: 'app-sort-bar',
  templateUrl: './sort-bar.component.html',
  styleUrls: ['./sort-bar.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule]
})
export class SortBarComponent {
  @Input()  total:      number  = 0
  @Input()  sort:       string  = 'overall_score'
  @Input()  searchMode: boolean = false
  @Output() sortChange          = new EventEmitter<string>()

  browseOptions = [
    { label: 'Best quality', value: 'overall_score'   },
    { label: 'Newest first', value: 'date_taken_desc' },
    { label: 'Oldest first', value: 'date_taken_asc'  },
    { label: 'People count', value: 'people_count'    },
  ]

  searchOptions = [
    { label: 'Relevance',   value: 'relevance'        },
    { label: 'Best quality', value: 'overall_score'   },
    { label: 'Newest first', value: 'date_taken_desc' },
    { label: 'Oldest first', value: 'date_taken_asc'  },
  ]

  get sortOptions() {
    return this.searchMode ? this.searchOptions : this.browseOptions
  }

  onSortChange(value: string) {
    this.sortChange.emit(value)
  }
}
