// Shared navigation functionality
(function() {
    let allPlaylists = [];
    let allAssetGroups = [];

    // Create and inject navigation HTML
    function createNavigation() {
        const nav = document.createElement('nav');
        nav.className = 'top-nav';
        nav.innerHTML = `
            <a href="/wall.html" class="nav-link">Wall</a>
            <span class="nav-separator">|</span>
            <a href="/playlists.html" class="nav-link">Playlists</a>
            <span class="nav-separator">|</span>
            <a href="/queue.html" class="nav-link">Queue</a>
            <span class="nav-separator">|</span>
            <a href="/settings.html" class="nav-link">Settings</a>
            <span class="nav-separator">|</span>
            <div class="nav-search">
                <input type="text" id="nav-search-input" placeholder="Search playlists & asset groups..." autocomplete="off">
                <div class="search-results" id="search-results"></div>
            </div>
            <span class="nav-separator">|</span>
            <a href="#" class="nav-link" id="new-asset-group-btn">+ New</a>
        `;
        document.body.insertBefore(nav, document.body.firstChild);
        document.body.classList.add('has-nav');

        // Add click handler for new button
        const newBtn = document.getElementById('new-asset-group-btn');
        if (newBtn) {
            newBtn.addEventListener('click', function(e) {
                e.preventDefault();
                createNewAssetGroup();
            });
        }
    }

    // Load search data
    async function loadSearchData() {
        try {
            const [playlistsResp, assetGroupsResp] = await Promise.all([
                fetch('/playlists'),
                fetch('/asset-groups')
            ]);
            const playlistsData = await playlistsResp.json();
            const assetGroupsData = await assetGroupsResp.json();

            allPlaylists = playlistsData.playlists || [];
            allAssetGroups = assetGroupsData.asset_groups ? Object.keys(assetGroupsData.asset_groups).map(id => ({name: id})) : [];
        } catch (error) {
            console.error('Error loading search data:', error);
        }
    }

    // Perform search
    function performSearch(query) {
        if (!query) return [];

        query = query.toLowerCase();
        const results = [];

        // Search playlists
        allPlaylists.forEach(name => {
            if (name.toLowerCase().includes(query)) {
                results.push({ type: 'playlist', name: name });
            }
        });

        // Search asset groups
        allAssetGroups.forEach(item => {
            if (item.name.toLowerCase().includes(query)) {
                results.push({ type: 'asset_group', name: item.name });
            }
        });

        return results.slice(0, 10); // Limit to 10 results
    }

    // Render search results
    function renderSearchResults(results) {
        const container = document.getElementById('search-results');
        if (!container) return;

        if (results.length === 0) {
            container.classList.remove('active');
            return;
        }

        container.innerHTML = results.map((result, index) => `
            <div class="search-result-item" data-type="${result.type}" data-name="${result.name}" data-index="${index}">
                <div class="search-result-type">${result.type}</div>
                <div>${result.name}</div>
            </div>
        `).join('');

        container.classList.add('active');

        // Add click handlers to each result
        container.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', function() {
                const type = this.getAttribute('data-type');
                const name = this.getAttribute('data-name');
                navigateToResult(type, name);
            });
        });
    }

    // Navigate to search result
    function navigateToResult(type, name) {
        if (type === 'playlist') {
            window.location.href = '/playlists.html?name=' + encodeURIComponent(name);
        } else if (type === 'asset_group') {
            window.location.href = '/asset_group.html?id=' + encodeURIComponent(name);
        }
    }

    // Create new asset group
    async function createNewAssetGroup() {
        const name = prompt('Enter asset group name (e.g., "animals/elephant" or "test1"):');
        if (!name) return;

        try {
            // Call server to create the asset group with auto-generated prompt
            const response = await fetch('/asset-group/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ name: name })
            });

            if (response.ok) {
                // Navigate to asset group editor
                window.location.href = '/asset_group.html?id=' + encodeURIComponent(name);
            } else {
                const errorText = await response.text();
                alert('Error creating asset group: ' + errorText);
            }
        } catch (error) {
            alert('Error creating asset group: ' + error.message);
        }
    }

    // Setup search listeners
    function setupSearchListeners() {
        const searchInput = document.getElementById('nav-search-input');
        if (!searchInput) return;

        let currentResults = [];

        searchInput.addEventListener('input', function() {
            const query = this.value.trim();
            currentResults = performSearch(query);
            renderSearchResults(currentResults);
        });

        searchInput.addEventListener('focus', function() {
            if (this.value.trim()) {
                currentResults = performSearch(this.value.trim());
                renderSearchResults(currentResults);
            }
        });

        // Handle Enter key to select first result
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && currentResults.length > 0) {
                e.preventDefault();
                const firstResult = currentResults[0];
                navigateToResult(firstResult.type, firstResult.name);
            } else if (e.key === 'Escape') {
                const searchResults = document.getElementById('search-results');
                if (searchResults) {
                    searchResults.classList.remove('active');
                }
                searchInput.blur();
            }
        });

        // Close search results when clicking outside
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.nav-search')) {
                const searchResults = document.getElementById('search-results');
                if (searchResults) {
                    searchResults.classList.remove('active');
                }
            }
        });
    }

    // Initialize navigation
    function init() {
        createNavigation();
        loadSearchData();
        setupSearchListeners();
    }

    // Export public API
    window.tripticNav = {
        init: init,
        navigateToResult: navigateToResult,
        createNewAssetGroup: createNewAssetGroup
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
