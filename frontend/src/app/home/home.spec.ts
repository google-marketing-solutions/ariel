import {ComponentFixture, TestBed} from '@angular/core/testing';
import {Router} from '@angular/router';
import {RouterTestingModule} from '@angular/router/testing';
import {Home} from './home';

describe('Home', () => {
  let component: Home;
  let fixture: ComponentFixture<Home>;
  let mockRouter: any;
  let store: {[key: string]: string} = {};

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
    },
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
      writable: true,
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
          subscribe: () => {},
        }),
      },
    };

    // Mock fetch for languages.json and voices.json
    vi.spyOn(window, 'fetch').mockImplementation(
      async (input: RequestInfo | URL) => {
        if (typeof input === 'string') {
          if (input.includes('languages.json')) {
            return new Response(
              JSON.stringify([
                {name: 'English', code: 'en', readiness: 'GA'},
                {name: 'Spanish', code: 'es', readiness: 'Preview'},
              ]),
              {status: 200},
            );
          }
        }
        return Promise.reject(new Error('Unexpected fetch request'));
      },
    );

    await TestBed.configureTestingModule({
      imports: [Home, RouterTestingModule],
      providers: [{provide: Router, useValue: mockRouter}],
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
    expect(component.gaLanguages()).toEqual([
      {name: 'English', code: 'en', readiness: 'GA'},
    ]);
    expect(component.previewLanguages()).toEqual([
      {name: 'Spanish', code: 'es', readiness: 'Preview'},
    ]);
  });

  describe('video processing errors', () => {
    beforeEach(() => {
      // Clear previous fetch mocks for each test in this describe block
      vi.restoreAllMocks();
    });

    it('should show an error dialog when backend returns 413 error', async () => {
      // Mock fetch for /process endpoint to return 413
      vi.spyOn(window, 'fetch').mockImplementation(
        async (input: RequestInfo | URL) => {
          if (typeof input === 'string' && input.includes('/process')) {
            return new Response('Payload Too Large', {status: 413, statusText: 'Payload Too Large'});
          }
          // Fallback for other fetch requests, e.g., languages.json
          return new Response(
            JSON.stringify([
              {name: 'English', code: 'en', readiness: 'GA'},
              {name: 'Spanish', code: 'es', readiness: 'Preview'},
            ]),
            {status: 200},
          );
        },
      );

      // Simulate file selection
      const mockFile = new File(['test content'], 'test-video.mp4', {type: 'video/mp4'});
      component.selectedVideoFile.set(mockFile);
      component.translationLanguage.set('en'); // Set a language for the form to be valid

      // Trigger video processing
      await component.processVideo();

      // Wait for the DOM to update after signal changes
      fixture.detectChanges();
      await fixture.whenStable();

      // Assert that the error dialog is shown
      expect(component.showErrorDialog()).toBe(true);
      expect(component.errorMessage()).toBe('The uploaded file is too large. Please select a smaller file.');

      // Assert that the error message is rendered in the DOM
      const errorDialog = fixture.nativeElement.querySelector('app-error-dialog');
      expect(errorDialog).toBeTruthy();
      expect(errorDialog.textContent).toContain('The uploaded file is too large. Please select a smaller file.');
    });
  });
});
