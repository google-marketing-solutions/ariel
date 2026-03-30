import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Home } from './home';
import { RouterTestingModule } from '@angular/router/testing';
import { Router } from '@angular/router';

describe('Home', () => {
  let component: Home;
  let fixture: ComponentFixture<Home>;
  let mockRouter: any;
  let store: { [key: string]: string } = {};

  const mockLocalStorage = {
    getItem: (key: string): string | null => {
      return store[key] || null;
    },
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    }
  };

  const mockMatchMedia = {
    matches: false,
    media: '',
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };

  beforeEach(async () => {
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true
    });

    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => mockMatchMedia,
    });

    mockRouter = {
      navigate: vi.fn(),
      url: '/home',
      events: {
        pipe: () => ({
          subscribe: () => {}
        })
      }
    };

    // Mock fetch for languages.json and voices.json
    vi.spyOn(window, 'fetch').mockImplementation(async (input: RequestInfo | URL) => {
      if (typeof input === 'string') {
        if (input.includes('languages.json')) {
          return new Response(JSON.stringify([
            { name: 'English', code: 'en', readiness: 'GA' },
            { name: 'Spanish', code: 'es', readiness: 'Preview' },
          ]), { status: 200 });
        }
      }
      return Promise.reject(new Error('Unexpected fetch request'));
    });

    await TestBed.configureTestingModule({
      imports: [Home, RouterTestingModule],
      providers: [
        { provide: Router, useValue: mockRouter },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Home);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should fetch languages on ngOnInit', async () => {
    await fixture.whenStable();
    expect(component.gaLanguages()).toEqual([{ name: 'English', code: 'en', readiness: 'GA' }]);
    expect(component.previewLanguages()).toEqual([{ name: 'Spanish', code: 'es', readiness: 'Preview' }]);
  });
});
