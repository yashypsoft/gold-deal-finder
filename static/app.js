/* Gold Deal Finder 2026 Premium Fintech Application Engine */
(function () {
    const DEFAULT_FILTERS = Object.freeze({
        source: '',
        purity: '',
        search: '',
        min_discount: -100,
        max_discount: 100,
        min_weight: 0,
        max_weight: 100,
        onlyFavorites: false,
    });

    function cloneFilters() {
        return JSON.parse(JSON.stringify(DEFAULT_FILTERS));
    }

    function safeArray(value) {
        return Array.isArray(value) ? value : [];
    }

    function numeric(value, fallback = 0) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    window.app = new Vue({
        el: '#app',

        data: {
            activeTab: 'products',
            sidebarCollapsed: localStorage.getItem('goldSidebarCollapsed') === 'true',
            commandPaletteOpen: false,
            paletteQuery: '',
            showFilterDrawer: false,
            showSourcesInfo: false,

            loading: true,
            loadingProducts: false,
            refreshing: false,
            scanning: false,
            bootError: '',

            darkMode: localStorage.getItem('goldDarkMode') === 'true',
            windowWidth: window.innerWidth,
            mobileMenuOpen: false,

            showScanModal: false,
            showExportModal: false,
            showFavoritesModal: false,
            selectedProduct: null,

            selectedScanId: null,
            selectedScanTimestamp: null,
            selectedScanIsLatest: true,
            latestScanId: null,
            latestScanTimestamp: null,

            allProducts: [],
            scans: [],
            summaryStats: {
                live: {},
                historical: {},
            },
            spotPrice: null,
            dealerRates: null,
            timeline: {
                timeline: {},
                total_scans: 0,
                total_products: 0,
            },

            filters: cloneFilters(),
            currentPage: 1,
            itemsPerPage: 24,
            pageSizeOptions: [24, 48, 96],
            sortBy: 'discount_percent',
            sortOrder: 'desc',

            favorites: JSON.parse(localStorage.getItem('goldFavorites') || '[]'),
            exportFormat: 'csv',

            notifications: [],
            notificationId: 0,

            distributionChart: null,
            scanTrendChart: null,

            shortcuts: [
                { key: 'Ctrl/Cmd + K', action: 'Command Palette' },
                { key: 'Ctrl/Cmd + F', action: 'Search products' },
                { key: 'Ctrl/Cmd + R', action: 'Refresh data' },
                { key: 'Ctrl/Cmd + D', action: 'Toggle theme' },
                { key: 'Esc', action: 'Close overlays' },
            ],
        },

        computed: {
            filteredProducts() {
                let products = [...this.allProducts];

                if (this.filters.source) {
                    products = products.filter((product) => product.source === this.filters.source);
                }
                if (this.filters.purity) {
                    products = products.filter((product) => product.purity === this.filters.purity);
                }
                if (this.filters.search) {
                    const term = this.filters.search.toLowerCase();
                    products = products.filter((product) => {
                        return [product.title, product.brand, product.source, product.purity]
                            .filter(Boolean)
                            .some((value) => String(value).toLowerCase().includes(term));
                    });
                }

                products = products.filter((product) => {
                    const discount = numeric(product.discount_percent);
                    const weight = numeric(product.weight_grams);
                    return (
                        discount >= this.filters.min_discount &&
                        discount <= this.filters.max_discount &&
                        weight >= this.filters.min_weight &&
                        weight <= this.filters.max_weight
                    );
                });

                if (this.filters.onlyFavorites) {
                    products = products.filter((product) => this.favorites.includes(product.url));
                }

                return products;
            },

            sortedProducts() {
                const products = [...this.filteredProducts];
                const direction = this.sortOrder === 'desc' ? -1 : 1;
                products.sort((left, right) => {
                    let a = left[this.sortBy];
                    let b = right[this.sortBy];

                    if (this.sortBy === 'timestamp') {
                        a = new Date(a || 0).getTime();
                        b = new Date(b || 0).getTime();
                    } else {
                        a = typeof a === 'string' ? a.toLowerCase() : numeric(a);
                        b = typeof b === 'string' ? b.toLowerCase() : numeric(b);
                    }

                    if (a < b) return -1 * direction;
                    if (a > b) return 1 * direction;
                    return 0;
                });
                return products;
            },

            paginatedProducts() {
                const start = (this.currentPage - 1) * this.itemsPerPage;
                return this.sortedProducts.slice(start, start + this.itemsPerPage);
            },

            totalPages() {
                return Math.max(1, Math.ceil(this.sortedProducts.length / this.itemsPerPage));
            },

            pageNumbers() {
                const total = this.totalPages;
                const current = this.currentPage;
                const start = Math.max(1, current - 2);
                const end = Math.min(total, start + 4);
                const pages = [];
                for (let page = start; page <= end; page += 1) {
                    pages.push(page);
                }
                return pages;
            },

            activeFilterCount() {
                let count = 0;
                if (this.filters.source) count += 1;
                if (this.filters.purity) count += 1;
                if (this.filters.search) count += 1;
                if (this.filters.min_discount !== DEFAULT_FILTERS.min_discount) count += 1;
                if (this.filters.max_discount !== DEFAULT_FILTERS.max_discount) count += 1;
                if (this.filters.min_weight !== DEFAULT_FILTERS.min_weight) count += 1;
                if (this.filters.max_weight !== DEFAULT_FILTERS.max_weight) count += 1;
                if (this.filters.onlyFavorites) count += 1;
                return count;
            },

            uniqueSources() {
                const ALL_KNOWN = ['AJIO', 'Myntra', 'Candere', 'Bhima Gold', 'Tanishq', 'MMTC-PAMP', 'Jos Alukkas', 'Joyalukkas', 'Malabar Gold'];
                const fromProducts = this.allProducts.map((product) => product.source).filter(Boolean);
                return [...new Set([...ALL_KNOWN, ...fromProducts])].sort();
            },

            uniquePurities() {
                return [...new Set(this.allProducts.map((product) => product.purity).filter(Boolean))].sort();
            },

            isDesktop() {
                return this.windowWidth >= 1024;
            },

            scanLabel() {
                if (!this.selectedScanId) return 'No scan loaded';
                return this.selectedScanIsLatest ? 'Latest market capture' : 'Archived scan selected';
            },

            scanTimeFormatted() {
                if (!this.selectedScanTimestamp) return 'No timestamp';
                return this.formatDateTime(this.selectedScanTimestamp);
            },

            liveSpotPrice() {
                return numeric(this.spotPrice?.gold?.per_gram?.['999_landed']);
            },

            bestCurrentDeal() {
                if (!this.allProducts.length) return null;
                return [...this.allProducts].sort((a, b) => numeric(b.discount_percent) - numeric(a.discount_percent))[0];
            },

            favoriteProducts() {
                return this.allProducts.filter((product) => this.favorites.includes(product.url));
            },

            currentSourceDistribution() {
                const distribution = {};
                this.allProducts.forEach((product) => {
                    const source = product.source || 'Unknown';
                    distribution[source] = (distribution[source] || 0) + 1;
                });
                return distribution;
            },

            scanTrendSeries() {
                return [...this.scans].slice(0, 10).reverse();
            },
        },

        watch: {
            filters: {
                handler() {
                    this.currentPage = 1;
                },
                deep: true,
            },
            sortBy() {
                this.currentPage = 1;
            },
            sortOrder() {
                this.currentPage = 1;
            },
            itemsPerPage() {
                this.currentPage = 1;
            },
            favorites: {
                handler(value) {
                    localStorage.setItem('goldFavorites', JSON.stringify(value));
                },
                deep: true,
            },
            darkMode(value) {
                localStorage.setItem('goldDarkMode', String(value));
                this.applyTheme();
                this.$nextTick(() => this.renderCharts());
            },
            activeTab() {
                this.$nextTick(() => this.renderCharts());
            },
            allProducts() {
                this.currentPage = 1;
                this.$nextTick(() => this.renderCharts());
            },
            scans() {
                this.$nextTick(() => this.renderCharts());
            },
            sidebarCollapsed(value) {
                localStorage.setItem('goldSidebarCollapsed', String(value));
            },
            commandPaletteOpen(value) {
                if (value) {
                    this.$nextTick(() => {
                        if (this.$refs.paletteInput) {
                            this.$refs.paletteInput.focus();
                        }
                    });
                }
            },
        },

        mounted() {
            this.applyTheme();
            window.addEventListener('resize', this.handleResize);
            this.initKeyboardShortcuts();
            this.boot();
            this.setupAutoRefresh();
        },

        beforeDestroy() {
            window.removeEventListener('keydown', this.handleKeyDown);
            window.removeEventListener('resize', this.handleResize);
            this.destroyCharts();
        },

        methods: {
            toggleSidebar() {
                this.sidebarCollapsed = !this.sidebarCollapsed;
            },

            switchTab(tab) {
                this.activeTab = tab;
                this.mobileMenuOpen = false;
                this.showFilterDrawer = false;
                this.commandPaletteOpen = false;
                if (tab === 'insights') {
                    this.$nextTick(() => this.renderCharts());
                }
            },

            getSavingsRupees(product) {
                return numeric(product.expected_price) - numeric(product.selling_price);
            },

            getSavingsRupeesFormatted(product) {
                const diff = this.getSavingsRupees(product);
                if (diff >= 0) {
                    return `₹${Math.round(diff).toLocaleString('en-IN')} cheaper`;
                }
                return `₹${Math.abs(Math.round(diff)).toLocaleString('en-IN')} premium`;
            },

            isTopTierDeal(product) {
                const diff = this.getSavingsRupees(product);
                const discount = numeric(product.discount_percent);
                return diff >= 1000 || discount >= 5;
            },

            runScanCommand() {
                this.commandPaletteOpen = false;
                this.startNewScan();
            },

            async boot() {
                this.loading = true;
                this.bootError = '';
                try {
                    await this.refreshDashboardData({ preserveSelection: false });
                } catch (error) {
                    this.bootError = this.getErrorMessage(error, 'Unable to load the dashboard.');
                } finally {
                    this.loading = false;
                }
            },

            async refreshDashboardData({ preserveSelection = true, clearCache = false } = {}) {
                const selectedScanId = preserveSelection ? this.selectedScanId : null;
                const selectedScanIsLatest = preserveSelection ? this.selectedScanIsLatest : true;

                if (clearCache) {
                    await axios.post('/api/v1/cache/clear');
                }

                await Promise.all([
                    this.fetchScans(),
                    this.fetchSummaryStats(),
                    this.fetchSpotPrice(),
                    this.fetchDealerRates(),
                    this.fetchTimeline(),
                ]);

                if (selectedScanId && !selectedScanIsLatest && this.scans.some((scan) => scan.scan_id === selectedScanId)) {
                    await this.loadScanDetails(selectedScanId, { keepTab: true, silent: true });
                } else {
                    await this.loadLatestScan({ silent: true });
                }
            },

            async fetchScans() {
                const response = await axios.get('/api/v1/historical/scans?limit=30');
                this.scans = safeArray(response.data);
                if (this.scans.length) {
                    this.latestScanId = this.scans[0].scan_id;
                    this.latestScanTimestamp = this.scans[0].timestamp;
                } else {
                    this.latestScanId = null;
                    this.latestScanTimestamp = null;
                }
            },

            async fetchSummaryStats() {
                const response = await axios.get('/api/v1/stats/summary');
                this.summaryStats = response.data || { live: {}, historical: {} };
            },

            async fetchSpotPrice() {
                const response = await axios.get('/api/v1/spot-price');
                this.spotPrice = response.data || null;
            },

            async fetchDealerRates() {
                try {
                    const response = await axios.get('/api/v1/dealer-rates');
                    this.dealerRates = response.data || null;
                } catch (err) {
                    console.error('Failed to fetch dealer rates', err);
                }
            },

            async fetchTimeline() {
                const response = await axios.get('/api/v1/historical/timeline?days=30');
                this.timeline = response.data || { timeline: {}, total_scans: 0, total_products: 0 };
            },

            async loadLatestScan({ silent = false } = {}) {
                if (!this.scans.length) {
                    this.allProducts = [];
                    this.selectedScanId = null;
                    this.selectedScanTimestamp = null;
                    this.selectedScanIsLatest = true;
                    this.latestScanId = null;
                    this.latestScanTimestamp = null;
                    return;
                }
                await this.loadScanDetails(this.scans[0].scan_id, { isLatest: true, silent });
            },

            async loadScanDetails(scanId, { isLatest = false, keepTab = false, silent = false } = {}) {
                this.loadingProducts = true;
                if (!silent) {
                    this.bootError = '';
                }
                try {
                    const response = await axios.get(`/api/v1/historical/scan/${scanId}`);
                    const scanData = response.data || {};
                    this.allProducts = safeArray(scanData.products);
                    this.selectedScanId = scanData.scan_id || scanId;
                    this.selectedScanTimestamp = scanData.timestamp || null;
                    this.selectedScanIsLatest = Boolean(isLatest || this.latestScanId === this.selectedScanId);
                    if (!keepTab) {
                        this.activeTab = 'products';
                    }
                    this.mobileMenuOpen = false;
                    this.showFilterDrawer = false;
                    if (!silent) {
                        this.showNotification('info', this.selectedScanIsLatest ? 'Loaded latest scan dataset.' : `Loaded archived scan ${scanId}.`);
                    }
                } catch (error) {
                    const message = this.getErrorMessage(error, 'Unable to load scan details.');
                    this.bootError = message;
                    this.showNotification('error', message);
                } finally {
                    this.loadingProducts = false;
                }
            },

            async returnToLatest() {
                await this.loadLatestScan();
            },

            async refreshData() {
                this.refreshing = true;
                this.bootError = '';
                try {
                    await this.refreshDashboardData({ preserveSelection: true, clearCache: true });
                    this.showNotification('success', 'Dashboard refreshed successfully.');
                } catch (error) {
                    this.showNotification('error', this.getErrorMessage(error, 'Refresh failed.'));
                } finally {
                    this.refreshing = false;
                }
            },

            async startNewScan() {
                this.scanning = true;
                try {
                    const response = await axios.get('/api/v1/scan');
                    this.showScanModal = false;
                    this.showNotification('success', response.data?.message || 'Scan completed successfully.');
                    await this.refreshDashboardData({ preserveSelection: false, clearCache: true });
                    await this.loadLatestScan({ silent: true });
                } catch (error) {
                    this.showNotification('error', this.getErrorMessage(error, 'Scan failed.'));
                } finally {
                    this.scanning = false;
                }
            },

            async checkForNewScan() {
                try {
                    const response = await axios.get('/api/v1/historical/scans?limit=1');
                    const latest = safeArray(response.data)[0];
                    if (latest && latest.scan_id !== this.latestScanId) {
                        this.showNotification('info', 'New scan detected. Updating dashboard.');
                        await this.refreshDashboardData({ preserveSelection: true, clearCache: false });
                    }
                } catch (error) {
                    console.error('Scan polling failed', error);
                }
            },

            handleResize() {
                this.windowWidth = window.innerWidth;
                if (this.isDesktop) {
                    this.showFilterDrawer = false;
                    this.mobileMenuOpen = false;
                }
            },

            exportData() {
                const rows = this.sortedProducts;
                const fileBase = this.selectedScanId ? `gold-deals-${this.selectedScanId}` : 'gold-deals';
                if (this.exportFormat === 'json') {
                    this.downloadBlob(JSON.stringify(rows, null, 2), `${fileBase}.json`, 'application/json');
                } else {
                    const headers = ['Source', 'Brand', 'Title', 'Purity', 'Weight (g)', 'Price', 'Expected', 'Savings (INR)', 'Discount %', 'Price/g', 'URL'];
                    const csvRows = rows.map((product) => [
                        product.source,
                        product.brand,
                        String(product.title || '').replace(/,/g, ';'),
                        product.purity,
                        numeric(product.weight_grams),
                        numeric(product.selling_price),
                        numeric(product.expected_price),
                        this.getSavingsRupees(product),
                        numeric(product.discount_percent),
                        numeric(product.price_per_gram),
                        product.url,
                    ]);
                    const csv = [headers, ...csvRows].map((row) => row.join(',')).join('\n');
                    this.downloadBlob(csv, `${fileBase}.csv`, 'text/csv;charset=utf-8');
                }
                this.showExportModal = false;
                this.showNotification('success', 'Export complete.');
            },

            downloadBlob(content, filename, mimeType) {
                const blob = new Blob([content], { type: mimeType });
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = filename;
                link.click();
                URL.revokeObjectURL(url);
            },

            resetFilters() {
                this.filters = cloneFilters();
                this.showNotification('info', 'Filters reset to default.');
            },

            toggleFavorite(product) {
                const index = this.favorites.indexOf(product.url);
                if (index === -1) {
                    this.favorites.push(product.url);
                    this.showNotification('success', 'Saved to shortlist.');
                } else {
                    this.favorites.splice(index, 1);
                    this.showNotification('info', 'Removed from shortlist.');
                }
            },

            isFavorite(product) {
                return this.favorites.includes(product.url);
            },

            closeAllPanels() {
                this.mobileMenuOpen = false;
                this.showFilterDrawer = false;
                this.commandPaletteOpen = false;
                this.showScanModal = false;
                this.showExportModal = false;
                this.showFavoritesModal = false;
                this.showSourcesInfo = false;
                this.selectedProduct = null;
            },

            copyToClipboard(text, successMessage = 'Copied.') {
                if (!text) return;
                navigator.clipboard.writeText(text);
                this.showNotification('success', successMessage);
            },

            handleImageError(event) {
                event.target.src = 'https://placehold.co/400x400/faf8f5/c5a059?text=Gold+Deal';
            },

            focusSearch() {
                const element = document.getElementById('search-input');
                if (element) {
                    element.focus();
                    element.select();
                }
            },

            goToPage(page) {
                if (page < 1 || page > this.totalPages) return;
                this.currentPage = page;
            },

            nextPage() {
                this.goToPage(this.currentPage + 1);
            },

            prevPage() {
                this.goToPage(this.currentPage - 1);
            },

            formatCurrency(value) {
                return `₹${numeric(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
            },

            formatNumber(value) {
                return numeric(value).toLocaleString('en-IN', { maximumFractionDigits: 2 });
            },

            formatWeight(value) {
                const amount = numeric(value);
                if (amount >= 1000) {
                    return `${(amount / 1000).toFixed(2)} kg`;
                }
                return `${amount} g`;
            },

            formatPercent(value) {
                const amount = numeric(value);
                return `${amount > 0 ? '+' : ''}${amount.toFixed(1)}%`;
            },

            formatDateTime(value) {
                if (!value) return 'Unknown time';
                return new Date(value).toLocaleString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                });
            },

            formatDate(value) {
                if (!value) return 'Unknown';
                return new Date(value).toLocaleDateString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                });
            },

            getErrorMessage(error, fallback) {
                return (
                    error?.response?.data?.detail?.message ||
                    error?.response?.data?.detail ||
                    error?.message ||
                    fallback
                );
            },

            showNotification(type, message, duration = 3200) {
                const id = this.notificationId + 1;
                this.notificationId = id;
                this.notifications.push({ id, type, message });
                window.setTimeout(() => {
                    this.notifications = this.notifications.filter((notification) => notification.id !== id);
                }, duration);
            },

            notificationClass(type) {
                if (type === 'error') return 'toast toast-error';
                if (type === 'success') return 'toast toast-success';
                return 'toast toast-info';
            },

            setupAutoRefresh() {
                window.setInterval(() => this.fetchSpotPrice().catch(() => {}), 5 * 60 * 1000);
                window.setInterval(() => this.checkForNewScan(), 5 * 60 * 1000);
            },

            applyTheme() {
                document.documentElement.classList.toggle('dark', this.darkMode);
            },

            toggleTheme() {
                this.darkMode = !this.darkMode;
            },

            initKeyboardShortcuts() {
                window.addEventListener('keydown', this.handleKeyDown);
            },

            handleKeyDown(event) {
                if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
                    event.preventDefault();
                    this.commandPaletteOpen = !this.commandPaletteOpen;
                }
                if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'f') {
                    event.preventDefault();
                    this.focusSearch();
                }
                if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'r') {
                    event.preventDefault();
                    this.refreshData();
                }
                if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'd') {
                    event.preventDefault();
                    this.toggleTheme();
                }
                if (event.key === 'Escape') {
                    this.closeAllPanels();
                }
            },

            destroyCharts() {
                if (this.distributionChart) {
                    this.distributionChart.destroy();
                    this.distributionChart = null;
                }
                if (this.scanTrendChart) {
                    this.scanTrendChart.destroy();
                    this.scanTrendChart = null;
                }
            },

            renderCharts() {
                if (typeof Chart === 'undefined') return;
                this.renderDistributionChart();
                this.renderScanTrendChart();
            },

            renderDistributionChart() {
                const canvas = document.getElementById('distributionChart');
                if (!canvas) return;
                if (this.distributionChart) {
                    this.distributionChart.destroy();
                }
                const labels = Object.keys(this.currentSourceDistribution);
                const data = Object.values(this.currentSourceDistribution);
                if (!labels.length) return;
                this.distributionChart = new Chart(canvas.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels,
                        datasets: [{
                            data,
                            backgroundColor: ['#c5a059', '#8f6a20', '#3d6a80', '#7a3f29', '#5b7f58'],
                            borderWidth: 0,
                        }],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: {
                                    color: this.darkMode ? '#f0f2f5' : '#1a1a1a',
                                    font: { family: 'Plus Jakarta Sans', size: 12 }
                                },
                            },
                        },
                    },
                });
            },

            renderScanTrendChart() {
                const canvas = document.getElementById('scanTrendChart');
                if (!canvas) return;
                if (this.scanTrendChart) {
                    this.scanTrendChart.destroy();
                }
                if (!this.scanTrendSeries.length) return;
                this.scanTrendChart = new Chart(canvas.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: this.scanTrendSeries.map((scan) => this.formatDate(scan.timestamp)),
                        datasets: [
                            {
                                label: 'Total Products',
                                data: this.scanTrendSeries.map((scan) => numeric(scan.total_products)),
                                borderColor: '#c5a059',
                                backgroundColor: 'rgba(197, 160, 89, 0.15)',
                                fill: true,
                                tension: 0.35,
                            },
                            {
                                label: 'Good Deals',
                                data: this.scanTrendSeries.map((scan) => numeric(scan.good_deals)),
                                borderColor: '#15803d',
                                backgroundColor: 'rgba(21, 128, 61, 0.1)',
                                fill: true,
                                tension: 0.35,
                            },
                        ],
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                labels: {
                                    color: this.darkMode ? '#f0f2f5' : '#1a1a1a',
                                    font: { family: 'Plus Jakarta Sans', size: 12 }
                                },
                            },
                        },
                        scales: {
                            x: {
                                ticks: { color: this.darkMode ? '#9ca3af' : '#5e5953' },
                                grid: { color: this.darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)' },
                            },
                            y: {
                                ticks: { color: this.darkMode ? '#9ca3af' : '#5e5953' },
                                grid: { color: this.darkMode ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)' },
                            },
                        },
                    },
                });
            },
        },
    });
})();
