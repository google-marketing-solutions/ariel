import { Component, input, output, inject, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive, Router } from '@angular/router';
import { VideoGenerationService } from '../services/video-generation.service';
import { MatTooltipModule } from '@angular/material/tooltip';

@Component({
  selector: 'app-header',
  imports: [CommonModule, RouterLink, RouterLinkActive, MatTooltipModule],
  templateUrl: './header.html',
  styleUrl: './header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class Header {
  isDarkMode = input(false);
  toggleTheme = output<void>();

  private router = inject(Router);
  videoGenerationService = inject(VideoGenerationService);

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
