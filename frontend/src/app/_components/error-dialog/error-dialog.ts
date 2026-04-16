import {CommonModule} from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
} from '@angular/core';

/**
 * Common component to be used when an error dialog is shown.
 *
 * When used, a message to be shown is passed as the "message" prop.
 * The function to run when the close button is clicked is passed as
 * the "close" prop.
 */
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
  @Output() readonly close = new EventEmitter<void>();
}
