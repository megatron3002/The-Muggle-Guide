/* ═══════════════════════════════════════════════════
   The Muggle Guide — SPA Application
   Router · Auth · API · Page Renderers
   ═══════════════════════════════════════════════════ */

(() => {
    'use strict';

    // ── Constants ──
    const API = '/api';
    const $ = (sel, ctx = document) => ctx.querySelector(sel);
    const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

    // ── State ──
    const state = {
        token: null,
        user: null,       // { user_id, role, username }
        currentPage: null,
        books: [],
        totalBooks: 0,
        page: 1,
        pageSize: 20,
        searchQuery: '',
        genreFilter: '',
        genres: [],
        interactions: {},  // { bookId: { like: bool, bookmark: bool, rating: number } }
    };

    // ═══ API CLIENT ═══
    const api = {
        async request(method, path, body = null) {
            const opts = {
                method,
                headers: { 'Content-Type': 'application/json' },
            };
            if (state.token) opts.headers['Authorization'] = `Bearer ${state.token}`;
            if (body) opts.body = JSON.stringify(body);

            const res = await fetch(`${API}${path}`, opts);

            if (res.status === 401) {
                // Try to refresh
                const refreshed = await this.refreshToken();
                if (refreshed) {
                    opts.headers['Authorization'] = `Bearer ${state.token}`;
                    const retry = await fetch(`${API}${path}`, opts);
                    if (!retry.ok) throw new Error((await retry.json()).detail || 'Request failed');
                    if (retry.status === 204) return null;
                    return retry.json();
                }
                logout();
                throw new Error('Session expired');
            }

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Error ${res.status}`);
            }
            if (res.status === 204) return null;
            return res.json();
        },

        async refreshToken() {
            const refresh = localStorage.getItem('mg_refresh');
            if (!refresh) return false;
            try {
                const data = await fetch(`${API}/auth/refresh`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: refresh }),
                }).then(r => r.ok ? r.json() : null);
                if (data) {
                    state.token = data.access_token;
                    localStorage.setItem('mg_refresh', data.refresh_token);
                    return true;
                }
            } catch { /* ignore */ }
            return false;
        },

        get: (path) => api.request('GET', path),
        post: (path, body) => api.request('POST', path, body),
        put: (path, body) => api.request('PUT', path, body),
        del: (path) => api.request('DELETE', path),
    };

    // ═══ AUTH ═══
    async function login(email, password) {
        const data = await api.post('/auth/login', { email, password });
        state.token = data.access_token;
        localStorage.setItem('mg_refresh', data.refresh_token);
        decodeAndSetUser(data.access_token);
        showApp();
        navigate('discover');
        toast('Welcome back! 📚', 'success');
    }

    async function register(email, username, password) {
        const data = await api.post('/auth/register', { email, username, password });
        state.token = data.access_token;
        localStorage.setItem('mg_refresh', data.refresh_token);
        decodeAndSetUser(data.access_token);
        showApp();
        navigate('discover');
        toast('Account created! Happy reading 🎉', 'success');
    }

    function logout() {
        state.token = null;
        state.user = null;
        localStorage.removeItem('mg_refresh');
        hideApp();
        renderAuth();
    }

    function decodeAndSetUser(token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            state.user = {
                user_id: parseInt(payload.sub),
                role: payload.role || 'user',
                username: payload.username || `User ${payload.sub}`,
            };
            const el = $('#nav-username');
            if (el) el.textContent = state.user.username;
        } catch { /* ignore */ }
    }

    function showApp() {
        const nav = $('#navbar');
        if (nav) nav.classList.remove('hidden');
    }

    function hideApp() {
        const nav = $('#navbar');
        if (nav) nav.classList.add('hidden');
    }

    // ═══ ROUTER ═══
    function navigate(page, params = {}) {
        state.currentPage = page;
        updateNavActive(page);

        switch (page) {
            case 'discover': renderDiscover(); break;
            case 'book': renderBookDetail(params.id); break;
            case 'recommendations': renderRecommendations(); break;
            case 'library': renderLibrary(); break;
            default: renderDiscover();
        }
    }

    function updateNavActive(page) {
        $$('.nav-link').forEach(link => {
            link.classList.toggle('active', link.dataset.nav === page);
        });
    }

    // ═══ RENDER: AUTH ═══
    function renderAuth() {
        const app = $('#app');
        app.innerHTML = `
            <div class="auth-page">
                <div class="auth-bg-orb"></div>
                <div class="auth-bg-orb"></div>
                <div class="auth-bg-orb"></div>
                <div class="auth-card">
                    <div class="auth-header">
                        <h1>The Muggle Guide</h1>
                        <p id="auth-subtitle">Sign in to discover your next great read</p>
                    </div>
                    <div id="auth-error" class="auth-error"></div>
                    <form id="auth-form">
                        <div id="username-group" class="form-group hidden">
                            <label for="auth-username">Username</label>
                            <input type="text" id="auth-username" class="form-input"
                                   placeholder="Choose a username" autocomplete="username">
                        </div>
                        <div class="form-group">
                            <label for="auth-email">Email</label>
                            <input type="email" id="auth-email" class="form-input"
                                   placeholder="you@example.com" autocomplete="email" required>
                        </div>
                        <div class="form-group">
                            <label for="auth-password">Password</label>
                            <input type="password" id="auth-password" class="form-input"
                                   placeholder="••••••••" autocomplete="current-password" required>
                        </div>
                        <button type="submit" id="auth-submit-btn" class="btn btn-primary auth-submit">
                            Sign In
                        </button>
                    </form>
                    <p class="auth-toggle">
                        <span id="auth-toggle-text">Don't have an account?</span>
                        <a id="auth-toggle-link">Create one</a>
                    </p>
                </div>
            </div>
        `;

        let isLogin = true;
        const form = $('#auth-form');
        const toggleLink = $('#auth-toggle-link');
        const toggleText = $('#auth-toggle-text');
        const subtitle = $('#auth-subtitle');
        const usernameGroup = $('#username-group');
        const submitBtn = $('#auth-submit-btn');
        const errorEl = $('#auth-error');

        toggleLink.addEventListener('click', () => {
            isLogin = !isLogin;
            errorEl.classList.remove('visible');
            if (isLogin) {
                usernameGroup.classList.add('hidden');
                subtitle.textContent = 'Sign in to discover your next great read';
                submitBtn.textContent = 'Sign In';
                toggleText.textContent = "Don't have an account?";
                toggleLink.textContent = 'Create one';
            } else {
                usernameGroup.classList.remove('hidden');
                subtitle.textContent = 'Create an account to get started';
                submitBtn.textContent = 'Create Account';
                toggleText.textContent = 'Already have an account?';
                toggleLink.textContent = 'Sign in';
            }
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorEl.classList.remove('visible');
            submitBtn.disabled = true;
            submitBtn.textContent = isLogin ? 'Signing in…' : 'Creating account…';
            try {
                if (isLogin) {
                    await login($('#auth-email').value, $('#auth-password').value);
                } else {
                    await register(
                        $('#auth-email').value,
                        $('#auth-username').value,
                        $('#auth-password').value
                    );
                }
            } catch (err) {
                errorEl.textContent = err.message;
                errorEl.classList.add('visible');
                submitBtn.disabled = false;
                submitBtn.textContent = isLogin ? 'Sign In' : 'Create Account';
            }
        });
    }

    // ═══ RENDER: DISCOVER ═══
    async function renderDiscover() {
        const app = $('#app');
        app.innerHTML = `
            <div class="page fade-in">
                <div class="page-container">
                    <div class="discover-hero">
                        <h1>Discover Your Next <span>Great Read</span></h1>
                        <p>Explore our curated collection and get AI-powered recommendations tailored just for you.</p>
                        <div class="search-bar">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
                            </svg>
                            <input type="text" id="search-input" placeholder="Search by title or author…"
                                   value="${escapeHtml(state.searchQuery)}">
                        </div>
                        <div id="genre-chips" class="genre-chips"></div>
                    </div>
                    <div id="book-grid" class="book-grid stagger"></div>
                    <div id="pagination" class="pagination"></div>
                </div>
            </div>
        `;

        // Search handler
        let searchTimer;
        $('#search-input').addEventListener('input', (e) => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                state.searchQuery = e.target.value.trim();
                state.page = 1;
                loadBooks();
            }, 350);
        });

        // Load genres + books
        await loadBooks();
        renderGenreChips();
    }

    function renderGenreChips() {
        const genres = ['All', 'Classic', 'Fantasy', 'Science Fiction', 'Thriller', 'Romance',
            'Dystopian', 'Non-Fiction', 'Memoir', 'Fiction', 'Horror'];
        const container = $('#genre-chips');
        if (!container) return;

        container.innerHTML = genres.map(g => `
            <button class="genre-chip ${(g === 'All' && !state.genreFilter) || state.genreFilter === g ? 'active' : ''}"
                    data-genre="${g === 'All' ? '' : g}">
                ${g}
            </button>
        `).join('');

        container.addEventListener('click', (e) => {
            const chip = e.target.closest('.genre-chip');
            if (!chip) return;
            state.genreFilter = chip.dataset.genre;
            state.page = 1;
            $$('.genre-chip', container).forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            loadBooks();
        });
    }

    async function loadBooks() {
        const grid = $('#book-grid');
        if (!grid) return;

        // Show skeleton loading
        grid.innerHTML = Array(8).fill('').map(() => `
            <div class="book-card skeleton-card"></div>
        `).join('');

        try {
            let url = `/books?page=${state.page}&page_size=${state.pageSize}`;
            if (state.searchQuery) url += `&search=${encodeURIComponent(state.searchQuery)}`;
            if (state.genreFilter) url += `&genre=${encodeURIComponent(state.genreFilter)}`;

            const data = await api.get(url);
            state.books = data.books;
            state.totalBooks = data.total;

            if (data.books.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state" style="grid-column: 1 / -1">
                        <div class="empty-state-icon">🔍</div>
                        <h3>No books found</h3>
                        <p>Try adjusting your search or filters</p>
                    </div>
                `;
            } else {
                grid.innerHTML = '';
                grid.classList.add('stagger');
                data.books.forEach(book => {
                    grid.appendChild(createBookCard(book));
                });
            }

            renderPagination();
        } catch (err) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1">
                    <div class="empty-state-icon">⚠️</div>
                    <h3>Could not load books</h3>
                    <p>${escapeHtml(err.message)}</p>
                </div>
            `;
        }
    }

    function createBookCard(book) {
        const card = document.createElement('div');
        card.className = 'book-card';
        card.innerHTML = `
            <span class="book-card-genre">${escapeHtml(book.genre)}</span>
            <h3 class="book-card-title">${escapeHtml(book.title)}</h3>
            <p class="book-card-author">by ${escapeHtml(book.author)}</p>
            <p class="book-card-desc">${escapeHtml(book.description || '')}</p>
            <div class="book-card-footer">
                <span class="book-card-rating">
                    ★ ${book.avg_rating > 0 ? book.avg_rating.toFixed(1) : '—'}
                </span>
                <span class="book-card-year">${book.published_year || ''}</span>
            </div>
        `;
        card.addEventListener('click', () => navigate('book', { id: book.id }));
        return card;
    }

    function renderPagination() {
        const container = $('#pagination');
        if (!container) return;
        const totalPages = Math.ceil(state.totalBooks / state.pageSize);
        if (totalPages <= 1) { container.innerHTML = ''; return; }

        let html = `
            <button ${state.page <= 1 ? 'disabled' : ''} data-page="${state.page - 1}">← Previous</button>
            <span class="pagination-info">Page ${state.page} of ${totalPages}</span>
            <button ${state.page >= totalPages ? 'disabled' : ''} data-page="${state.page + 1}">Next →</button>
        `;
        container.innerHTML = html;
        container.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn || btn.disabled) return;
            state.page = parseInt(btn.dataset.page);
            loadBooks();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // ═══ RENDER: BOOK DETAIL ═══
    async function renderBookDetail(bookId) {
        const app = $('#app');
        app.innerHTML = `<div class="detail-page"><div class="detail-container"><div class="loading"><div class="spinner"></div></div></div></div>`;

        try {
            const book = await api.get(`/books/${bookId}`);

            // Load user interactions for this book
            let userLiked = false, userBookmarked = false, userRating = 0;
            try {
                const interactions = await api.get('/interactions/me?page_size=100');
                interactions.forEach(i => {
                    if (i.book_id === bookId) {
                        if (i.interaction_type === 'like') userLiked = true;
                        if (i.interaction_type === 'bookmark') userBookmarked = true;
                        if (i.interaction_type === 'rate' && i.rating) userRating = i.rating;
                    }
                });
            } catch { /* ignore */ }

            // Record view
            try { await api.post('/interactions', { book_id: bookId, interaction_type: 'view' }); } catch { /* ignore */ }

            app.innerHTML = `
                <div class="detail-page fade-in">
                    <div class="detail-container">
                        <a class="detail-back" id="back-btn">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>
                            Back
                        </a>
                        <div class="detail-card">
                            <span class="detail-genre">${escapeHtml(book.genre)}</span>
                            <h1 class="detail-title">${escapeHtml(book.title)}</h1>
                            <p class="detail-author">by ${escapeHtml(book.author)}</p>
                            <div class="detail-meta">
                                ${book.published_year ? `
                                <span class="detail-meta-item">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
                                    ${book.published_year}
                                </span>` : ''}
                                ${book.isbn ? `
                                <span class="detail-meta-item">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
                                    ISBN ${escapeHtml(book.isbn)}
                                </span>` : ''}
                                <span class="detail-meta-item">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
                                    ${book.total_interactions} interactions
                                </span>
                                ${book.avg_rating > 0 ? `
                                <span class="detail-meta-item" style="color: var(--accent-gold)">
                                    ★ ${book.avg_rating.toFixed(1)} avg rating
                                </span>` : ''}
                            </div>
                            <div class="detail-description">${escapeHtml(book.description || 'No description available.')}</div>

                            <div class="detail-actions">
                                <button class="action-btn ${userLiked ? 'active-like' : ''}" id="like-btn" data-book="${bookId}">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="${userLiked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
                                    ${userLiked ? 'Liked' : 'Like'}
                                </button>
                                <button class="action-btn ${userBookmarked ? 'active-bookmark' : ''}" id="bookmark-btn" data-book="${bookId}">
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="${userBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
                                    ${userBookmarked ? 'Bookmarked' : 'Bookmark'}
                                </button>
                            </div>

                            <div style="margin-bottom: 8px; font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">Rate this book</div>
                            <div class="star-rating" id="star-rating" data-book="${bookId}">
                                ${[1, 2, 3, 4, 5].map(i => `
                                    <span class="star ${i <= userRating ? 'filled' : ''}" data-value="${i}">★</span>
                                `).join('')}
                                <span class="star-rating-label" id="rating-label">
                                    ${userRating > 0 ? `You rated ${userRating}/5` : 'Click to rate'}
                                </span>
                            </div>
                        </div>

                        <div class="similar-section" id="similar-section">
                            <h2>📖 Similar Books</h2>
                            <div class="similar-scroll" id="similar-scroll">
                                <div class="loading"><div class="spinner"></div></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Back button
            $('#back-btn').addEventListener('click', () => {
                navigate('discover');
            });

            // Like button
            $('#like-btn').addEventListener('click', async function () {
                if (this.classList.contains('active-like')) return;
                try {
                    await api.post('/interactions', { book_id: bookId, interaction_type: 'like' });
                    this.classList.add('active-like');
                    this.querySelector('svg').setAttribute('fill', 'currentColor');
                    this.lastElementChild?.remove();
                    this.insertAdjacentHTML('beforeend', ' Liked');
                    toast('Added to your likes ❤️', 'success');
                } catch (err) { toast(err.message, 'error'); }
            });

            // Bookmark button
            $('#bookmark-btn').addEventListener('click', async function () {
                if (this.classList.contains('active-bookmark')) return;
                try {
                    await api.post('/interactions', { book_id: bookId, interaction_type: 'bookmark' });
                    this.classList.add('active-bookmark');
                    this.querySelector('svg').setAttribute('fill', 'currentColor');
                    this.lastElementChild?.remove();
                    this.insertAdjacentHTML('beforeend', ' Bookmarked');
                    toast('Bookmarked! 🔖', 'success');
                } catch (err) { toast(err.message, 'error'); }
            });

            // Star rating
            const starRating = $('#star-rating');
            const stars = $$('.star', starRating);
            const ratingLabel = $('#rating-label');
            let currentRating = userRating;

            stars.forEach(star => {
                star.addEventListener('mouseenter', () => {
                    const val = parseInt(star.dataset.value);
                    stars.forEach((s, i) => s.classList.toggle('hovered', i < val));
                });
                star.addEventListener('mouseleave', () => {
                    stars.forEach(s => s.classList.remove('hovered'));
                });
                star.addEventListener('click', async () => {
                    const val = parseInt(star.dataset.value);
                    if (val === currentRating) return;
                    try {
                        await api.post('/interactions', {
                            book_id: bookId,
                            interaction_type: 'rate',
                            rating: val
                        });
                        currentRating = val;
                        stars.forEach((s, i) => s.classList.toggle('filled', i < val));
                        ratingLabel.textContent = `You rated ${val}/5`;
                        toast(`Rated ${val} star${val > 1 ? 's' : ''} ⭐`, 'success');
                    } catch (err) { toast(err.message, 'error'); }
                });
            });

            // Load similar books
            loadSimilarBooks(bookId);

        } catch (err) {
            app.innerHTML = `
                <div class="detail-page">
                    <div class="detail-container">
                        <div class="empty-state">
                            <div class="empty-state-icon">📖</div>
                            <h3>Book not found</h3>
                            <p>${escapeHtml(err.message)}</p>
                            <button class="btn btn-secondary" style="margin-top: 20px" onclick="navigate('discover')">Back to Discover</button>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    async function loadSimilarBooks(bookId) {
        const scroll = $('#similar-scroll');
        if (!scroll) return;

        try {
            const data = await api.get(`/recommendations/similar/${bookId}?n=8`);
            if (!data || !data.recommendations || data.recommendations.length === 0) {
                scroll.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">No similar books found yet. Interact with more books to improve recommendations!</p>';
                return;
            }
            scroll.innerHTML = data.recommendations.map(rec => `
                <div class="similar-card" data-book-id="${rec.book_id}">
                    <div class="similar-card-title">${escapeHtml(rec.title || `Book #${rec.book_id}`)}</div>
                    <div class="similar-card-author">${rec.score ? `Score: ${rec.score.toFixed(2)}` : ''}</div>
                </div>
            `).join('');

            $$('.similar-card', scroll).forEach(card => {
                card.addEventListener('click', () => {
                    navigate('book', { id: parseInt(card.dataset.bookId) });
                });
            });
        } catch {
            scroll.innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem;">Recommendations will appear as you use the system more.</p>';
        }
    }

    // ═══ RENDER: RECOMMENDATIONS ═══
    async function renderRecommendations() {
        const app = $('#app');
        app.innerHTML = `
            <div class="page fade-in">
                <div class="page-container">
                    <div class="page-header">
                        <h1 class="page-title">✨ For You</h1>
                        <p class="page-subtitle">AI-powered recommendations based on your reading history</p>
                    </div>
                    <div id="rec-content" class="rec-grid">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                </div>
            </div>
        `;

        const content = $('#rec-content');

        try {
            const data = await api.get('/recommendations/top?n=15');
            if (!data || !data.recommendations || data.recommendations.length === 0) {
                content.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">🤖</div>
                        <h3>Not enough data yet</h3>
                        <p>Like, rate, and browse more books to unlock personalized recommendations</p>
                        <button class="btn btn-primary" style="margin-top: 20px" id="go-discover">Explore Books</button>
                    </div>
                `;
                $('#go-discover')?.addEventListener('click', () => navigate('discover'));
                return;
            }

            content.classList.add('stagger');
            content.innerHTML = data.recommendations.map((rec, i) => `
                <div class="rec-item" data-book-id="${rec.book_id}">
                    <span class="rec-rank">${i + 1}</span>
                    <div class="rec-info">
                        <div class="rec-title">${escapeHtml(rec.title || `Book #${rec.book_id}`)}</div>
                        <div class="rec-author">${rec.author ? `by ${escapeHtml(rec.author)}` : ''}</div>
                        ${rec.genre ? `<span class="rec-genre">${escapeHtml(rec.genre)}</span>` : ''}
                    </div>
                    ${rec.score ? `<div class="rec-score">${(rec.score * 100).toFixed(0)}% match</div>` : ''}
                </div>
            `).join('');

            $$('.rec-item', content).forEach(item => {
                item.addEventListener('click', () => {
                    navigate('book', { id: parseInt(item.dataset.bookId) });
                });
            });
        } catch (err) {
            content.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">⚡</div>
                    <h3>Recommendations unavailable</h3>
                    <p>${escapeHtml(err.message)}</p>
                </div>
            `;
        }
    }

    // ═══ RENDER: LIBRARY ═══
    async function renderLibrary() {
        const app = $('#app');
        app.innerHTML = `
            <div class="page fade-in">
                <div class="page-container">
                    <div class="page-header">
                        <h1 class="page-title">📚 My Library</h1>
                        <p class="page-subtitle">Your reading history and saved books</p>
                    </div>
                    <div class="library-tabs" id="library-tabs">
                        <button class="library-tab active" data-filter="all">All</button>
                        <button class="library-tab" data-filter="like">❤️ Liked</button>
                        <button class="library-tab" data-filter="bookmark">🔖 Bookmarked</button>
                        <button class="library-tab" data-filter="rate">⭐ Rated</button>
                        <button class="library-tab" data-filter="view">👁️ Viewed</button>
                    </div>
                    <div id="library-content">
                        <div class="loading"><div class="spinner"></div></div>
                    </div>
                </div>
            </div>
        `;

        let activeFilter = 'all';
        let allInteractions = [];

        // Tab handler
        $('#library-tabs').addEventListener('click', (e) => {
            const tab = e.target.closest('.library-tab');
            if (!tab) return;
            activeFilter = tab.dataset.filter;
            $$('.library-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            renderLibraryList(allInteractions, activeFilter);
        });

        const content = $('#library-content');

        try {
            allInteractions = await api.get('/interactions/me?page_size=100');
            renderLibraryList(allInteractions, activeFilter);
        } catch (err) {
            content.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📕</div>
                    <h3>Could not load your library</h3>
                    <p>${escapeHtml(err.message)}</p>
                </div>
            `;
        }
    }

    function renderLibraryList(interactions, filter) {
        const content = $('#library-content');
        if (!content) return;

        const filtered = filter === 'all'
            ? interactions
            : interactions.filter(i => i.interaction_type === filter);

        if (filtered.length === 0) {
            content.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">${filter === 'like' ? '❤️' : filter === 'bookmark' ? '🔖' : filter === 'rate' ? '⭐' : '📚'}</div>
                    <h3>Nothing here yet</h3>
                    <p>Start exploring books to build your library</p>
                    <button class="btn btn-primary" style="margin-top: 20px" id="go-discover-lib">Discover Books</button>
                </div>
            `;
            $('#go-discover-lib')?.addEventListener('click', () => navigate('discover'));
            return;
        }

        const typeIcons = { view: '👁️', like: '❤️', rate: '⭐', bookmark: '🔖', purchase: '🛒' };
        const typeLabels = { view: 'Viewed', like: 'Liked', rate: 'Rated', bookmark: 'Bookmarked', purchase: 'Purchased' };

        content.innerHTML = filtered.map(i => `
            <div class="library-item" data-book-id="${i.book_id}">
                <span class="library-item-type">${typeIcons[i.interaction_type] || '📖'}</span>
                <div class="library-item-info">
                    <div class="library-item-title">Book #${i.book_id}</div>
                    <div class="library-item-detail">
                        ${typeLabels[i.interaction_type] || i.interaction_type}
                        ${i.rating ? ` — ${i.rating}/5 ⭐` : ''}
                    </div>
                </div>
                <span class="library-item-date">${formatDate(i.created_at)}</span>
            </div>
        `).join('');

        // Enrich with book titles
        enrichLibraryItems(filtered);

        $$('.library-item', content).forEach(item => {
            item.addEventListener('click', () => {
                navigate('book', { id: parseInt(item.dataset.bookId) });
            });
        });
    }

    async function enrichLibraryItems(interactions) {
        const bookIds = [...new Set(interactions.map(i => i.book_id))];
        for (const id of bookIds) {
            try {
                const book = await api.get(`/books/${id}`);
                $$(`[data-book-id="${id}"] .library-item-title`).forEach(el => {
                    el.textContent = book.title;
                });
            } catch { /* ignore */ }
        }
    }

    // ═══ UTILITIES ═══
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        try {
            const d = new Date(dateStr);
            const now = new Date();
            const diff = now - d;
            if (diff < 60000) return 'Just now';
            if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
            if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
            if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
            return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } catch { return ''; }
    }

    function toast(message, type = 'success') {
        const container = $('#toast-container');
        const el = document.createElement('div');
        el.className = `toast toast-${type}`;
        el.innerHTML = `<span>${type === 'success' ? '✓' : '✕'}</span> ${escapeHtml(message)}`;
        container.appendChild(el);
        setTimeout(() => {
            el.classList.add('toast-out');
            setTimeout(() => el.remove(), 300);
        }, 3000);
    }

    // ═══ INIT ═══
    function init() {
        // Nav link handlers
        $$('[data-nav]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                navigate(link.dataset.nav);
            });
        });

        // Logout button
        $('#logout-btn')?.addEventListener('click', logout);

        // Try to restore session
        const refresh = localStorage.getItem('mg_refresh');
        if (refresh) {
            api.refreshToken().then(ok => {
                if (ok) {
                    decodeAndSetUser(state.token);
                    showApp();
                    navigate('discover');
                } else {
                    renderAuth();
                }
            });
        } else {
            renderAuth();
        }
    }

    // Make navigate globally accessible for inline onclick
    window.navigate = navigate;

    // Boot
    init();
})();
