import { Component, Input, Output, EventEmitter } from '@angular/core'
import { CommonModule } from '@angular/common'

@Component({
  selector: 'app-category-card',
  templateUrl: './category-card.component.html',
  styleUrls: ['./category-card.component.scss'],
  standalone: true,
  imports: [CommonModule]
})
export class CategoryCardComponent {
  @Input()  name:  string = ''
  @Input()  count: number = 0
  @Input()  icon:  string = ''
  @Input()  color: string = '#4a9eff'
  @Output() categoryClick = new EventEmitter<string>()

  onClick() {
    this.categoryClick.emit(this.name)
  }
}
