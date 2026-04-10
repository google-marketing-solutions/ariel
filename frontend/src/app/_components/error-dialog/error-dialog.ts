import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-error-dialog',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './error-dialog.html',
  styleUrls: ['./error-dialog.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ErrorDialog {
  @Input() message = '';
  @Output() close = new EventEmitter<void>();
}
