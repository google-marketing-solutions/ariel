import {
  Component,
  PLATFORM_ID,
  signal,
  inject,
  ChangeDetectionStrategy,
} from '@angular/core';
import {RouterOutlet, Router, NavigationEnd} from '@angular/router';
import {Header} from './header/header';
import {isPlatformBrowser} from '@angular/common';
import {toSignal} from '@angular/core/rxjs-interop';
import {filter, map} from 'rxjs/operators';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Header],
  templateUrl: './app.html',
  styleUrl: './app.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App {
  isDarkMode = signal(false);
  private router = inject(Router);
  private platformId = inject(PLATFORM_ID);

  constructor() {
    this.initTheme();
  }

  initTheme() {
    if (isPlatformBrowser(this.platformId)) {
      const savedTheme = localStorage.getItem('color-theme');
      const prefersDark = window.matchMedia(
        '(prefers-color-scheme: dark)',
      ).matches;

      if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        this.setDarkMode(true);
      } else if (savedTheme === 'light') {
        this.setDarkMode(false);
      } else {
        // Defaulting to dark since requested by user
        this.setDarkMode(true);
      }
    }
  }

  isEditorRoute = toSignal(
    this.router.events.pipe(
      filter(event => event instanceof NavigationEnd),
      map(event =>
        (event as NavigationEnd).urlAfterRedirects.includes('/editor'),
      ),
    ),
    {initialValue: this.router.url.includes('/editor')},
  );

  toggleTheme() {
    this.setDarkMode(!this.isDarkMode());
  }

  setDarkMode(isDark: boolean) {
    this.isDarkMode.set(isDark);
    if (isPlatformBrowser(this.platformId)) {
      if (isDark) {
        document.documentElement.classList.add('dark');
        localStorage.setItem('color-theme', 'dark');
      } else {
        document.documentElement.classList.remove('dark');
        localStorage.setItem('color-theme', 'light');
      }
    }
  }
}
