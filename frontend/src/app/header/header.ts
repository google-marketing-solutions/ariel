import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';

@Component({
  selector: 'app-header',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './header.html',
  styleUrl: './header.scss'
})
export class Header {
  @Input() isDarkMode = false;
  @Output() toggleTheme = new EventEmitter<void>();

  private router = inject(Router);

  get isEditorRoute(): boolean {
    return this.router.url.includes('/editor');
  }

  onToggleTheme() {
    this.toggleTheme.emit();
  }
}
