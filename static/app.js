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
            activeCalcTab: 'bill',
            sidebarCollapsed: localStorage.getItem('goldSidebarCollapsed') === 'true',
            commandPaletteOpen: false,
            paletteQuery: '',
            showFilterDrawer: false,
            showSourcesInfo: false,

            // Interactive Investment & Calculation Suite State
            calcBill: {
                weight: 10,
                unit: 'gram',
                karat: '22',
                makingPercent: 8,
                discountPerGram: 0,
                includeGst: true,
            },
            calcBudget: {
                amount: 50000,
                karat: '22',
            },
            calcWorth: {
                weight: 25,
                unit: 'gram',
                karat: '22',
                buyPricePerGram: 0,
                buyDate: '',
            },
            calcSip: {
                mode: 'budget',
                amount: 5000,
                weight: 1,
                karat: '24',
                durationMonths: 12,
                cagr: 10,
            },
            calcGoal: {
                mode: 'weight',
                targetWeight: 25,
                targetMoney: 200000,
                karat: '22',
                durationMonths: 24,
                cagr: 10,
            },

            // Market Signals & Cultural Tools State
            matrixUnit: '1g',
            muhuratDrawerOpen: false,
            muhuratFilter: 'upcoming',
            countdownNow: Date.now(),
            auspiciousDates: [
                {
                    name: 'Dhanteras (Diwali)',
                    date: '2026-11-06T18:14:00+05:30',
                    displayDate: '06 November 2026',
                    occasion: 'Prime Gold Buying Festival',
                    significance: 'Wealth & Prosperity',
                    auspiciousTime: '06:14 PM to 08:20 PM',
                    badge: 'FESTIVAL OF WEALTH'
                },
                {
                    name: 'Diwali (Lakshmi Puja)',
                    date: '2026-11-08T17:30:00+05:30',
                    displayDate: '08 November 2026',
                    occasion: 'Diwali Mahurat',
                    significance: 'Annual Family Jewelry Purchases',
                    auspiciousTime: '05:30 PM to 07:25 PM',
                    badge: 'MAHA LAKSHMI'
                },
                {
                    name: 'Guru Pushya Yoga (Nov)',
                    date: '2026-11-19T06:00:00+05:30',
                    displayDate: '19 November 2026',
                    occasion: 'Guru Pushya Nakshatra',
                    significance: 'Most Auspicious Nakshatra for Gold & Bullion',
                    auspiciousTime: 'Full Day Auspicious Tithi',
                    badge: 'HIGHLY AUSPICIOUS'
                },
                {
                    name: 'Pushya Nakshatra (Dec)',
                    date: '2026-12-16T07:05:00+05:30',
                    displayDate: '16 December 2026',
                    occasion: 'Pushya Nakshatra',
                    significance: 'Traditional Bullion Investment Day',
                    auspiciousTime: '07:05 AM to 03:40 PM',
                    badge: 'NAKSHATRA'
                },
                {
                    name: 'Makar Sankranti / Pongal',
                    date: '2027-01-14T08:30:00+05:30',
                    displayDate: '14 January 2027',
                    occasion: 'Harvest Festival',
                    significance: 'Auspicious Start for New Gold Investments',
                    auspiciousTime: '08:30 AM to 12:15 PM',
                    badge: 'FESTIVAL'
                },
                {
                    name: 'Vasant Panchami',
                    date: '2027-02-11T07:10:00+05:30',
                    displayDate: '11 February 2027',
                    occasion: 'Saraswati Puja',
                    significance: 'Shubh Muhurat for Gold Ornaments',
                    auspiciousTime: '07:10 AM to 12:35 PM',
                    badge: 'SHUBH MUHURAT'
                },
                {
                    name: 'Ugadi / Gudi Padwa',
                    date: '2027-04-07T06:05:00+05:30',
                    displayDate: '07 April 2027',
                    occasion: 'New Year Day',
                    significance: 'New Beginnings & Gold Coin Purchases',
                    auspiciousTime: '06:05 AM to 10:45 AM',
                    badge: 'NEW YEAR'
                },
                {
                    name: 'Akshaya Tritiya',
                    date: '2027-05-09T05:40:00+05:30',
                    displayDate: '09 May 2027',
                    occasion: 'Akshaya Tritiya (Akha Teej)',
                    significance: 'Highest Gold Buying Day in India (Eternal Wealth)',
                    auspiciousTime: '05:40 AM to 12:20 PM',
                    badge: 'GRAND MUHURAT'
                }
            ],

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
                return numeric(this.spotPrice?.gold?.per_gram?.['999_landed'], 8800);
            },

            liveSilverPrice() {
                return numeric(this.spotPrice?.silver?.per_gram, 98);
            },

            gsrRatio() {
                if (!this.liveSilverPrice || this.liveSilverPrice <= 0) return 88.5;
                return Math.round((this.liveSpotPrice / this.liveSilverPrice) * 10) / 10;
            },

            gsrPointerPosition() {
                // Scale from ratio 50 to 100
                const percent = ((this.gsrRatio - 50) / 50) * 100;
                return Math.max(5, Math.min(95, Math.round(percent)));
            },

            gsrInsight() {
                const ratio = this.gsrRatio;
                if (ratio > 80) {
                    return {
                        zone: 'silver',
                        badge: 'SILVER FAVORED',
                        title: 'Silver is Historically Undervalued',
                        desc: `At ${ratio}:1, 1 gram of 24K gold buys ${ratio} grams of silver. Historical mean is ~65:1. Current ratio indicates silver offers strong relative upside.`
                    };
                } else if (ratio < 65) {
                    return {
                        zone: 'gold',
                        badge: 'GOLD FAVORED',
                        title: 'Gold is Historically Undervalued',
                        desc: `At ${ratio}:1, gold purchasing power is high relative to silver. Gold offers stronger relative stability.`
                    };
                }
                return {
                    zone: 'fair',
                    badge: 'FAIR BALANCE',
                    title: 'Fair Valuation Equilibrium',
                    desc: `At ${ratio}:1, gold and silver are trading within normal historical valuation parity (65 to 80 range).`
                };
            },

            multiKaratMatrix() {
                const unitMultipliers = {
                    '1g': { label: '1 Gram', mult: 1 },
                    '8g': { label: '8 Grams (Pavan)', mult: 8 },
                    '10g': { label: '10 Grams', mult: 10 },
                    'tola': { label: '1 Tola (11.66g)', mult: 11.6638 },
                    '100g': { label: '100 Grams Bar', mult: 100 }
                };

                const currentMult = unitMultipliers[this.matrixUnit]?.mult || 1;
                const rates = this.karatRates;

                return {
                    unitLabel: unitMultipliers[this.matrixUnit]?.label || '1 Gram',
                    '24k': Math.round(rates['24'] * currentMult),
                    '22k': Math.round(rates['22'] * currentMult),
                    '18k': Math.round(rates['18'] * currentMult),
                    '9k': Math.round(rates['9'] * currentMult),
                };
            },

            nextMuhurat() {
                const now = this.countdownNow;
                return this.auspiciousDates.find((item) => new Date(item.date).getTime() > now) || this.auspiciousDates[0];
            },

            nextMuhuratCountdownFormatted() {
                if (!this.nextMuhurat) return 'Upcoming';
                const diff = new Date(this.nextMuhurat.date).getTime() - this.countdownNow;
                if (diff <= 0) return 'Auspicious Muhurat Live Today!';
                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                const secs = Math.floor((diff % (1000 * 60)) / 1000);
                return `${days}d ${hours}h ${mins}m ${secs}s left`;
            },

            filteredMuhurats() {
                const now = this.countdownNow;
                if (this.muhuratFilter === 'upcoming') {
                    return this.auspiciousDates.filter((item) => new Date(item.date).getTime() >= now);
                } else if (this.muhuratFilter === 'passed') {
                    return this.auspiciousDates.filter((item) => new Date(item.date).getTime() < now);
                }
                return this.auspiciousDates;
            },

            karatRates() {
                const spot24 = this.liveSpotPrice > 0 ? this.liveSpotPrice : 8800;
                return {
                    '24': spot24,
                    '22': Math.round(spot24 * (22 / 24)),
                    '18': Math.round(spot24 * (18 / 24)),
                    '14': Math.round(spot24 * (14 / 24)),
                    '9': Math.round(spot24 * (9 / 24)),
                };
            },

            billResult() {
                const unitMultipliers = { gram: 1, pavan: 8, tola: 11.6638 };
                const mult = unitMultipliers[this.calcBill.unit] || 1;
                const weightGrams = (numeric(this.calcBill.weight) || 0) * mult;
                const rate = this.karatRates[this.calcBill.karat] || this.karatRates['22'];
                const goldValue = weightGrams * rate;
                const discount = (numeric(this.calcBill.discountPerGram) || 0) * weightGrams;
                const effectiveGoldValue = Math.max(0, goldValue - discount);
                const makingCharges = effectiveGoldValue * ((numeric(this.calcBill.makingPercent) || 0) / 100);
                const subtotal = effectiveGoldValue + makingCharges;
                const gst = this.calcBill.includeGst ? subtotal * 0.03 : 0;
                const total = subtotal + gst;

                return {
                    weightGrams: Math.round(weightGrams * 100) / 100,
                    ratePerGram: rate,
                    goldValue: Math.round(goldValue),
                    discount: Math.round(discount),
                    effectiveGoldValue: Math.round(effectiveGoldValue),
                    makingCharges: Math.round(makingCharges),
                    gst: Math.round(gst),
                    total: Math.round(total),
                };
            },

            budgetResult() {
                const amount = numeric(this.calcBudget.amount);
                const rate = this.karatRates[this.calcBudget.karat] || this.karatRates['22'];
                const grams = rate > 0 ? amount / rate : 0;
                const pavans = grams / 8;
                const tolas = grams / 11.6638;

                return {
                    ratePerGram: rate,
                    grams: Math.round(grams * 1000) / 1000,
                    pavans: Math.round(pavans * 100) / 100,
                    tolas: Math.round(tolas * 100) / 100,
                };
            },

            worthResult() {
                const unitMultipliers = { gram: 1, pavan: 8, tola: 11.6638 };
                const mult = unitMultipliers[this.calcWorth.unit] || 1;
                const weightGrams = (numeric(this.calcWorth.weight) || 0) * mult;
                const rate = this.karatRates[this.calcWorth.karat] || this.karatRates['22'];
                const currentWorth = weightGrams * rate;
                const buyPrice = numeric(this.calcWorth.buyPricePerGram);
                const invested = buyPrice > 0 ? weightGrams * buyPrice : 0;
                const profitLoss = invested > 0 ? currentWorth - invested : 0;
                const returnsPercent = invested > 0 ? (profitLoss / invested) * 100 : 0;

                return {
                    weightGrams: Math.round(weightGrams * 100) / 100,
                    ratePerGram: rate,
                    currentWorth: Math.round(currentWorth),
                    invested: Math.round(invested),
                    profitLoss: Math.round(profitLoss),
                    returnsPercent: Math.round(returnsPercent * 10) / 10,
                };
            },

            sipResult() {
                const rate = this.karatRates[this.calcSip.karat] || this.karatRates['24'];
                const months = numeric(this.calcSip.durationMonths, 12);
                const cagr = numeric(this.calcSip.cagr, 10);
                const isBudgetMode = this.calcSip.mode === 'budget';

                let monthlyAmount = 0;
                let monthlyWeight = 0;

                if (isBudgetMode) {
                    monthlyAmount = numeric(this.calcSip.amount, 5000);
                    monthlyWeight = rate > 0 ? monthlyAmount / rate : 0;
                } else {
                    monthlyWeight = numeric(this.calcSip.weight, 1);
                    monthlyAmount = monthlyWeight * rate;
                }

                const totalGoldAccumulated = monthlyWeight * months;
                const totalInvested = monthlyAmount * months;
                const futureGoldRate = rate * Math.pow(1 + (cagr / 100), months / 12);
                const projectedMaturityValue = totalGoldAccumulated * futureGoldRate;
                const wealthGain = projectedMaturityValue - totalInvested;

                return {
                    ratePerGram: rate,
                    monthlyAmount: Math.round(monthlyAmount),
                    monthlyWeight: Math.round(monthlyWeight * 100) / 100,
                    totalGoldGrams: Math.round(totalGoldAccumulated * 100) / 100,
                    totalInvested: Math.round(totalInvested),
                    futureGoldRate: Math.round(futureGoldRate),
                    projectedMaturityValue: Math.round(projectedMaturityValue),
                    wealthGain: Math.round(wealthGain),
                };
            },

            goalResult() {
                const rate = this.karatRates[this.calcGoal.karat] || this.karatRates['22'];
                const months = numeric(this.calcGoal.durationMonths, 24);
                const cagr = numeric(this.calcGoal.cagr, 10);
                const isWeightMode = this.calcGoal.mode === 'weight';

                let targetWeight = 0;
                let futureTargetCorpus = 0;

                const futureGoldRate = rate * Math.pow(1 + (cagr / 100), months / 12);

                if (isWeightMode) {
                    targetWeight = numeric(this.calcGoal.targetWeight, 25);
                    futureTargetCorpus = targetWeight * futureGoldRate;
                } else {
                    futureTargetCorpus = numeric(this.calcGoal.targetMoney, 200000);
                    targetWeight = futureGoldRate > 0 ? futureTargetCorpus / futureGoldRate : 0;
                }

                // SIP required formula with compounding: SIP = Target * r / [((1+r)^n - 1) * (1+r)]
                const monthlyRate = (cagr / 100) / 12;
                let requiredMonthlySip = 0;
                if (monthlyRate > 0) {
                    const compoundFactor = Math.pow(1 + monthlyRate, months);
                    requiredMonthlySip = futureTargetCorpus * (monthlyRate / ((compoundFactor - 1) * (1 + monthlyRate)));
                } else {
                    requiredMonthlySip = futureTargetCorpus / months;
                }

                const totalInvested = requiredMonthlySip * months;
                const gainFromAppreciation = Math.max(0, futureTargetCorpus - totalInvested);

                return {
                    ratePerGram: rate,
                    futureGoldRate: Math.round(futureGoldRate),
                    targetWeight: Math.round(targetWeight * 100) / 100,
                    futureTargetCorpus: Math.round(futureTargetCorpus),
                    requiredMonthlySip: Math.round(requiredMonthlySip),
                    totalInvested: Math.round(totalInvested),
                    gainFromAppreciation: Math.round(gainFromAppreciation),
                };
            },

            bestCurrentDeal() {
                if (!this.allProducts.length) return null;
                const valid = this.allProducts.filter((p) => {
                    const ppg = numeric(p.price_per_gram);
                    const disc = numeric(p.discount_percent);
                    const wt = numeric(p.weight_grams);
                    const title = (p.title || '').toLowerCase();
                    const isOutOfStock = p.in_stock === false || p.stock_status === 'OUT_OF_STOCK' || p.is_available === false || title.includes('out of stock') || title.includes('sold out');
                    // Real gold listing criteria: valid stock, >0.3g weight, realistic gold price per gram (>= ₹3000/g) and sane discount (<40%)
                    return !isOutOfStock && ppg >= 3000 && wt >= 0.3 && disc < 40;
                });
                if (!valid.length) return null;
                return [...valid].sort((a, b) => numeric(b.discount_percent) - numeric(a.discount_percent))[0];
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

            sortedDealerRates() {
                if (!this.dealerRates) return [];
                const keys = ['bhima', 'kalyan', 'tanishq', 'mmtc', 'josalukkas', 'joyalukkas', 'malabar'];
                const cardConfigs = {
                    kalyan: {
                        brand: 'Kalyan Jewellers',
                        card_class: 'kalyan-card',
                        title: 'Kalyan Jewellers Rates',
                        tag: 'OFFICIAL BOARD RATE',
                        badge_bg: 'rgba(197, 160, 89, 0.15)',
                        badge_color: 'var(--gold-primary)',
                        tag_bg: 'rgba(197, 160, 89, 0.12)',
                        tag_color: 'var(--gold-primary)',
                        tag_border: 'rgba(197, 160, 89, 0.25)',
                        icon: 'fa-solid fa-gem',
                        filter_source: '',
                        site_label: 'Kalyan Site'
                    },
                    joyalukkas: {
                        brand: 'Joyalukkas',
                        card_class: 'joyalukkas-card',
                        title: 'Joyalukkas Rates',
                        tag: 'OFFICIAL BOARD RATE',
                        badge_bg: 'rgba(198, 40, 40, 0.15)',
                        badge_color: '#c62828',
                        tag_bg: 'rgba(198, 40, 40, 0.12)',
                        tag_color: '#c62828',
                        tag_border: 'rgba(198, 40, 40, 0.25)',
                        icon: 'fa-solid fa-crown',
                        filter_source: 'Joyalukkas',
                        site_label: 'Joyalukkas Site'
                    },
                    malabar: {
                        brand: 'Malabar Gold',
                        card_class: 'malabar-card',
                        title: 'Malabar Gold Rates',
                        tag: 'OFFICIAL BOARD RATE',
                        badge_bg: 'rgba(183, 28, 28, 0.15)',
                        badge_color: '#b71c1c',
                        tag_bg: 'rgba(183, 28, 28, 0.12)',
                        tag_color: '#b71c1c',
                        tag_border: 'rgba(183, 28, 28, 0.25)',
                        icon: 'fa-solid fa-coins',
                        filter_source: 'Malabar Gold',
                        site_label: 'Malabar Site'
                    },
                    josalukkas: {
                        brand: 'Jos Alukkas',
                        card_class: 'josalukkas-card',
                        title: 'Jos Alukkas Rates',
                        tag: 'OFFICIAL BOARD RATE',
                        badge_bg: 'rgba(230, 81, 0, 0.15)',
                        badge_color: '#e65100',
                        tag_bg: 'rgba(230, 81, 0, 0.12)',
                        tag_color: '#e65100',
                        tag_border: 'rgba(230, 81, 0, 0.25)',
                        icon: 'fa-solid fa-gem',
                        filter_source: 'Jos Alukkas',
                        site_label: 'Jos Alukkas Site'
                    },
                    tanishq: {
                        brand: 'Tanishq (Titan)',
                        card_class: 'tanishq-card',
                        title: 'Tanishq Live Rates',
                        tag: 'TATA GOLD RATE',
                        badge_bg: 'rgba(216, 27, 96, 0.15)',
                        badge_color: '#d81b60',
                        tag_bg: 'rgba(216, 27, 96, 0.12)',
                        tag_color: '#d81b60',
                        tag_border: 'rgba(216, 27, 96, 0.25)',
                        icon: 'fa-solid fa-gem',
                        filter_source: 'Tanishq',
                        site_label: 'Tanishq Site'
                    },
                    mmtc: {
                        brand: 'MMTC-PAMP',
                        card_class: 'mmtc-card',
                        title: 'MMTC-PAMP Live Rates',
                        tag: 'LBMA REFINERY RATE',
                        badge_bg: 'rgba(197, 160, 89, 0.15)',
                        badge_color: 'var(--gold-primary)',
                        tag_bg: 'rgba(197, 160, 89, 0.12)',
                        tag_color: 'var(--gold-primary)',
                        tag_border: 'rgba(197, 160, 89, 0.25)',
                        icon: 'fa-solid fa-building-columns',
                        filter_source: 'MMTC-PAMP',
                        site_label: 'MMTC Site'
                    },
                    bhima: {
                        brand: 'Bhima Gold',
                        card_class: 'bhima-card',
                        title: 'Bhima Gold Live Rates',
                        tag: 'OFFICIAL DEALER RATE',
                        badge_bg: 'rgba(197, 160, 89, 0.15)',
                        badge_color: 'var(--gold-primary)',
                        tag_bg: 'rgba(197, 160, 89, 0.12)',
                        tag_color: 'var(--gold-primary)',
                        tag_border: 'rgba(197, 160, 89, 0.25)',
                        icon: 'fa-solid fa-gem',
                        filter_source: 'Bhima Gold',
                        site_label: 'Shop Bhima'
                    }
                };

                const list = [];
                keys.forEach((key) => {
                    const data = this.dealerRates[key];
                    if (data && cardConfigs[key]) {
                        list.push({
                            key,
                            ...cardConfigs[key],
                            data,
                            sub_text: data.location ? `${data.location} Official Rate` : (data.tagline || 'Official Online Rate'),
                            rate_24k: numeric(data.rate_24k_per_g)
                        });
                    }
                });

                // Sort LOW TO HIGH by 24K per gram rate
                list.sort((a, b) => a.rate_24k - b.rate_24k);

                // Assign Rank (#1 Lowest Rate, #2, etc.)
                list.forEach((item, index) => {
                    item.rank = index + 1;
                });

                return list;
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
            this.countdownInterval = setInterval(() => {
                this.countdownNow = Date.now();
            }, 1000);
        },

        beforeDestroy() {
            window.removeEventListener('keydown', this.handleKeyDown);
            window.removeEventListener('resize', this.handleResize);
            this.destroyCharts();
            if (this.countdownInterval) {
                clearInterval(this.countdownInterval);
            }
        },

        methods: {
            getWhatsAppShareText() {
                const spot24 = this.formatCurrency(this.liveSpotPrice);
                const spot22 = this.formatCurrency(this.karatRates['22']);
                const spot18 = this.formatCurrency(this.karatRates['18']);
                const silver = this.formatCurrency(this.liveSilverPrice);
                const gsr = this.gsrRatio;
                const best = this.bestCurrentDeal;

                let msg = `🪙 *GOLD DEAL FINDER — DAILY LIVE BRIEFING*\n\n`;
                msg += `📊 *Live Benchmark Rates:*\n`;
                msg += `• 24K (999 Pure): ${spot24}/g (₹${Math.round(this.liveSpotPrice * 10).toLocaleString('en-IN')}/10g)\n`;
                msg += `• 22K (916 Hallmark): ${spot22}/g (₹${Math.round(this.karatRates['22'] * 8).toLocaleString('en-IN')}/8g Pavan)\n`;
                msg += `• 18K (750): ${spot18}/g\n`;
                msg += `• Silver (999): ${silver}/g\n\n`;
                msg += `⚖️ *Gold-to-Silver Ratio:* ${gsr}:1 (${this.gsrInsight.badge})\n`;

                if (best) {
                    const savings = Math.max(0, numeric(best.expected_price) - numeric(best.selling_price));
                    msg += `\n🔥 *Top Deal Today:*\n`;
                    msg += `• ${best.title}\n`;
                    msg += `• Vendor: ${best.source} | Purity: ${best.purity} | ${best.weight_grams}g\n`;
                    msg += `• Price: ${this.formatCurrency(best.selling_price)} (Save ${this.formatCurrency(savings)} / ${this.formatPercent(best.discount_percent)})\n`;
                    msg += `• Link: ${best.url}\n`;
                }

                if (this.nextMuhurat) {
                    msg += `\n✨ *Next Shubh Muhurat:* ${this.nextMuhurat.name} (${this.nextMuhurat.displayDate})\n`;
                }

                msg += `\nCheck live market deals on Gold Deal Finder.`;
                return msg;
            },

            shareOnWhatsApp() {
                const text = encodeURIComponent(this.getWhatsAppShareText());
                window.open(`https://api.whatsapp.com/send?text=${text}`, '_blank');
            },

            copyWhatsAppBriefing() {
                this.copyToClipboard(this.getWhatsAppShareText(), 'Daily Gold Deal Briefing copied to clipboard!');
            },

            getProductShareText(product) {
                if (!product) return this.getWhatsAppShareText();
                const savings = Math.max(0, numeric(product.expected_price) - numeric(product.selling_price));
                const ppg = this.formatCurrency(numeric(product.price_per_gram));
                const price = this.formatCurrency(numeric(product.selling_price));
                const exp = this.formatCurrency(numeric(product.expected_price));
                const disc = this.formatPercent(product.discount_percent);

                let msg = `🪙 *GOLD DEAL ALERT — ${product.source}*\n\n`;
                msg += `✨ *${product.title}*\n`;
                msg += `• Purity: ${product.purity || '24K'} | Weight: ${product.weight_grams}g\n`;
                msg += `• Deal Price: *${price}* (Effective ${ppg}/g)\n`;
                msg += `• Benchmark Value: ${exp}\n`;
                if (savings > 0) {
                    msg += `• 🔥 *You Save: ${this.formatCurrency(savings)} (${disc})*\n`;
                }
                msg += `\n🛒 *Buy Now:* ${product.url}\n`;
                msg += `\nLive rates: 24K @ ${this.formatCurrency(this.liveSpotPrice)}/g | GSR @ ${this.gsrRatio}:1`;
                return msg;
            },

            shareProductOnWhatsApp(product) {
                const text = encodeURIComponent(this.getProductShareText(product));
                window.open(`https://api.whatsapp.com/send?text=${text}`, '_blank');
            },

            copyProductWhatsApp(product) {
                this.copyToClipboard(this.getProductShareText(product), 'Product deal briefing copied!');
            },

            onSortByChange() {
                if (this.sortBy === 'selling_price' || this.sortBy === 'price_per_gram') {
                    this.sortOrder = 'asc';
                } else if (this.sortBy === 'discount_percent' || this.sortBy === 'weight_grams') {
                    this.sortOrder = 'desc';
                }
                this.currentPage = 1;
            },

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

            setCalcTab(tab) {
                this.activeCalcTab = tab;
            },

            getPurityKaratNumber(purityStr) {
                const clean = String(purityStr || '').toUpperCase();
                if (clean.includes('24') || clean.includes('999')) return '24';
                if (clean.includes('22') || clean.includes('916')) return '22';
                if (clean.includes('18') || clean.includes('750')) return '18';
                if (clean.includes('14') || clean.includes('585')) return '14';
                if (clean.includes('9') || clean.includes('375')) return '9';
                return '22';
            },

            getMeltBreakdown(product) {
                const weight = numeric(product.weight_grams);
                const karat = this.getPurityKaratNumber(product.purity);
                const rate = this.karatRates[karat] || this.karatRates['22'];
                const meltValue = Math.round(weight * rate);
                const rawWithGst = Math.round(meltValue * 1.03);
                const sellingPrice = numeric(product.selling_price);
                const makingMarkup = Math.round(Math.max(0, sellingPrice - rawWithGst));
                const makingPercent = meltValue > 0 ? Math.round((makingMarkup / meltValue) * 100 * 10) / 10 : 0;

                return {
                    karat,
                    meltValue,
                    rawWithGst,
                    makingMarkup,
                    makingPercent,
                };
            },

            openProductInCalculator(product) {
                if (!product) return;
                const karat = this.getPurityKaratNumber(product.purity);
                this.calcBill.weight = numeric(product.weight_grams, 10);
                this.calcBill.unit = 'gram';
                this.calcBill.karat = karat;
                this.calcBill.discountPerGram = 0;
                this.calcBill.includeGst = true;

                // Estimate making %
                const melt = this.getMeltBreakdown(product);
                this.calcBill.makingPercent = melt.makingPercent > 0 ? melt.makingPercent : 8;

                this.switchTab('calculators');
                this.activeCalcTab = 'bill';
                this.notify(`Loaded "${product.title.slice(0, 30)}..." into Jewelry Bill Calculator`, 'info');
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
