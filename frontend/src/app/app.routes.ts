import { Routes } from '@angular/router';
import { Home } from './home/home';
import { Library } from './library/library';
import { Editor } from './editor/editor';
import { Result } from './result/result';

export const routes: Routes = [
  { path: '', component: Home, title: 'Ariel - Home' },
  { path: 'library', component: Library, title: 'Ariel - Library' },
  { path: 'editor', component: Editor, title: 'Ariel - Editor' },
  { path: 'result', component: Result, title: 'Ariel - Result' }
];
