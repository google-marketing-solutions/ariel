import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { VideoGenerationService } from '../services/video-generation.service';

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
  private videoGenerationService = inject(VideoGenerationService);

  get isEditorRoute(): boolean {
    return this.router.url.includes('/editor');
  }

  onToggleTheme() {
    this.toggleTheme.emit();
  }

  generateVideo() {
    if (this.isEditorRoute) {
      this.videoGenerationService.triggerGenerateVideo();
    }
  }
}
