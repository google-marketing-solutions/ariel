import { Routes } from '@angular/router';


export const routes: Routes = [
  { path: '', loadComponent: () => import('./home/home').then(m => m.Home), title: 'Ariel - Home' },
  { path: 'library', loadComponent: () => import('./library/library').then(m => m.Library), title: 'Ariel - Library' },
  { path: 'editor', loadComponent: () => import('./editor/editor').then(m => m.Editor), title: 'Ariel - Editor' },
  { path: 'result', loadComponent: () => import('./result/result').then(m => m.Result), title: 'Ariel - Result' }
];
