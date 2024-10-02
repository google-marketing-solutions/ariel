import { LiveAnnouncer } from '@angular/cdk/a11y';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  inject,
  Input,
  Output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import {
  MatChipEditedEvent,
  MatChipInputEvent,
  MatChipsModule,
} from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';

export interface Chip {
  name: string;
}

@Component({
  selector: 'input-chips',
  templateUrl: 'input-chips.component.html',
  styleUrl: 'input-chips.component.css',
  standalone: true,
  imports: [
    MatButtonModule,
    MatFormFieldModule,
    MatChipsModule,
    FormsModule,
    MatIconModule,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InputChipsComponent {
  readonly chipsCollection = signal<Chip[]>([]);
  readonly addOnBlur = true;
  readonly separatorKeysCodes = [ENTER, COMMA] as const;
  @Input() chips: Chip[] = [];
  @Output() chipsChange = new EventEmitter<string>();
  announcer = inject(LiveAnnouncer);

  remove(chip: Chip) {
    this.chipsCollection.update(chips => {
      const index = chips.indexOf(chip);
      if (index < 0) {
        return chips;
      }

      chips.splice(index, 1);
      this.announcer.announce(`removed ${chip.name} from chips collection`);
      return [...chips];
    });
  }

  add(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();

    // Add our keyword
    if (value) {
      this.chipsCollection.update(chips => [...chips, { name: value }]);
      this.announcer.announce(`added ${value} to chips collection`);
    }

    // Clear the input value
    event.chipInput!.clear();
  }

  edit(chip: Chip, event: MatChipEditedEvent) {
    const value = event.value.trim();
    if (!value) {
      this.remove(chip);
      return;
    }
    this.chipsCollection.update(chips => {
      const index = chips.indexOf(chip);
      if (index >= 0) {
        chips[index].name = value;
        return [...chips];
      }
      return chips;
    });
  }
}
