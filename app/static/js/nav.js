/**
 * Navigation functionality
 */

(function() {
    'use strict';
    
    // Mobile navigation toggle
    const navToggle = document.getElementById('nav-toggle');
    const navMenu = document.getElementById('nav-menu');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function() {
            navToggle.classList.toggle('active');
            navMenu.classList.toggle('active');
            
            // Update aria-expanded
            const isExpanded = navMenu.classList.contains('active');
            navToggle.setAttribute('aria-expanded', isExpanded);
        });
        
        // Close menu when clicking a nav link
        navMenu.querySelectorAll('.nav-link').forEach(function(link) {
            link.addEventListener('click', function() {
                navToggle.classList.remove('active');
                navMenu.classList.remove('active');
                navToggle.setAttribute('aria-expanded', 'false');
            });
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!navToggle.contains(e.target) && !navMenu.contains(e.target)) {
                navToggle.classList.remove('active');
                navMenu.classList.remove('active');
                navToggle.setAttribute('aria-expanded', 'false');
            }
        });
    }
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            const target = document.querySelector(href);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Header scroll effect
    const header = document.getElementById('site-header');
    if (header) {
        let lastScroll = 0;
        
        window.addEventListener('scroll', function() {
            const currentScroll = window.pageYOffset;
            
            // Add shadow when scrolled
            if (currentScroll > 10) {
                header.style.boxShadow = 'var(--shadow-md)';
            } else {
                header.style.boxShadow = 'var(--shadow-sm)';
            }
            
            lastScroll = currentScroll;
        }, { passive: true });
    }
})();

// YouTube embed loading
function loadYouTube(placeholder) {
    const container = placeholder.closest('.media-youtube');
    const url = container.dataset.youtubeUrl;
    
    if (!url) return;
    
    // Extract video ID from various YouTube URL formats
    let videoId = null;
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/
    ];
    
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) {
            videoId = match[1];
            break;
        }
    }
    
    if (!videoId) return;
    
    // Replace placeholder with iframe
    const iframe = document.createElement('iframe');
    iframe.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1`;
    iframe.width = '100%';
    iframe.height = '100%';
    iframe.frameBorder = '0';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
    iframe.allowFullscreen = true;
    iframe.style.position = 'absolute';
    iframe.style.inset = '0';
    
    container.style.position = 'relative';
    container.innerHTML = '';
    container.appendChild(iframe);
}

// Extract YouTube video ID from URL
function getYouTubeVideoId(url) {
    if (!url) return null;
    const patterns = [
        /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/
    ];
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match) return match[1];
    }
    return null;
}

// Set YouTube thumbnails on page load
(function() {
    document.querySelectorAll('.media-youtube').forEach(function(container) {
        const url = container.dataset.youtubeUrl;
        const videoId = getYouTubeVideoId(url);
        
        if (videoId) {
            const placeholder = container.querySelector('.youtube-placeholder');
            if (placeholder) {
                placeholder.style.backgroundImage = `url('https://img.youtube.com/vi/${videoId}/hqdefault.jpg')`;
            }
        }
    });
})();

// Audio embed loading
function loadAudio(placeholder) {
    const container = placeholder.closest('.media-audio');
    const url = container.dataset.audioUrl;
    const provider = container.dataset.provider;
    
    if (!url) return;
    
    let embedUrl = null;
    
    if (provider === 'spotify') {
        // Convert Spotify URL to embed URL
        const match = url.match(/spotify\.com\/(track|album|playlist|artist)\/([a-zA-Z0-9]+)/);
        if (match) {
            embedUrl = `https://open.spotify.com/embed/${match[1]}/${match[2]}`;
        }
    } else if (provider === 'soundcloud') {
        // SoundCloud embeds require their widget API
        embedUrl = `https://w.soundcloud.com/player/?url=${encodeURIComponent(url)}&color=%23ff5500&auto_play=true`;
    }
    
    if (!embedUrl) return;
    
    const iframe = document.createElement('iframe');
    iframe.src = embedUrl;
    iframe.width = '100%';
    iframe.height = provider === 'spotify' ? '152' : '166';
    iframe.frameBorder = '0';
    iframe.allow = 'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture';
    iframe.loading = 'lazy';
    
    container.innerHTML = '';
    container.appendChild(iframe);
}

// ========================================
// Lightbox Component
// ========================================
(function() {
    'use strict';
    
    // Create lightbox elements
    const overlay = document.createElement('div');
    overlay.className = 'lightbox-overlay';
    overlay.innerHTML = `
        <button class="lightbox-close" aria-label="Schließen">&times;</button>
        <img class="lightbox-image" src="" alt="">
        <button class="lightbox-prev" aria-label="Vorheriges Bild">&#10094;</button>
        <button class="lightbox-next" aria-label="Nächstes Bild">&#10095;</button>
    `;
    
    let currentGroup = [];
    let currentIndex = 0;
    let initialized = false;
    
    function initLightbox() {
        if (initialized) return;
        initialized = true;
        
        document.body.appendChild(overlay);
        
        const closeBtn = overlay.querySelector('.lightbox-close');
        const prevBtn = overlay.querySelector('.lightbox-prev');
        const nextBtn = overlay.querySelector('.lightbox-next');
        const lightboxImg = overlay.querySelector('.lightbox-image');
        
        // Close handlers
        closeBtn.addEventListener('click', closeLightbox);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) {
                closeLightbox();
            }
        });
        
        // Navigation handlers
        prevBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            showImage(currentIndex - 1);
        });
        
        nextBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            showImage(currentIndex + 1);
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (!overlay.classList.contains('active')) return;
            
            if (e.key === 'Escape') {
                closeLightbox();
            } else if (e.key === 'ArrowLeft') {
                showImage(currentIndex - 1);
            } else if (e.key === 'ArrowRight') {
                showImage(currentIndex + 1);
            }
        });
    }
    
    function openLightbox(img) {
        initLightbox();
        
        const groupName = img.dataset.lightbox;
        const allInGroup = document.querySelectorAll(`[data-lightbox="${groupName}"]`);
        
        currentGroup = Array.from(allInGroup);
        currentIndex = currentGroup.indexOf(img);
        
        showImage(currentIndex);
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    function closeLightbox() {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    function showImage(index) {
        if (index < 0) index = currentGroup.length - 1;
        if (index >= currentGroup.length) index = 0;
        
        currentIndex = index;
        const img = currentGroup[currentIndex];
        const lightboxImg = overlay.querySelector('.lightbox-image');
        
        // Use data-full-src if available, otherwise use the src
        lightboxImg.src = img.dataset.fullSrc || img.src;
        lightboxImg.alt = img.alt || '';
        
        // Show/hide navigation for single images
        const prevBtn = overlay.querySelector('.lightbox-prev');
        const nextBtn = overlay.querySelector('.lightbox-next');
        const showNav = currentGroup.length > 1;
        prevBtn.style.display = showNav ? 'flex' : 'none';
        nextBtn.style.display = showNav ? 'flex' : 'none';
    }
    
    // Attach click handlers to lightbox images
    document.querySelectorAll('[data-lightbox]').forEach(function(img) {
        img.style.cursor = 'pointer';
        img.addEventListener('click', function(e) {
            e.preventDefault();
            openLightbox(img);
        });
    });
})();
