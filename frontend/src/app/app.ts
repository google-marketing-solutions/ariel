import { Component, Inject, PLATFORM_ID, signal, inject } from '@angular/core';
import { RouterOutlet, Router } from '@angular/router';
import { Header } from './header/header';
import { isPlatformBrowser } from '@angular/common';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, Header],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  isDarkMode = signal(false);
  private router = inject(Router);

  constructor(@Inject(PLATFORM_ID) private platformId: Object) {
    this.initTheme();
  }

  initTheme() {
    if (isPlatformBrowser(this.platformId)) {
      const savedTheme = localStorage.getItem('color-theme');
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

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

  get isEditorRoute(): boolean {
    return this.router.url.includes('/editor');
  }

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
