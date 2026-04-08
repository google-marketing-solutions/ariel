import {CommonModule} from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  output,
} from '@angular/core';
import {toSignal} from '@angular/core/rxjs-interop';
import {MatTooltipModule} from '@angular/material/tooltip';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
} from '@angular/router';
import {filter, map} from 'rxjs/operators';
import {VideoGenerationService} from '../services/video-generation.service';

@Component({
  selector: 'app-header',
  imports: [CommonModule, RouterLink, RouterLinkActive, MatTooltipModule],
  templateUrl: './header.html',
  styleUrl: './header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Header {
  isDarkMode = input(false);
  toggleTheme = output<void>();

  private router = inject(Router);
  videoGenerationService = inject(VideoGenerationService);

  isEditorRoute = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map((event) =>
        (event as NavigationEnd).urlAfterRedirects.includes('/editor'),
      ),
    ),
    {initialValue: this.router.url.includes('/editor')},
  );

  onToggleTheme() {
    this.toggleTheme.emit();
  }

  generateVideo() {
    if (this.isEditorRoute()) {
      this.videoGenerationService.triggerGenerateVideo();
    }
  }
}
