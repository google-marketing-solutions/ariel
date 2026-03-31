import {
  Component,
  input,
  output,
  inject,
  ChangeDetectionStrategy,
} from '@angular/core';
import {CommonModule} from '@angular/common';
import {
  RouterLink,
  RouterLinkActive,
  Router,
  NavigationEnd,
} from '@angular/router';
import {VideoGenerationService} from '../services/video-generation.service';
import {MatTooltipModule} from '@angular/material/tooltip';
import {toSignal} from '@angular/core/rxjs-interop';
import {filter, map} from 'rxjs/operators';

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
      filter(event => event instanceof NavigationEnd),
      map(event =>
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
