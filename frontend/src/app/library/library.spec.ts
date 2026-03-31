import {ComponentFixture, TestBed} from '@angular/core/testing';
import {Library} from './library';
import {provideRouter} from '@angular/router';

describe('Library', () => {
  let component: Library;
  let fixture: ComponentFixture<Library>;

  const mockVideos = [
    {
      video_id: 'video1',
      name: 'Test Video 1',
      url: 'http://test.com/v1.mp4',
      download_url: 'http://test.com/v1_dl.mp4',
      created_at: 1711800000,
      original_language: 'en',
      translate_language: 'es',
      duration: 125,
      speakers: [
        {id: 's1', name: 'Alice', voice: 'AliceVoice', gender: 'female'},
      ],
      has_metadata: true,
    },
    {
      video_id: 'video2',
      name: 'Test Video 2',
      url: 'http://test.com/v2.mp4',
      download_url: 'http://test.com/v2_dl.mp4',
      created_at: 1711800000,
      original_language: 'en',
      translate_language: 'fr',
      duration: 60,
      speakers: [{id: 's2', name: 'Bob', voice: 'BobVoice', gender: 'male'}],
      has_metadata: false,
    },
  ];

  beforeEach(async () => {
    // Mock fetch
    window.fetch = vi
      .fn()
      .mockImplementation(
        async (input: RequestInfo | URL, init?: RequestInit) => {
          const url =
            typeof input === 'string' ? input : (input as URL).toString();

          if (url.includes('/api/videos')) {
            let responseData;
            if (url.includes('page_token=token123')) {
              responseData = {
                videos: [mockVideos[1]],
                next_page_token: null,
              };
            } else {
              responseData = {
                videos: [mockVideos[0]],
                next_page_token: 'token123',
              };
            }

            return {
              ok: true,
              status: 200,
              json: async () => responseData,
            } as Response;
          }

          if (url.includes('/api/videos/video1') && init?.method === 'DELETE') {
            return {
              ok: true,
              status: 200,
            } as Response;
          }

          return Promise.reject(new Error(`Unexpected fetch request: ${url}`));
        },
      );

    await TestBed.configureTestingModule({
      imports: [Library],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(Library);
    component = fixture.componentInstance;
  });

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should fetch and display videos on init', async () => {
    fixture.detectChanges(); // ngOnInit -> fetchVideos(true)
    await fixture.whenStable();
    await new Promise(resolve => setTimeout(resolve, 100));
    fixture.detectChanges();

    expect(component.videos().length).toBe(1);

    const videoCards = fixture.nativeElement.querySelectorAll('.video-card');
    expect(videoCards.length).toBe(1);
    expect(videoCards[0].querySelector('h3').textContent).toContain(
      'Test Video 1',
    );
    expect(component.nextPageToken()).toBe('token123');
  });

  it('should load more videos when clicking "Load more"', async () => {
    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise(resolve => setTimeout(resolve, 100));
    fixture.detectChanges();

    const loadMoreBtn = fixture.nativeElement.querySelector('.load-more-btn');
    expect(loadMoreBtn).toBeTruthy();

    loadMoreBtn.click();

    await fixture.whenStable();
    await new Promise(resolve => setTimeout(resolve, 100));
    fixture.detectChanges();

    expect(component.videos().length).toBe(2);
    const videoCards = fixture.nativeElement.querySelectorAll('.video-card');
    expect(videoCards.length).toBe(2);
    expect(component.nextPageToken()).toBeNull();
  });

  it('should show error message if fetch fails', async () => {
    vi.mocked(window.fetch).mockRejectedValueOnce(new Error('Network error'));

    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise(resolve => setTimeout(resolve, 100));
    fixture.detectChanges();

    const errorAlert = fixture.nativeElement.querySelector('.error-alert');
    expect(errorAlert).toBeTruthy();
    expect(errorAlert.textContent).toContain('Network error');
  });

  it('should open delete modal and delete a video', async () => {
    fixture.detectChanges();
    await fixture.whenStable();
    await new Promise(resolve => setTimeout(resolve, 100));
    fixture.detectChanges();

    const videoCards = fixture.nativeElement.querySelectorAll('.video-card');
    expect(videoCards.length).toBe(1);

    const deleteBtn = videoCards[0].querySelector('.delete-btn');
    expect(deleteBtn).toBeTruthy();
    deleteBtn.click();
    fixture.detectChanges();

    expect(component.isDeleteModalOpen()).toBe(true);
    expect(component.pendingDeleteVideoId()).toBe('video1');

    const confirmBtn = fixture.nativeElement.querySelector('.confirm-btn');
    expect(confirmBtn).toBeTruthy();

    // Clear fetch spy to check for subsequent calls
    vi.mocked(window.fetch).mockClear();

    // Mock for delete and subsequent fetch
    vi.mocked(window.fetch)
      .mockResolvedValueOnce({ok: true, status: 200} as Response)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({videos: [], next_page_token: null}),
      } as Response);

    confirmBtn.click();
    fixture.detectChanges();

    await fixture.whenStable();
    await new Promise(resolve => setTimeout(resolve, 100));
    fixture.detectChanges();

    expect(component.isDeleteModalOpen()).toBe(false);
    expect(window.fetch).toHaveBeenCalledWith(
      '/api/videos/video1',
      expect.objectContaining({method: 'DELETE'}),
    );
  });
});
