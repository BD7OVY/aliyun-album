/**
 * Gallery app logic
 * - Password gate (SHA-256 via SubtleCrypto)
 * - Masonry grid with lazy loading + infinite scroll
 * - Lightbox with keyboard navigation
 */

(function () {
  'use strict';

  // ── State ──────────────────────────────────────
  let PHOTOS = [];
  let RENDERED = 0;
  const PAGE_SIZE = 30;
  let currentLbIndex = -1;

  // ── DOM refs ───────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const gate = $('gate');
  const gallery = $('gallery');
  const grid = $('grid');
  const sentinel = $('sentinel');
  const lightbox = $('lightbox');
  const lbImage = $('lb-image');
  const lbName = $('lb-name');
  const lbOriginal = $('lb-original');

  // ── Init ───────────────────────────────────────
  async function init() {
    try {
      const resp = await fetch('data.json');
      if (!resp.ok) throw new Error('data.json not found');
      const data = await resp.json();

      // Update title
      const g = data.gallery || {};
      document.title = g.title || '共享相册';
      $('gallery-title').textContent = g.title || '共享相册';
      $('gallery-subtitle').textContent = g.subtitle || '';
      $('gate-title').textContent = g.title || '共享相册';

      PHOTOS = data.photos || [];
      $('photo-count').textContent = `共 ${PHOTOS.length} 张照片`;

      // If no password set, skip gate (testing mode)
      if (!data.password_hash) {
        unlockGallery();
      } else {
        setupGate(data.password_hash);
      }
    } catch (e) {
      console.error('Init failed:', e);
      $('gate-error').textContent = '相册数据加载失败，请检查 data.json';
    }
  }

  // ── Password Gate ──────────────────────────────
  function setupGate(expectedHash) {
    const input = $('gate-input');
    const btn = $('gate-btn');

    const tryUnlock = async () => {
      const pw = input.value;
      if (!pw) return;
      const hash = await sha256(pw);
      if (hash === expectedHash) {
        unlockGallery();
      } else {
        $('gate-error').textContent = '密码错误，请重试';
        input.value = '';
        input.focus();
        // Shake animation
        btn.style.animation = 'none';
        void btn.offsetWidth;
        btn.style.animation = 'shake 0.4s';
      }
    };

    btn.addEventListener('click', tryUnlock);
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') tryUnlock();
    });
    input.focus();
  }

  async function sha256(text) {
    const buf = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(hash))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
  }

  function unlockGallery() {
    gate.style.opacity = '0';
    setTimeout(() => {
      gate.style.display = 'none';
      gallery.style.display = 'block';
      renderBatch();
      setupScrollObserver();
    }, 400);
  }

  // ── Rendering ──────────────────────────────────
  function renderBatch() {
    const end = Math.min(RENDERED + PAGE_SIZE, PHOTOS.length);
    if (RENDERED >= end) return;

    for (let i = RENDERED; i < end; i++) {
      const photo = PHOTOS[i];
      const item = document.createElement('div');
      item.className = 'photo-item';
      item.style.animationDelay = `${(i - RENDERED) * 0.03}s`;
      item.dataset.index = i;

      // Determine aspect ratio for placeholder
      let ratio = '3 / 4';
      if (photo.dimensions) {
        ratio = `${photo.dimensions.width} / ${photo.dimensions.height}`;
      }

      const img = document.createElement('img');
      img.dataset.src = `thumbnails/${photo.thumbnail}`;
      img.alt = photo.name;
      img.style.aspectRatio = ratio;
      img.loading = 'lazy';
      img.classList.add('skeleton');

      img.addEventListener('load', () => {
        img.classList.remove('skeleton');
      });

      item.appendChild(img);
      item.addEventListener('click', () => openLightbox(i));

      grid.appendChild(item);
      lazyObserver.observe(img);
    }

    RENDERED = end;
  }

  // ── Lazy Loading ───────────────────────────────
  const lazyObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        if (img.dataset.src) {
          img.src = img.dataset.src;
          delete img.dataset.src;
        }
        lazyObserver.unobserve(img);
      }
    });
  }, { rootMargin: '200px' });

  // ── Infinite Scroll ────────────────────────────
  function setupScrollObserver() {
    const scrollObserver = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && RENDERED < PHOTOS.length) {
        renderBatch();
      }
    }, { rootMargin: '300px' });
    scrollObserver.observe(sentinel);
  }

  // ── Lightbox ───────────────────────────────────
  function openLightbox(index) {
    currentLbIndex = index;
    const photo = PHOTOS[index];

    lbImage.src = `thumbnails/${photo.thumbnail}`;
    lbImage.alt = photo.name;
    lbName.textContent = photo.name;
    lbOriginal.href = photo.share_url || '#';

    lightbox.style.display = 'flex';
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    lightbox.style.display = 'none';
    lbImage.src = '';
    document.body.style.overflow = '';
    currentLbIndex = -1;
  }

  function navLightbox(dir) {
    if (currentLbIndex < 0) return;
    const next = currentLbIndex + dir;
    if (next < 0 || next >= PHOTOS.length) return;
    openLightbox(next);
  }

  // ── Lightbox Events ────────────────────────────
  $('lb-close').addEventListener('click', closeLightbox);
  $('lb-prev').addEventListener('click', (e) => { e.stopPropagation(); navLightbox(-1); });
  $('lb-next').addEventListener('click', (e) => { e.stopPropagation(); navLightbox(1); });

  document.querySelector('.lb-backdrop').addEventListener('click', closeLightbox);

  document.addEventListener('keydown', (e) => {
    if (lightbox.style.display === 'none') return;
    switch (e.key) {
      case 'Escape':  closeLightbox(); break;
      case 'ArrowLeft':  navLightbox(-1); break;
      case 'ArrowRight': navLightbox(1); break;
    }
  });

  // ── Touch swipe for mobile ─────────────────────
  let touchStartX = 0;
  lightbox.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
  }, { passive: true });

  lightbox.addEventListener('touchend', (e) => {
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 50) {
      navLightbox(dx > 0 ? -1 : 1);
    }
  }, { passive: true });

  // ── Boot ────────────────────────────────────────
  // Add shake animation dynamically
  const style = document.createElement('style');
  style.textContent = `
    @keyframes shake {
      0%, 100% { transform: translateX(0); }
      25% { transform: translateX(-8px); }
      75% { transform: translateX(8px); }
    }
  `;
  document.head.appendChild(style);

  init();
})();
