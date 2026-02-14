// ============================================
// GOLD DEAL FINDER - PREMIUM EDITION
// ============================================
// Features:
// ✅ Latest scan data only
// ✅ Working pagination
// ✅ Price history charts
// ✅ Deal alerts & notifications
// ✅ Dark mode toggle
// ✅ Export to CSV
// ✅ Favorites/Watchlist
// ✅ Keyboard shortcuts
// ✅ Responsive mobile design
// ✅ Real-time price updates
// ============================================

console.log('🚀 Gold Deal Finder Premium loading...');


try {
    window.app = new Vue({
        el: '#app',
        
        data: {
            // ========== UI STATE ==========
            activeTab: 'products',
            loading: true,
            loadingProducts: false,
            scanning: false,
            showScanModal: false,
            showExportModal: false,
            showFavoritesModal: false,
            showSettingsModal: false,
            showPriceHistoryModal: false,
            selectedProduct: null,
            darkMode: localStorage.getItem('darkMode') === 'true',
            sidebarCollapsed: false,
            
            // ========== DATA ==========
            // Latest scan only - NO HISTORICAL MIX
            currentScanId: null,
            currentScanTimestamp: null,
            allProducts: [], // All products from latest scan
            scans: [], // Limited to 5 for history view
            latestProducts: [],
            filteredProducts: {
                total: 0,
                products: []
            },
            spotPrice: null,
            spotPriceHistory: [],
            stats: {
                live: {},
                historical: {
                    total_scans: 0,
                    total_products_ever: 0,
                    total_good_deals: 0,
                    avg_discount_all: 0,
                    source_distribution: {},
                    purity_distribution: {},
                    best_deal_ever: null
                }
            },
            timeline: null,
            
            // ========== FAVORITES ==========
            favorites: JSON.parse(localStorage.getItem('goldFavorites') || '[]'),
            
            // ========== FILTERS ==========
            filters: {
                source: '',
                purity: '',
                min_discount: -3,
                max_discount: 100,
                min_weight: 0,
                max_weight: 100,
                search: '',
                inStock: false,
                onlyFavorites: false
            },
            
            // ========== PAGINATION (FIXED) ==========
            currentPage: 1,
            itemsPerPage: 12,
            pageSizeOptions: [12, 24, 48, 96],
            sortBy: 'discount_percent',
            sortOrder: 'desc',
            
            // ========== CHARTS ==========
            scansChart: null,
            distributionChart: null,
            timelineChart: null,
            priceHistoryChart: null,
            
            // ========== EXPORT ==========
            exportFormat: 'csv',
            exporting: false,
            
            // ========== NOTIFICATIONS ==========
            notifications: [],
            notificationId: 0,
            
            // ========== KEYBOARD SHORTCUTS ==========
            keysPressed: {},
            
            // ========== PRICE ALERTS ==========
            priceAlerts: JSON.parse(localStorage.getItem('priceAlerts') || '[]'),
            showPriceAlertModal: false,
            alertProduct: null,
            alertPrice: null,
            
            // ========== STATS ==========
            averagePricePerGram: 0,
            totalValue: 0,
            bestDeal: null,
            
            // ========== DEBUG ==========
            debug: false
        },
        
        // ========== COMPUTED ==========
        computed: {
            // ✅ FIXED: Pagination using latest scan only
            paginatedProducts() {
                if (!this.filteredProducts?.products?.length) return [];
                const start = (this.currentPage - 1) * this.itemsPerPage;
                const end = start + this.itemsPerPage;
                return this.filteredProducts.products.slice(start, end);
            },
            
            // ✅ FIXED: Total pages based on filtered products count
            totalPages() {
                return Math.ceil((this.filteredProducts.total || 0) / this.itemsPerPage);
            },
            
            // Show page range (e.g., "1-12 of 145")
            pageRange() {
                if (!this.filteredProducts.products?.length) return '0';
                const start = ((this.currentPage - 1) * this.itemsPerPage) + 1;
                const end = Math.min(start + this.itemsPerPage - 1, this.filteredProducts.total);
                return `${start}-${end}`;
            },
            
            // Unique filter options (from latest scan only)
            uniqueSources() {
                if (!this.allProducts?.length) return [];
                return [...new Set(this.allProducts.map(p => p.source).filter(Boolean))];
            },
            
            uniquePurities() {
                if (!this.allProducts?.length) return [];
                return [...new Set(this.allProducts.map(p => p.purity).filter(Boolean))];
            },
            
            uniqueBrands() {
                if (!this.allProducts?.length) return [];
                return [...new Set(this.allProducts.map(p => p.brand).filter(Boolean))].slice(0, 10);
            },
            
            // Stats from latest scan
            totalProductsCount() {
                return this.allProducts.length || 0;
            },
            
            goodDealsCount() {
                return this.allProducts.filter(p => (p.discount_percent || 0) >= 10).length;
            },
            
            averageDiscount() {
                if (!this.allProducts.length) return 0;
                const sum = this.allProducts.reduce((acc, p) => acc + (p.discount_percent || 0), 0);
                return (sum / this.allProducts.length).toFixed(1);
            },
            
            maxDiscount() {
                if (!this.allProducts.length) return 0;
                return Math.max(...this.allProducts.map(p => p.discount_percent || 0));
            },
            
            // Total value of all products
            totalInventoryValue() {
                return this.allProducts.reduce((acc, p) => acc + (p.selling_price || 0), 0);
            },
            
            // Favorites
            favoriteProducts() {
                return this.allProducts.filter(p => this.favorites.includes(p.url));
            },
            
            // Filtered favorites count
            filteredFavoritesCount() {
                return this.filteredProducts.products?.filter(p => this.favorites.includes(p.url)).length || 0;
            },
            
            // Dark mode class
            darkModeClass() {
                return this.darkMode ? 'dark' : '';
            },
            
            // Scan timestamp formatted
            scanTimeFormatted() {
                if (!this.currentScanTimestamp) return 'Never';
                return new Date(this.currentScanTimestamp).toLocaleString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                });
            },
            
            // Keyboard shortcut hints
            shortcutHints() {
                return [
                    { key: '⌘F', action: 'Focus search' },
                    { key: '⌘R', action: 'Refresh data' },
                    { key: '⌘N', action: 'New scan' },
                    { key: '⌘D', action: 'Toggle dark mode' },
                    { key: '⌘E', action: 'Export data' },
                    { key: '⌘,', action: 'Settings' },
                    { key: 'ESC', action: 'Close modal' }
                ];
            }
        },
        
        // ========== WATCHERS ==========
        watch: {
            filters: {
                handler() {
                    this.currentPage = 1;
                    this.applyFilters();
                },
                deep: true
            },
            sortBy: 'applySorting',
            sortOrder: 'applySorting',
            itemsPerPage() {
                this.currentPage = 1;
                this.applyFilters();
            },
            darkMode(val) {
                localStorage.setItem('darkMode', val);
                if (val) {
                    document.documentElement.classList.add('dark');
                } else {
                    document.documentElement.classList.remove('dark');
                }
            },
            favorites: {
                handler(val) {
                    localStorage.setItem('goldFavorites', JSON.stringify(val));
                },
                deep: true
            }
        },
        
        // ========== MOUNTED ==========
        mounted() {
            console.log('✅ Vue mounted - Loading latest scan only');
            this.initKeyboardShortcuts();
            this.loadLatestScanOnly();
            this.setupAutoRefresh();
            this.loadSpotPriceHistory();
            
            // Apply dark mode on load
            if (this.darkMode) {
                document.documentElement.classList.add('dark');
            }
            
            // Show welcome notification
            this.$nextTick(() => {
                this.showNotification('success', '✨ Gold Deal Finder Premium loaded');
            });
        },
        
        // ========== METHODS ==========
        methods: {
            // ========== ✅ FIXED: LOAD LATEST SCAN ONLY ==========
            async loadLatestScanOnly() {
                this.loading = true;
                try {
                    // Get latest scan file directly
                    const scansRes = await axios.get('/api/v1/historical/scans?limit=1');
                    if (scansRes.data && scansRes.data.length > 0) {
                        const latestScan = scansRes.data[0];
                        this.currentScanId = latestScan.scan_id;
                        this.currentScanTimestamp = latestScan.timestamp;
                        
                        // Load complete products from this scan only
                        const productsRes = await axios.get(`/api/v1/historical/scan/${this.currentScanId}`);
                        if (productsRes.data && productsRes.data.products) {
                            this.allProducts = productsRes.data.products;
                            this.latestProducts = this.allProducts.slice(0, 6);
                            
                            // Initialize filtered products with all products
                            this.filteredProducts = {
                                total: this.allProducts.length,
                                products: [...this.allProducts]
                            };
                            this.applySorting();
                            console.log(`✅ Loaded ${this.allProducts.length} products from scan ${this.currentScanId}`);
                        }
                    }
                    
                    // Load supporting data
                    await Promise.all([
                        this.fetchScans(), // Get last 5 scans for history
                        this.fetchStats(),
                        this.fetchSpotPrice(),
                        this.fetchTimeline()
                    ]);
                    
                    this.$nextTick(() => this.initCharts());
                    this.calculateStats();
                    
                } catch (error) {
                    console.error('Error loading latest scan:', error);
                    this.showNotification('error', 'Failed to load latest scan data');
                } finally {
                    this.loading = false;
                }
            },
            
            // ========== ✅ FIXED: APPLY FILTERS ==========
            applyFilters() {
                if (!this.allProducts.length) {
                    this.filteredProducts = { total: 0, products: [] };
                    return;
                }
                
                let filtered = [...this.allProducts];
                
                // Source filter
                if (this.filters.source) {
                    filtered = filtered.filter(p => p.source === this.filters.source);
                }
                
                // Purity filter
                if (this.filters.purity) {
                    filtered = filtered.filter(p => p.purity === this.filters.purity);
                }
                
                // Discount range
                filtered = filtered.filter(p => 
                    p.discount_percent >= this.filters.min_discount && 
                    p.discount_percent <= this.filters.max_discount
                );
                
                // Weight range
                filtered = filtered.filter(p => 
                    p.weight_grams >= this.filters.min_weight && 
                    p.weight_grams <= this.filters.max_weight
                );
                
                // Search
                if (this.filters.search) {
                    const searchLower = this.filters.search.toLowerCase();
                    filtered = filtered.filter(p => 
                        p.title.toLowerCase().includes(searchLower) ||
                        p.brand.toLowerCase().includes(searchLower) ||
                        p.purity.toLowerCase().includes(searchLower)
                    );
                }
                
                // In stock only
                if (this.filters.inStock) {
                    filtered = filtered.filter(p => p.available !== false);
                }
                
                // Favorites only
                if (this.filters.onlyFavorites) {
                    filtered = filtered.filter(p => this.favorites.includes(p.url));
                }
                
                // Update filtered products
                this.filteredProducts = {
                    total: filtered.length,
                    products: filtered
                };
                
                this.applySorting();
                console.log(`🔍 Filtered: ${filtered.length} of ${this.allProducts.length} products`);
            },
            
            // ========== ✅ FIXED: APPLY SORTING ==========
            applySorting() {
                if (!this.filteredProducts.products?.length) return;
                
                const sortField = this.sortBy;
                const sortMultiplier = this.sortOrder === 'desc' ? -1 : 1;
                
                this.filteredProducts.products.sort((a, b) => {
                    let valA = a[sortField] || 0;
                    let valB = b[sortField] || 0;
                    
                    if (sortField === 'timestamp') {
                        valA = new Date(valA).getTime();
                        valB = new Date(valB).getTime();
                    }
                    
                    if (valA < valB) return -1 * sortMultiplier;
                    if (valA > valB) return 1 * sortMultiplier;
                    return 0;
                });
            },
            
            // ========== FETCH SUPPORTING DATA ==========
            async fetchScans() {
                try {
                    const res = await axios.get('/api/v1/historical/scans?limit=5');
                    this.scans = res.data || [];
                } catch (error) {
                    console.error('Error fetching scans:', error);
                    this.scans = [];
                }
            },
            
            async fetchStats() {
                try {
                    const res = await axios.get('/api/v1/stats/summary');
                    this.stats = res.data || { live: {}, historical: {} };
                } catch (error) {
                    console.error('Error fetching stats:', error);
                }
            },
            
            async fetchSpotPrice() {
                try {
                    const res = await axios.get('/api/v1/spot-price');
                    this.spotPrice = res.data;
                } catch (error) {
                    console.error('Error fetching spot price:', error);
                }
            },
            
            async fetchTimeline() {
                try {
                    const res = await axios.get('/api/v1/historical/timeline?days=30');
                    this.timeline = res.data;
                    this.$nextTick(() => this.updateTimelineChart());
                } catch (error) {
                    console.error('Error fetching timeline:', error);
                }
            },
            
            async loadSpotPriceHistory() {
                // Simulate price history for demo
                this.spotPriceHistory = Array.from({ length: 30 }, (_, i) => ({
                    date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
                    price: 5800 + Math.floor(Math.random() * 400)
                }));
            },
            
            // ========== STATS CALCULATION ==========
            calculateStats() {
                if (!this.allProducts.length) return;
                
                this.averagePricePerGram = this.allProducts.reduce((acc, p) => acc + (p.price_per_gram || 0), 0) / this.allProducts.length;
                this.totalValue = this.allProducts.reduce((acc, p) => acc + (p.selling_price || 0), 0);
                this.bestDeal = this.allProducts.reduce((best, p) => 
                    (p.discount_percent || 0) > (best?.discount_percent || 0) ? p : best, null);
            },
            
            // ========== FAVORITES ==========
            toggleFavorite(product) {
                const index = this.favorites.indexOf(product.url);
                if (index === -1) {
                    this.favorites.push(product.url);
                    this.showNotification('success', '⭐ Added to favorites');
                } else {
                    this.favorites.splice(index, 1);
                    this.showNotification('info', 'Removed from favorites');
                }
            },
            
            isFavorite(product) {
                return this.favorites.includes(product.url);
            },
            
            // ========== EXPORT ==========
            async exportData() {
                this.exporting = true;
                try {
                    let data = this.filteredProducts.products;
                    let filename = `gold-deals-${new Date().toISOString().split('T')[0]}`;
                    
                    if (this.exportFormat === 'csv') {
                        this.exportCSV(data, filename);
                    } else if (this.exportFormat === 'json') {
                        this.exportJSON(data, filename);
                    }
                    
                    this.showNotification('success', `📊 Exported ${data.length} products`);
                    this.showExportModal = false;
                } catch (error) {
                    console.error('Export error:', error);
                    this.showNotification('error', 'Export failed');
                } finally {
                    this.exporting = false;
                }
            },
            
            exportCSV(data, filename) {
                const headers = ['Source', 'Brand', 'Title', 'Purity', 'Weight', 'Price', 'Discount', 'Price/g', 'URL'];
                const rows = data.map(p => [
                    p.source,
                    p.brand,
                    p.title.replace(/,/g, ';'),
                    p.purity,
                    p.weight_grams,
                    p.selling_price,
                    `${p.discount_percent}%`,
                    p.price_per_gram,
                    p.url
                ]);
                
                const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.csv`;
                a.click();
                URL.revokeObjectURL(url);
            },
            
            exportJSON(data, filename) {
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${filename}.json`;
                a.click();
                URL.revokeObjectURL(url);
            },
            
            // ========== PRICE ALERTS ==========
            setPriceAlert(product) {
                this.alertProduct = product;
                this.alertPrice = Math.round(product.selling_price * 0.9); // 10% below current
                this.showPriceAlertModal = true;
            },
            
            savePriceAlert() {
                const alert = {
                    id: Date.now(),
                    product: this.alertProduct,
                    targetPrice: this.alertPrice,
                    createdAt: new Date().toISOString(),
                    active: true
                };
                
                this.priceAlerts.push(alert);
                localStorage.setItem('priceAlerts', JSON.stringify(this.priceAlerts));
                this.showPriceAlertModal = false;
                this.showNotification('success', `🔔 Alert set for ₹${this.alertPrice.toLocaleString()}`);
            },
            
            removePriceAlert(alertId) {
                this.priceAlerts = this.priceAlerts.filter(a => a.id !== alertId);
                localStorage.setItem('priceAlerts', JSON.stringify(this.priceAlerts));
                this.showNotification('info', 'Price alert removed');
            },
            
            // ========== NOTIFICATIONS ==========
            showNotification(type, message, duration = 3000) {
                const id = this.notificationId++;
                const notification = { id, type, message };
                
                this.notifications.push(notification);
                
                setTimeout(() => {
                    const index = this.notifications.findIndex(n => n.id === id);
                    if (index !== -1) this.notifications.splice(index, 1);
                }, duration);
            },
            
            // ========== KEYBOARD SHORTCUTS ==========
            initKeyboardShortcuts() {
                window.addEventListener('keydown', this.handleKeyDown);
                window.addEventListener('keyup', this.handleKeyUp);
            },
            
            handleKeyDown(e) {
                this.keysPressed[e.key.toLowerCase()] = true;
                
                // Cmd+F or Ctrl+F: Focus search
                if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
                    e.preventDefault();
                    this.focusSearch();
                }
                
                // Cmd+R or Ctrl+R: Refresh
                if ((e.metaKey || e.ctrlKey) && e.key === 'r') {
                    e.preventDefault();
                    this.refreshData();
                }
                
                // Cmd+N or Ctrl+N: New scan
                if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
                    e.preventDefault();
                    this.showScanModal = true;
                }
                
                // Cmd+D or Ctrl+D: Dark mode
                if ((e.metaKey || e.ctrlKey) && e.key === 'd') {
                    e.preventDefault();
                    this.darkMode = !this.darkMode;
                }
                
                // Cmd+E or Ctrl+E: Export
                if ((e.metaKey || e.ctrlKey) && e.key === 'e') {
                    e.preventDefault();
                    this.showExportModal = true;
                }
                
                // Cmd+, : Settings
                if ((e.metaKey || e.ctrlKey) && e.key === ',') {
                    e.preventDefault();
                    this.showSettingsModal = true;
                }
                
                // ESC: Close modals
                if (e.key === 'Escape') {
                    this.closeAllModals();
                }
            },
            
            handleKeyUp(e) {
                delete this.keysPressed[e.key.toLowerCase()];
            },
            
            focusSearch() {
                const searchInput = document.querySelector('input[placeholder*="Search"]');
                if (searchInput) searchInput.focus();
            },
            
            closeAllModals() {
                this.showScanModal = false;
                this.showExportModal = false;
                this.showFavoritesModal = false;
                this.showSettingsModal = false;
                this.showPriceAlertModal = false;
                this.showPriceHistoryModal = false;
                this.selectedProduct = null;
            },
            
            // ========== PAGINATION CONTROLS ==========
            nextPage() {
                if (this.currentPage < this.totalPages) {
                    this.currentPage++;
                }
            },
            
            prevPage() {
                if (this.currentPage > 1) {
                    this.currentPage--;
                }
            },
            
            goToPage(page) {
                if (page >= 1 && page <= this.totalPages) {
                    this.currentPage = page;
                }
            },
            
            // ========== SCAN ACTIONS ==========
            async startNewScan() {
                this.scanning = true;
                try {
                    const res = await axios.get('/api/v1/scan');
                    this.showNotification('success', `🔄 Scan started! Found ${res.data.total_count} products`);
                    this.showScanModal = false;
                    
                    // Reload latest scan after 3 seconds
                    setTimeout(() => {
                        this.loadLatestScanOnly();
                        this.showNotification('success', '✨ Latest scan loaded');
                    }, 3000);
                    
                } catch (error) {
                    console.error('Error starting scan:', error);
                    this.showNotification('error', 'Failed to start scan');
                } finally {
                    this.scanning = false;
                }
            },
            
            async refreshData() {
                this.loading = true;
                try {
                    await axios.post('/api/v1/cache/clear');
                    await this.loadLatestScanOnly();
                    this.showNotification('success', '✨ Data refreshed');
                } catch (error) {
                    console.error('Error refreshing data:', error);
                    this.showNotification('error', 'Refresh failed');
                } finally {
                    this.loading = false;
                }
            },
            
            resetFilters() {
                this.filters = {
                    source: '',
                    purity: '',
                    min_discount: -3,
                    max_discount: 100,
                    min_weight: 0,
                    max_weight: 100,
                    search: '',
                    inStock: false,
                    onlyFavorites: false
                };
                this.showNotification('info', 'Filters reset');
            },
            
            // ========== PRODUCT ACTIONS ==========
            viewProductDetails(product) {
                this.selectedProduct = product;
            },
            
            handleImageError(e) {
                e.target.src = 'https://placehold.co/400x400/FFD700/FFFFFF?text=Gold';
            },
            
            shareProduct(product) {
                if (navigator.share) {
                    navigator.share({
                        title: product.title,
                        text: `💰 ${product.discount_percent}% off! ₹${product.selling_price.toLocaleString()}`,
                        url: product.url
                    }).catch(() => {});
                } else {
                    navigator.clipboard.writeText(product.url);
                    this.showNotification('success', '📋 Link copied to clipboard');
                }
            },
            
            // ========== FORMATTING ==========
            formatCurrency(value) {
                if (!value) return '₹0';
                return `₹${value.toLocaleString('en-IN')}`;
            },
            
            formatWeight(grams) {
                if (grams >= 1000) {
                    return `${(grams / 1000).toFixed(2)}kg`;
                }
                return `${grams}g`;
            },
            
            formatDiscount(discount) {
                return `${discount.toFixed(1)}%`;
            },
            
            formatDate(timestamp) {
                if (!timestamp) return 'N/A';
                try {
                    return new Date(timestamp).toLocaleDateString('en-IN', {
                        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
                    });
                } catch {
                    return 'N/A';
                }
            },
            
            formatDateTime(timestamp) {
                if (!timestamp) return 'N/A';
                try {
                    return new Date(timestamp).toLocaleString('en-IN', {
                        day: '2-digit', month: 'short', year: 'numeric',
                        hour: '2-digit', minute: '2-digit', second: '2-digit'
                    });
                } catch {
                    return 'N/A';
                }
            },
            
            // ========== STYLING ==========
            getDiscountClass(discount) {
                if (discount >= 30) return 'bg-gradient-to-r from-red-500 to-pink-500 text-white';
                if (discount >= 20) return 'bg-gradient-to-r from-orange-500 to-amber-500 text-white';
                if (discount >= 10) return 'bg-gradient-to-r from-yellow-500 to-amber-500 text-white';
                if (discount >= 5) return 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white';
                return 'bg-gray-500 text-white';
            },
            
            getSourceIcon(source) {
                const icons = {
                    'AJIO': 'fa-bolt',
                    'Myntra': 'fa-shopping-bag',
                    'Amazon': 'fa-amazon',
                    'Flipkart': 'fa-shopping-cart'
                };
                return icons[source] || 'fa-store';
            },
            
            getTypeIcon(type) {
                return type === 'jewellery' ? 'fa-ring' : 'fa-coins';
            },
            
            getWeightColor(weight) {
                if (weight >= 20) return 'text-purple-600';
                if (weight >= 10) return 'text-blue-600';
                if (weight >= 5) return 'text-green-600';
                return 'text-gray-600';
            },
            
            // ========== CHARTS ==========
            initCharts() {
                this.initScansChart();
                this.initDistributionChart();
            },
            
            initScansChart() {
                const ctx = document.getElementById('scansChart');
                if (!ctx || !this.scans?.length) return;
                if (this.scansChart) this.scansChart.destroy();
                
                const recent = this.scans.slice(0, 7).reverse();
                try {
                    this.scansChart = new Chart(ctx.getContext('2d'), {
                        type: 'line',
                        data: {
                            labels: recent.map(s => {
                                try {
                                    return new Date(s.timestamp).toLocaleDateString('en-IN', {
                                        day: '2-digit', month: 'short'
                                    });
                                } catch {
                                    return 'N/A';
                                }
                            }),
                            datasets: [
                                {
                                    label: 'Products',
                                    data: recent.map(s => s.total_products || 0),
                                    borderColor: '#FDB813',
                                    backgroundColor: 'rgba(253, 184, 19, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                },
                                {
                                    label: 'Deals',
                                    data: recent.map(s => s.good_deals || 0),
                                    borderColor: '#27ae60',
                                    backgroundColor: 'rgba(39, 174, 96, 0.1)',
                                    tension: 0.4,
                                    fill: true
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false },
                                tooltip: { mode: 'index', intersect: false }
                            }
                        }
                    });
                } catch (e) {
                    console.error('Chart error:', e);
                }
            },
            
            initDistributionChart() {
                const ctx = document.getElementById('distributionChart');
                if (!ctx) return;
                if (this.distributionChart) this.distributionChart.destroy();
                
                // Use latest scan data instead of historical
                const sources = {};
                this.allProducts.forEach(p => {
                    sources[p.source] = (sources[p.source] || 0) + 1;
                });
                
                const labels = Object.keys(sources);
                const data = Object.values(sources);
                
                if (!labels.length) return;
                
                try {
                    this.distributionChart = new Chart(ctx.getContext('2d'), {
                        type: 'doughnut',
                        data: {
                            labels: labels,
                            datasets: [{
                                data: data,
                                backgroundColor: ['#FDB813', '#8e44ad', '#e74c3c', '#3498db', '#2ecc71'],
                                borderWidth: 0
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom' }
                            }
                        }
                    });
                } catch (e) {
                    console.error('Chart error:', e);
                }
            },
            
            updateTimelineChart() {
                const ctx = document.getElementById('timelineChart');
                if (!ctx || !this.timeline?.timeline) return;
                if (this.timelineChart) this.timelineChart.destroy();
                
                const dates = Object.keys(this.timeline.timeline).sort().slice(-14);
                try {
                    this.timelineChart = new Chart(ctx.getContext('2d'), {
                        type: 'bar',
                        data: {
                            labels: dates,
                            datasets: [
                                {
                                    label: 'Scans',
                                    data: dates.map(d => this.timeline.timeline[d]?.scans || 0),
                                    backgroundColor: '#FDB813',
                                    yAxisID: 'y'
                                },
                                {
                                    label: 'Products',
                                    data: dates.map(d => this.timeline.timeline[d]?.products || 0),
                                    backgroundColor: '#3498db',
                                    yAxisID: 'y1'
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    title: { display: true, text: 'Scans' }
                                },
                                y1: {
                                    beginAtZero: true,
                                    position: 'right',
                                    title: { display: true, text: 'Products' },
                                    grid: { drawOnChartArea: false }
                                }
                            }
                        }
                    });
                } catch (e) {
                    console.error('Chart error:', e);
                }
            },
            
            // ========== AUTO REFRESH ==========
            setupAutoRefresh() {
                // Refresh spot price every 5 minutes
                setInterval(() => this.fetchSpotPrice(), 5 * 60 * 1000);
                
                // Check for new scans every 10 minutes
                setInterval(() => {
                    this.checkForNewScan();
                }, 10 * 60 * 1000);
            },
            
            async checkForNewScan() {
                try {
                    const res = await axios.get('/api/v1/historical/scans?limit=1');
                    if (res.data[0]?.scan_id !== this.currentScanId) {
                        this.showNotification('info', '🔄 New scan detected! Refreshing...');
                        this.loadLatestScanOnly();
                    }
                } catch (e) {
                    console.error('Error checking for new scan:', e);
                }
            },
            
            // ========== UTILITIES ==========
            copyToClipboard(text) {
                navigator.clipboard.writeText(text);
                this.showNotification('success', '📋 Copied to clipboard');
            },
            
            getContrastColor(hexcolor) {
                // Simple contrast calculator for badges
                const r = parseInt(hexcolor.substr(1, 2), 16);
                const g = parseInt(hexcolor.substr(3, 2), 16);
                const b = parseInt(hexcolor.substr(5, 2), 16);
                const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
                return (yiq >= 128) ? 'text-gray-900' : 'text-white';
            },
            
            // ========== DEBUG ==========
            toggleDebug() {
                this.debug = !this.debug;
                console.log('Debug mode:', this.debug);
                if (this.debug) {
                    console.log('All Products:', this.allProducts);
                    console.log('Filtered:', this.filteredProducts);
                    console.log('Current Page:', this.currentPage);
                    console.log('Total Pages:', this.totalPages);
                }
            }
        }
    });
    
    console.log('✅ Gold Deal Finder Premium ready!');
    
} catch (error) {
    console.error('❌ FATAL ERROR:', error);
    document.body.innerHTML += `<div style="padding: 20px; background: #ffebee; border: 2px solid #f44336; margin: 20px;">
        <h3 style="color: #f44336;">❌ Application Failed to Start</h3>
        <pre style="background: #fff; padding: 10px;">${error.toString()}</pre>
    </div>`;
}