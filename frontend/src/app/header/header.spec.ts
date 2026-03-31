import {ComponentFixture, TestBed} from '@angular/core/testing';
import {Header} from './header';
import {provideRouter, Router, NavigationEnd} from '@angular/router';
import {VideoGenerationService} from '../services/video-generation.service';
import {MatTooltipModule} from '@angular/material/tooltip';
import {Subject} from 'rxjs'; // 'of' is from rxjs, 'Subject' for router.events
import {signal, WritableSignal} from '@angular/core'; // 'signal' and 'WritableSignal' is from @angular/core

describe('Header', () => {
  let component: Header;
  let fixture: ComponentFixture<Header>;
  let mockRouter: any;
  let mockVideoGenerationService: any;
  let navigationEndSubject: Subject<NavigationEnd>; // Declare here to be accessible
  let mockRouterUrlGetter: any; // Declare this to hold the mock getter
  let mockIsEditorRouteSignal: WritableSignal<boolean>; // Mock the signal directly

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
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => mockMatchMedia,
    });

    // Initialize the Subject before TestBed configuration
    navigationEndSubject = new Subject<NavigationEnd>();
    mockIsEditorRouteSignal = signal(false); // Initialize the mock signal

    mockVideoGenerationService = {
      triggerGenerateVideo: vi.fn(),
      unregeneratedCount: signal(0),
      isProcessingAudio: signal(false),
    };

    await TestBed.configureTestingModule({
      imports: [Header, MatTooltipModule],
      providers: [
        provideRouter([]),
        {provide: VideoGenerationService, useValue: mockVideoGenerationService},
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Header);
    component = fixture.componentInstance;

    // Get the Router instance from the injector and spy on its methods
    mockRouter = TestBed.inject(Router);
    vi.spyOn(mockRouter, 'navigate');

    // Set the initial URL for the router directly for `isEditorRoute` initialValue
    mockRouterUrlGetter = vi.fn().mockReturnValue('/home');
    Object.defineProperty(mockRouter, 'url', {
      get: mockRouterUrlGetter,
    });

    // Manually set up router events for testing isEditorRoute signal
    Object.defineProperty(mockRouter, 'events', {
      value: navigationEndSubject.asObservable(),
      writable: true,
    });

    // Directly set the component's isEditorRoute signal
    Object.defineProperty(component, 'isEditorRoute', {
      value: mockIsEditorRouteSignal,
      writable: true,
    });

    // Emit initial event to simulate router state
    navigationEndSubject.next(new NavigationEnd(1, '/home', '/home'));

    fixture.detectChanges();
  });

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should toggle theme on button click', () => {
    vi.spyOn(component.toggleTheme, 'emit');
    const themeToggleButton =
      fixture.nativeElement.querySelector('.theme-toggle-btn');
    themeToggleButton.click();
    expect(component.toggleTheme.emit).toHaveBeenCalled();
  });

  it('should call generateVideoService.triggerGenerateVideo when generate video button is clicked on editor route', async () => {
    mockRouterUrlGetter.mockReturnValue('/editor'); // Change the URL getter
    mockIsEditorRouteSignal.set(true); // Directly set the signal
    navigationEndSubject.next(new NavigationEnd(1, '/editor', '/editor')); // Still emit for completeness, though not directly driving isEditorRoute now
    fixture.detectChanges();
    await fixture.whenStable(); // Wait for the DOM to update

    const generateVideoButton =
      fixture.nativeElement.querySelector('.generate-btn');
    expect(generateVideoButton).toBeTruthy(); // Ensure the button exists for the editor route
    generateVideoButton.click();
    expect(mockVideoGenerationService.triggerGenerateVideo).toHaveBeenCalled();
  });

  it('should not call generateVideoService.triggerGenerateVideo when generate video button is clicked on non-editor route', async () => {
    mockRouterUrlGetter.mockReturnValue('/home'); // Change the URL getter
    mockIsEditorRouteSignal.set(false); // Directly set the signal
    navigationEndSubject.next(new NavigationEnd(1, '/home', '/home'));
    fixture.detectChanges();
    await fixture.whenStable(); // Wait for the DOM to update

    const generateVideoButton =
      fixture.nativeElement.querySelector('.generate-btn');
    expect(generateVideoButton).toBeFalsy(); // Ensure the button does not exist for non-editor route
    // Even if we somehow clicked it, it shouldn't be called
    expect(
      mockVideoGenerationService.triggerGenerateVideo,
    ).not.toHaveBeenCalled();
  });

  it('should display unregenerated count', async () => {
    // Ensure we are on an editor route for the warning info to be displayed
    mockRouterUrlGetter.mockReturnValue('/editor');
    mockIsEditorRouteSignal.set(true); // Directly set the signal
    navigationEndSubject.next(new NavigationEnd(1, '/editor', '/editor'));
    fixture.detectChanges(); // First detect changes to update isEditorRoute
    await fixture.whenStable(); // Wait for the DOM to update

    mockVideoGenerationService.unregeneratedCount.set(5);
    fixture.detectChanges(); // Trigger change detection again after signal update
    await fixture.whenStable(); // Wait for the DOM to update

    const warningInfo = fixture.nativeElement.querySelector('.warning-info');
    expect(warningInfo).toBeTruthy();
    expect(warningInfo.textContent).toContain('5 change(s) need regeneration');
  });

  it('should disable generate video button when audio is processing', async () => {
    mockRouterUrlGetter.mockReturnValue('/editor');
    mockIsEditorRouteSignal.set(true); // Directly set the signal
    navigationEndSubject.next(new NavigationEnd(1, '/editor', '/editor'));
    mockVideoGenerationService.isProcessingAudio.set(true);
    fixture.detectChanges();
    await fixture.whenStable(); // Wait for the DOM to update

    const generateVideoButton =
      fixture.nativeElement.querySelector('.generate-btn');
    expect(generateVideoButton.disabled).toBe(true);
  });
});
