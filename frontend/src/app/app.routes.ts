import { Routes } from '@angular/router';
import { Home } from './home/home';
import { Library } from './library/library';
import { Editor } from './editor/editor';
import { Result } from './result/result';

export const routes: Routes = [
  { path: '', component: Home, title: 'Ariel v2.0 - Home' },
  { path: 'library', component: Library, title: 'Ariel v2.0 - Library' },
  { path: 'editor', component: Editor, title: 'Ariel v2.0 - Editor' },
  { path: 'result', component: Result, title: 'Ariel v2.0 - Result' }
];
