/**
 * RPC Benchmarker - Main Application
 */

import { api } from './api.js';
import { formatMs, formatPercent, formatDate, formatDuration, truncateAddress, getCategoryColor } from './utils/formatting.js';

// ============================================================================
// LocalStorage Keys
// ============================================================================

const STORAGE_KEYS = {
    RPC_HISTORY: 'rpc-benchmarker-rpc-history',
};

// ============================================================================
// RPC History Management
// ============================================================================

function getRpcHistory() {
    try {
        const stored = localStorage.getItem(STORAGE_KEYS.RPC_HISTORY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

function saveRpcHistory(history) {
    try {
        localStorage.setItem(STORAGE_KEYS.RPC_HISTORY, JSON.stringify(history));
    } catch (e) {
        console.error('Failed to save RPC history:', e);
    }
}

function addRpcToHistory(url) {
    if (!url || !url.trim()) return;
    const history = getRpcHistory();
    // Remove if exists, add to front
    const filtered = history.filter(h => h !== url);
    filtered.unshift(url);
    // Keep last 20
    saveRpcHistory(filtered.slice(0, 20));
}

function removeRpcFromHistory(url) {
    const history = getRpcHistory();
    saveRpcHistory(history.filter(h => h !== url));
}

// ============================================================================
// State
// ============================================================================

const state = {
    currentPage: 'benchmark',
    currentStep: 1,
    chains: [],
    testCases: [],
    selectedChain: null,
    providers: [{ name: '', url: '', region: '', validated: false }],
    providersValidated: false,
    selectedTests: new Set(),
    iterationMode: 'quick',
    selectedCategories: new Set(['simple', 'medium', 'complex', 'load']),
    selectedLabels: new Set(['latest', 'archival']),
    params: {},
    currentJobId: null,
    eventSource: null,
};

// ============================================================================
// DOM Elements
// ============================================================================

const elements = {
    // Navigation
    navLinks: document.querySelectorAll('.nav-link'),
    pages: document.querySelectorAll('.page'),

    // Wizard
    wizardSteps: document.querySelectorAll('.wizard-steps .step'),
    wizardContents: document.querySelectorAll('.wizard-content'),
    btnPrev: document.getElementById('btn-prev'),
    btnNext: document.getElementById('btn-next'),

    // Chain selection
    chainList: document.getElementById('chain-list'),

    // Providers
    providersContainer: document.getElementById('providers-container'),
    btnAddProvider: document.getElementById('btn-add-provider'),
    btnValidateProviders: document.getElementById('btn-validate-providers'),

    // Tests
    testList: document.getElementById('test-list'),
    btnSelectAllTests: document.getElementById('btn-select-all-tests'),
    btnDeselectAllTests: document.getElementById('btn-deselect-all-tests'),

    // Parameters
    btnRandomizeParams: document.getElementById('btn-randomize-params'),
    btnValidateParams: document.getElementById('btn-validate-params'),
    paramsValidationResults: document.getElementById('params-validation-results'),

    // Benchmark
    benchmarkSummary: document.getElementById('benchmark-summary'),
    benchmarkControls: document.getElementById('benchmark-controls'),
    btnStartBenchmark: document.getElementById('btn-start-benchmark'),
    benchmarkProgress: document.getElementById('benchmark-progress'),
    progressStatus: document.getElementById('progress-status'),
    progressBar: document.getElementById('progress-bar'),
    progressDetails: document.getElementById('progress-details'),
    btnCancelBenchmark: document.getElementById('btn-cancel-benchmark'),

    // History
    historyChainFilter: document.getElementById('history-chain-filter'),
    historyList: document.getElementById('history-list'),
    btnImportResults: document.getElementById('btn-import-results'),
    importFileInput: document.getElementById('import-file-input'),

    // Results
    resultsTabs: document.querySelectorAll('.tab-btn'),
    resultsContent: document.getElementById('results-content'),
    btnExportJson: document.getElementById('btn-export-json'),
    btnExportCsv: document.getElementById('btn-export-csv'),
    btnBackToHistory: document.getElementById('btn-back-to-history'),

    // Chains management
    chainsList: document.getElementById('chains-list'),
    btnAddChain: document.getElementById('btn-add-chain'),
    chainModal: document.getElementById('chain-modal'),
    chainForm: document.getElementById('chain-form'),
    btnSaveChain: document.getElementById('btn-save-chain'),
};

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    setupNavigation();
    setupWizard();
    setupProviders();
    setupTests();
    setupParams();
    setupBenchmark();
    setupHistory();
    setupResults();
    setupChainsPage();

    // Load initial data
    await loadChains();
    await loadTestCases();
}

// ============================================================================
// Navigation
// ============================================================================

function setupNavigation() {
    elements.navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            navigateToPage(page);
        });
    });

    // Logo click goes to new benchmark (step 1)
    const navHome = document.getElementById('nav-home');
    if (navHome) {
        navHome.addEventListener('click', (e) => {
            e.preventDefault();
            navigateToPage('benchmark');
            setWizardStep(1);
        });
    }
}

function navigateToPage(page) {
    state.currentPage = page;

    elements.navLinks.forEach(link => {
        link.classList.toggle('active', link.dataset.page === page);
    });

    elements.pages.forEach(p => {
        p.classList.toggle('hidden', p.id !== `page-${page}`);
        p.classList.toggle('active', p.id === `page-${page}`);
    });

    if (page === 'history') {
        loadHistory();
    } else if (page === 'chains') {
        renderChainsPage();
    }
}

// ============================================================================
// Wizard
// ============================================================================

function setupWizard() {
    elements.btnPrev.addEventListener('click', () => {
        if (state.currentStep > 1) {
            setWizardStep(state.currentStep - 1);
        }
    });

    elements.btnNext.addEventListener('click', async () => {
        if (await validateCurrentStep()) {
            if (state.currentStep < 5) {
                setWizardStep(state.currentStep + 1);
            }
        }
    });
}

function setWizardStep(step) {
    state.currentStep = step;

    elements.wizardSteps.forEach(s => {
        const stepNum = parseInt(s.dataset.step);
        s.classList.toggle('active', stepNum === step);
        s.classList.toggle('completed', stepNum < step);
    });

    elements.wizardContents.forEach(c => {
        c.classList.toggle('hidden', parseInt(c.dataset.step) !== step);
    });

    elements.btnPrev.disabled = step === 1;
    elements.btnNext.textContent = step === 4 ? 'Review' : 'Next';
    elements.btnNext.classList.toggle('hidden', step === 5);

    if (step === 3) {
        renderTestList();
    } else if (step === 5) {
        renderBenchmarkSummary();
    }
}

async function validateCurrentStep() {
    switch (state.currentStep) {
        case 1:
            if (!state.selectedChain) {
                alert('Please select a chain');
                return false;
            }
            return true;

        case 2:
            // Get providers that have URLs (may or may not have names yet)
            const providersWithUrls = state.providers.filter(p => p.url && p.url.startsWith('http'));
            if (providersWithUrls.length === 0) {
                alert('Please add at least one provider with an RPC URL');
                return false;
            }
            // All providers must be validated
            if (!state.providersValidated) {
                alert('All providers must pass validation before continuing. Click "Validate Providers" to check URLs.');
                return false;
            }
            // All providers with URLs must also have names before proceeding
            const providersWithoutNames = providersWithUrls.filter(p => !p.name || !p.name.trim());
            if (providersWithoutNames.length > 0) {
                alert('Please enter a name for all providers before continuing');
                return false;
            }
            return true;

        case 3:
            if (state.selectedTests.size === 0) {
                alert('Please select at least one test');
                return false;
            }
            return true;

        case 4:
            // Parameters validation is optional
            return true;

        default:
            return true;
    }
}

// ============================================================================
// Chains
// ============================================================================

async function loadChains() {
    try {
        state.chains = await api.listChains();
        renderChainList();
        updateHistoryChainFilter();
    } catch (e) {
        console.error('Failed to load chains:', e);
    }
}

function renderChainList() {
    elements.chainList.innerHTML = state.chains.map(chain => `
        <div class="chain-card ${state.selectedChain?.chain_id === chain.chain_id ? 'selected' : ''}"
             data-chain-id="${chain.chain_id}">
            <h3>${chain.chain_name}</h3>
            <span class="chain-id">Chain ID: ${chain.chain_id}</span>
        </div>
    `).join('');

    elements.chainList.querySelectorAll('.chain-card').forEach(card => {
        card.addEventListener('click', () => {
            const chainId = parseInt(card.dataset.chainId);
            state.selectedChain = state.chains.find(c => c.chain_id === chainId);
            renderChainList();
        });
    });
}

// ============================================================================
// Providers
// ============================================================================

function setupProviders() {
    elements.btnAddProvider.addEventListener('click', () => {
        if (state.providers.length < 10) {
            state.providers.push({ name: '', url: '', region: '', validated: false });
            state.providersValidated = false;
            renderProviders();
        }
    });

    elements.btnValidateProviders.addEventListener('click', validateProviders);

    renderProviders();
}

function renderProviders() {
    const rpcHistory = getRpcHistory();

    elements.providersContainer.innerHTML = state.providers.map((p, i) => `
        <div class="provider-entry ${p.validated === true ? 'validated' : p.validated === false ? '' : 'invalid'}" data-index="${i}">
            <div class="provider-status ${p.validated === true ? 'valid' : p.validated === 'error' ? 'invalid' : 'pending'}">
                ${p.validated === true ? '✓' : p.validated === 'error' ? '✗' : '○'}
            </div>
            <div class="provider-fields">
                <input type="text" class="provider-name" placeholder="Provider Name" value="${p.name}">
                <div class="rpc-url-combo">
                    <input type="url" class="provider-url" placeholder="RPC URL (https://...)" value="${p.url}" autocomplete="off">
                    ${rpcHistory.length > 0 ? `
                        <button type="button" class="rpc-dropdown-toggle" title="Recent URLs">▼</button>
                        <div class="rpc-dropdown hidden">
                            ${rpcHistory.map(url => `
                                <div class="rpc-dropdown-item" data-url="${url}">
                                    <span class="rpc-url-text" title="${url}">${truncateUrl(url)}</span>
                                    <button type="button" class="rpc-delete-btn" data-url="${url}" title="Remove from history">×</button>
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
                <input type="text" class="provider-region" placeholder="Region (optional)" value="${p.region}">
            </div>
            <button type="button" class="btn-icon btn-remove-provider" title="Remove">&times;</button>
        </div>
    `).join('');

    elements.providersContainer.querySelectorAll('.provider-entry').forEach(entry => {
        const index = parseInt(entry.dataset.index);

        entry.querySelector('.provider-name').addEventListener('input', (e) => {
            state.providers[index].name = e.target.value;
            state.providers[index].validated = false;
            state.providersValidated = false;
            updateProviderStatus(index);
        });

        // Auto-validate when name is filled (if URL already exists)
        entry.querySelector('.provider-name').addEventListener('blur', () => {
            if (state.providers[index].name && state.providers[index].url) {
                setTimeout(() => autoValidateProviders(), 100);
            }
        });

        const urlInput = entry.querySelector('.provider-url');
        urlInput.addEventListener('input', (e) => {
            state.providers[index].url = e.target.value;
            state.providers[index].validated = false;
            state.providersValidated = false;
            updateProviderStatus(index);
        });

        // Auto-validate on blur if URL looks valid
        urlInput.addEventListener('blur', (e) => {
            const url = e.target.value.trim();
            if (url && url.startsWith('http')) {
                addRpcToHistory(url);
                // Auto-validate after a short delay to allow UI to update
                setTimeout(() => autoValidateProviders(), 100);
            }
        });

        entry.querySelector('.provider-region').addEventListener('input', (e) => {
            state.providers[index].region = e.target.value;
        });

        entry.querySelector('.btn-remove-provider').addEventListener('click', () => {
            if (state.providers.length > 1) {
                state.providers.splice(index, 1);
                state.providersValidated = false;
                renderProviders();
            }
        });

        // Dropdown toggle
        const dropdownToggle = entry.querySelector('.rpc-dropdown-toggle');
        const dropdown = entry.querySelector('.rpc-dropdown');
        if (dropdownToggle && dropdown) {
            dropdownToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                // Close other dropdowns
                document.querySelectorAll('.rpc-dropdown').forEach(d => {
                    if (d !== dropdown) d.classList.add('hidden');
                });
                dropdown.classList.toggle('hidden');
            });

            // Select URL from dropdown
            dropdown.querySelectorAll('.rpc-url-text').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const url = item.parentElement.dataset.url;
                    urlInput.value = url;
                    state.providers[index].url = url;
                    state.providers[index].validated = false;
                    state.providersValidated = false;
                    dropdown.classList.add('hidden');
                    updateProviderStatus(index);
                    // Auto-validate when selecting from dropdown
                    setTimeout(() => autoValidateProviders(), 100);
                });
            });

            // Delete from history
            dropdown.querySelectorAll('.rpc-delete-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const url = btn.dataset.url;
                    removeRpcFromHistory(url);
                    renderProviders();
                });
            });
        }
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.rpc-dropdown').forEach(d => d.classList.add('hidden'));
    });

    elements.btnAddProvider.disabled = state.providers.length >= 10;
}

function truncateUrl(url) {
    if (url.length <= 50) return url;
    try {
        const parsed = new URL(url);
        const path = parsed.pathname + parsed.search;
        if (path.length > 30) {
            return parsed.origin + path.slice(0, 27) + '...';
        }
        return url.slice(0, 47) + '...';
    } catch {
        return url.slice(0, 47) + '...';
    }
}

function updateProviderStatus(index) {
    const entry = elements.providersContainer.querySelector(`[data-index="${index}"]`);
    if (entry) {
        const p = state.providers[index];
        entry.className = `provider-entry ${p.validated === true ? 'validated' : p.validated === 'error' ? 'invalid' : ''}`;
        const status = entry.querySelector('.provider-status');
        status.className = `provider-status ${p.validated === true ? 'valid' : p.validated === 'error' ? 'invalid' : 'pending'}`;
        status.textContent = p.validated === true ? '✓' : p.validated === 'error' ? '✗' : '○';
    }
}

async function validateProviders() {
    if (!state.selectedChain) {
        alert('Please select a chain first (go back to Step 1)');
        return;
    }

    // Validate providers that have URLs (name can be filled in later)
    const providersWithUrls = state.providers.filter(p => p.url && p.url.startsWith('http'));
    if (providersWithUrls.length === 0) {
        alert('Please add at least one provider with an RPC URL');
        return;
    }

    // Show loading state
    elements.btnValidateProviders.disabled = true;
    elements.btnValidateProviders.textContent = 'Validating...';

    // Mark all with URLs as validating
    state.providers.forEach((p, i) => {
        if (p.url && p.url.startsWith('http')) {
            const entry = elements.providersContainer.querySelector(`[data-index="${i}"]`);
            if (entry) {
                const status = entry.querySelector('.provider-status');
                status.className = 'provider-status validating';
                status.textContent = '↻';
            }
        }
    });

    try {
        const urls = state.providers.map(p => p.url).filter(u => u);
        const result = await api.validateProviders(urls, state.selectedChain.chain_id);

        // Update validation status for each provider
        let allValid = true;
        state.providers.forEach((p, i) => {
            if (p.url) {
                const providerResult = result.results.find(r => r.url.includes(p.url.split('?')[0].slice(-20)) || p.url.includes(r.url.split('?')[0].slice(-20)));
                if (providerResult) {
                    p.validated = providerResult.valid ? true : 'error';
                    p.validationError = providerResult.valid ? null : (providerResult.error || `Expected chain ${providerResult.expected_chain_id}, got ${providerResult.chain_id}`);
                    if (!providerResult.valid) allValid = false;
                } else {
                    // Match by index as fallback
                    const idx = urls.indexOf(p.url);
                    if (idx >= 0 && result.results[idx]) {
                        p.validated = result.results[idx].valid ? true : 'error';
                        p.validationError = result.results[idx].valid ? null : (result.results[idx].error || `Expected chain ${result.results[idx].expected_chain_id}, got ${result.results[idx].chain_id}`);
                        if (!result.results[idx].valid) allValid = false;
                    }
                }
            }
            updateProviderStatus(i);
        });

        state.providersValidated = allValid;

    } catch (e) {
        state.providersValidated = false;
        state.providers.forEach((p, i) => {
            if (p.url) {
                p.validated = 'error';
                p.validationError = e.message;
            }
            updateProviderStatus(i);
        });
    } finally {
        elements.btnValidateProviders.disabled = false;
        elements.btnValidateProviders.textContent = 'Validate Providers';
    }
}

// Auto-validate debounce state
let autoValidateTimer = null;
let isAutoValidating = false;

async function autoValidateProviders() {
    // Don't auto-validate if no chain selected
    if (!state.selectedChain) return;

    // Don't auto-validate if already validating
    if (isAutoValidating) return;

    // Check if there are any providers with URLs that need validation
    const providersNeedingValidation = state.providers.filter(p =>
        p.url && p.url.startsWith('http') && p.validated !== true
    );

    // If no providers need validation, or no providers with URLs, skip
    if (providersNeedingValidation.length === 0) return;

    // Check if all providers with URLs have been filled
    const providersWithUrls = state.providers.filter(p => p.url && p.url.startsWith('http'));
    if (providersWithUrls.length === 0) return;

    // Debounce - wait for user to stop typing
    if (autoValidateTimer) {
        clearTimeout(autoValidateTimer);
    }

    autoValidateTimer = setTimeout(async () => {
        isAutoValidating = true;
        await validateProviders();
        isAutoValidating = false;
    }, 500);
}

// ============================================================================
// Tests
// ============================================================================

async function loadTestCases() {
    try {
        state.testCases = await api.listTestCases();
        // Select all by default
        state.testCases.forEach(t => state.selectedTests.add(t.id));
    } catch (e) {
        console.error('Failed to load test cases:', e);
    }
}

function setupTests() {
    // Iteration mode
    document.querySelectorAll('input[name="iteration-mode"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            state.iterationMode = e.target.value;
        });
    });

    // Categories
    document.querySelectorAll('input[name="category"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                state.selectedCategories.add(e.target.value);
            } else {
                state.selectedCategories.delete(e.target.value);
            }
            updateTestSelection();
        });
    });

    // Labels
    document.querySelectorAll('input[name="label"]').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                state.selectedLabels.add(e.target.value);
            } else {
                state.selectedLabels.delete(e.target.value);
            }
            updateTestSelection();
        });
    });

    // Select all / deselect all
    elements.btnSelectAllTests.addEventListener('click', () => {
        state.testCases.forEach(t => state.selectedTests.add(t.id));
        renderTestList();
    });

    elements.btnDeselectAllTests.addEventListener('click', () => {
        state.selectedTests.clear();
        renderTestList();
    });
}

function updateTestSelection() {
    state.testCases.forEach(test => {
        const categoryMatch = state.selectedCategories.has(test.category);
        const labelMatch = state.selectedLabels.has(test.label);
        if (categoryMatch && labelMatch) {
            state.selectedTests.add(test.id);
        } else {
            state.selectedTests.delete(test.id);
        }
    });
    renderTestList();
}

function renderTestList() {
    elements.testList.innerHTML = `
        <div class="test-row header">
            <span></span>
            <span>Test Name</span>
            <span>Category</span>
            <span>Label</span>
        </div>
        ${state.testCases.map(test => `
            <div class="test-row" data-test-id="${test.id}">
                <input type="checkbox" ${state.selectedTests.has(test.id) ? 'checked' : ''}>
                <span class="test-name">${test.name}</span>
                <span class="test-category ${test.category}">${test.category}</span>
                <span class="test-label ${test.label}">${test.label}</span>
            </div>
        `).join('')}
    `;

    elements.testList.querySelectorAll('.test-row:not(.header)').forEach(row => {
        const checkbox = row.querySelector('input[type="checkbox"]');
        const testId = parseInt(row.dataset.testId);

        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                state.selectedTests.add(testId);
            } else {
                state.selectedTests.delete(testId);
            }
        });
    });
}

// ============================================================================
// Parameters
// ============================================================================

function setupParams() {
    elements.btnRandomizeParams.addEventListener('click', async () => {
        if (!state.selectedChain) {
            alert('Please select a chain first');
            return;
        }

        try {
            const params = await api.randomizeParams(state.selectedChain.chain_id);
            setParamValues(params);
            state.params = params;
        } catch (e) {
            alert(`Failed to randomize params: ${e.message}`);
        }
    });

    elements.btnValidateParams.addEventListener('click', async () => {
        const validProviders = state.providers.filter(p => p.url);
        if (validProviders.length === 0) {
            alert('No providers configured');
            return;
        }

        const params = getParamValues();
        try {
            const result = await api.validateParams(
                state.selectedChain.chain_id,
                validProviders[0].url,
                params
            );
            renderParamValidation(result);
        } catch (e) {
            alert(`Validation failed: ${e.message}`);
        }
    });

    // Update state when params change
    document.querySelectorAll('#params-form input').forEach(input => {
        input.addEventListener('change', () => {
            state.params = getParamValues();
        });
    });
}

function setParamValues(params) {
    document.getElementById('param-known-address').value = params.known_address || '';
    document.getElementById('param-archival-block').value = params.archival_block || '';
    document.getElementById('param-recent-block-offset').value = params.recent_block_offset || 100;
    document.getElementById('param-logs-token-contract').value = params.logs_token_contract || '';
    document.getElementById('param-logs-range-small').value = params.logs_range_small || 1000;
    document.getElementById('param-logs-range-large').value = params.logs_range_large || 10000;
}

function getParamValues() {
    const archivalBlock = parseInt(document.getElementById('param-archival-block').value) || 0;
    return {
        known_address: document.getElementById('param-known-address').value,
        archival_block: archivalBlock,
        recent_block_offset: parseInt(document.getElementById('param-recent-block-offset').value) || 100,
        logs_token_contract: document.getElementById('param-logs-token-contract').value,
        logs_range_small: parseInt(document.getElementById('param-logs-range-small').value) || 1000,
        logs_range_large: parseInt(document.getElementById('param-logs-range-large').value) || 10000,
        archival_logs_start_block: archivalBlock,  // Use same block as archival tests
    };
}

function renderParamValidation(result) {
    elements.paramsValidationResults.classList.remove('hidden');
    elements.paramsValidationResults.innerHTML = result.results.map(r => `
        <div class="validation-item ${r.valid ? 'valid' : 'invalid'}">
            <span>${r.field}</span>
            <span>${r.message}</span>
        </div>
    `).join('');
}

// ============================================================================
// Benchmark
// ============================================================================

function setupBenchmark() {
    elements.btnStartBenchmark.addEventListener('click', startBenchmark);
    elements.btnCancelBenchmark.addEventListener('click', cancelBenchmark);
}

function renderBenchmarkSummary() {
    const validProviders = state.providers.filter(p => p.name && p.url);
    const selectedTestsList = state.testCases.filter(t => state.selectedTests.has(t.id));

    elements.benchmarkSummary.innerHTML = `
        <div class="summary-grid">
            <div class="summary-item">
                <span class="label">Chain</span>
                <span class="value">${state.selectedChain?.chain_name || '-'}</span>
            </div>
            <div class="summary-item">
                <span class="label">Providers</span>
                <span class="value">${validProviders.length}</span>
            </div>
            <div class="summary-item">
                <span class="label">Tests</span>
                <span class="value">${state.selectedTests.size}</span>
            </div>
            <div class="summary-item">
                <span class="label">Rounds</span>
                <span class="value">${state.iterationMode} (${{'quick': 2, 'standard': 3, 'thorough': 5, 'statistical': 10}[state.iterationMode]} rounds)</span>
            </div>
            <div class="summary-item">
                <span class="label">Categories</span>
                <span class="value">${Array.from(state.selectedCategories).join(', ')}</span>
            </div>
            <div class="summary-item">
                <span class="label">Labels</span>
                <span class="value">${Array.from(state.selectedLabels).join(', ')}</span>
            </div>
        </div>
        <h4 style="margin-top: 1rem; margin-bottom: 0.5rem;">Providers:</h4>
        <ul style="margin-left: 1.5rem;">
            ${validProviders.map(p => `<li>${p.name} ${p.region ? `(${p.region})` : ''}</li>`).join('')}
        </ul>
    `;
}

async function startBenchmark() {
    const validProviders = state.providers.filter(p => p.name && p.url);
    const params = getParamValues();
    const timeoutSeconds = parseInt(document.getElementById('param-timeout').value) || 30;

    const jobData = {
        chain_id: state.selectedChain.chain_id,
        providers: validProviders.map(p => ({
            name: p.name,
            url: p.url,
            region: p.region || null,
        })),
        config: {
            iteration_mode: state.iterationMode,
            timeout_seconds: timeoutSeconds,
            categories: Array.from(state.selectedCategories),
            labels: Array.from(state.selectedLabels),
            enabled_test_ids: Array.from(state.selectedTests),
            test_params: params,
            load_concurrency: {
                simple: 50,
                medium: 50,
                complex: 25,
            },
        },
    };

    try {
        const job = await api.createJob(jobData);
        state.currentJobId = job.id;

        elements.benchmarkControls.classList.add('hidden');
        elements.benchmarkProgress.classList.remove('hidden');
        elements.progressDetails.innerHTML = '';
        elements.progressBar.style.width = '0%';
        elements.progressStatus.textContent = 'Starting...';

        // Subscribe to progress
        state.eventSource = api.subscribeToProgress(job.id, handleProgressEvent, handleProgressError);
    } catch (e) {
        alert(`Failed to start benchmark: ${e.message}`);
    }
}

function handleProgressEvent(event) {
    const log = document.createElement('div');
    log.className = 'progress-log';

    switch (event.event) {
        case 'job_started':
            state.totalTests = event.data.total_tests || 0;
            state.totalRounds = event.data.rounds || 3;
            log.textContent = `Starting benchmark: ${event.data.total_sequential || 0} sequential tests × ${event.data.rounds} rounds, ${event.data.total_load || 0} load tests`;
            break;

        case 'round_started':
            log.textContent = `Round ${event.data.round}/${event.data.total_rounds} (${event.data.iteration_type})`;
            log.style.fontWeight = 'bold';
            log.style.color = event.data.iteration_type === 'cold' ? '#f59e0b' : '#00ba7c';
            break;

        case 'round_complete':
            if (event.data.waiting_ms > 0) {
                log.textContent = `Round ${event.data.round} complete. Waiting ${event.data.waiting_ms}ms for cache propagation...`;
                log.style.color = 'var(--color-text-muted)';
            }
            break;

        case 'sequential_complete':
            log.textContent = `Sequential tests complete: ${event.data.total_rounds} rounds`;
            log.style.color = '#00ba7c';
            break;

        case 'iteration_complete':
            const iterProgress = event.data.progress || 0;
            elements.progressBar.style.width = `${iterProgress * 100}%`;
            elements.progressStatus.textContent = `${Math.round(iterProgress * 100)}% - Round ${event.data.round}/${event.data.total_rounds} (${event.data.iteration_type})`;
            log.textContent = `  ${event.data.provider_name}: ${event.data.test_name} - ${formatMs(event.data.response_time_ms)} ${event.data.success ? '✓' : '✗'}`;
            break;

        case 'load_test_start':
            elements.progressStatus.textContent = `${elements.progressStatus.textContent.split(' -')[0]} - Load: ${event.data.test_name}`;
            log.textContent = `Load test: ${event.data.test_name} (${event.data.concurrency} concurrent requests)`;
            break;

        case 'load_test_complete':
            const loadProgress = event.data.progress || 0;
            elements.progressBar.style.width = `${loadProgress * 100}%`;
            elements.progressStatus.textContent = `${Math.round(loadProgress * 100)}% complete - ${event.data.test_name}`;
            log.textContent = `Load test complete: ${event.data.test_name} - ${event.data.throughput_rps?.toFixed(1) || event.data.requests_per_second?.toFixed(1) || '?'} req/s, avg ${formatMs(event.data.avg_ms)}`;
            log.style.color = '#00ba7c';
            break;

        case 'job_complete':
            elements.progressBar.style.width = '100%';
            elements.progressStatus.textContent = 'Complete!';
            log.textContent = `Benchmark complete in ${formatDuration(event.data.duration_seconds)}`;
            log.style.fontWeight = 'bold';
            log.style.color = '#00ba7c';

            // Navigate to results after a short delay
            setTimeout(() => {
                viewJobResults(state.currentJobId);
            }, 1000);
            break;

        case 'error':
            log.textContent = `Error: ${event.data.message}`;
            log.style.color = '#f4212e';
            break;

        default:
            return;
    }

    elements.progressDetails.appendChild(log);
    elements.progressDetails.scrollTop = elements.progressDetails.scrollHeight;
}

function handleProgressError(error) {
    elements.progressStatus.textContent = 'Connection lost';
    console.error('SSE error:', error);
}

async function cancelBenchmark() {
    if (!state.currentJobId) return;

    try {
        await api.cancelJob(state.currentJobId);
        if (state.eventSource) {
            state.eventSource.close();
        }
        elements.progressStatus.textContent = 'Cancelled';
    } catch (e) {
        alert(`Failed to cancel: ${e.message}`);
    }
}

// ============================================================================
// History
// ============================================================================

function setupHistory() {
    elements.historyChainFilter.addEventListener('change', loadHistory);

    // Import button triggers hidden file input
    elements.btnImportResults.addEventListener('click', () => {
        elements.importFileInput.click();
    });

    // Handle file selection
    elements.importFileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        try {
            elements.btnImportResults.disabled = true;
            elements.btnImportResults.textContent = 'Importing...';

            const result = await api.importResults(file);

            // Reset file input
            elements.importFileInput.value = '';

            // Show success and navigate to results
            alert(`Imported: ${result.message}\nChain: ${result.chain}\nProviders: ${result.providers.join(', ')}`);

            // Reload history and view the imported results
            await loadHistory();
            viewJobResults(result.job_id);
        } catch (err) {
            alert(`Import failed: ${err.message}`);
        } finally {
            elements.btnImportResults.disabled = false;
            elements.btnImportResults.textContent = 'Import Results';
        }
    });
}

function updateHistoryChainFilter() {
    elements.historyChainFilter.innerHTML = `
        <option value="">All Chains</option>
        ${state.chains.map(c => `<option value="${c.chain_id}">${c.chain_name}</option>`).join('')}
    `;
}

async function loadHistory() {
    const chainId = elements.historyChainFilter.value || null;

    try {
        const jobs = await api.listJobs(chainId);
        renderHistory(jobs);
    } catch (e) {
        console.error('Failed to load history:', e);
    }
}

function renderHistory(jobs) {
    if (jobs.length === 0) {
        elements.historyList.innerHTML = '<p style="color: var(--color-text-muted);">No benchmarks yet</p>';
        return;
    }

    elements.historyList.innerHTML = jobs.map(job => `
        <div class="history-item" data-job-id="${job.id}">
            <div class="history-info">
                <h3>${job.chain_name}</h3>
                <div class="history-meta">
                    <span>${formatDate(job.created_at)}</span>
                    <span>${job.config?.iteration_mode || 'standard'} mode</span>
                </div>
            </div>
            <span class="history-status ${job.status}">${job.status}</span>
        </div>
    `).join('');

    elements.historyList.querySelectorAll('.history-item').forEach(item => {
        item.addEventListener('click', () => {
            const jobId = item.dataset.jobId;
            viewJobResults(jobId);
        });
    });
}

// ============================================================================
// Results
// ============================================================================

function setupResults() {
    elements.resultsTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            elements.resultsTabs.forEach(t => t.classList.toggle('active', t === tab));
            renderResultsTab(tabName);
        });
    });

    elements.btnExportJson.addEventListener('click', () => {
        if (state.currentJobId) {
            window.location.href = api.getExportJsonUrl(state.currentJobId);
        }
    });

    elements.btnExportCsv.addEventListener('click', () => {
        if (state.currentJobId) {
            window.location.href = api.getExportCsvUrl(state.currentJobId);
        }
    });

    elements.btnBackToHistory.addEventListener('click', () => {
        navigateToPage('history');
    });
}

async function viewJobResults(jobId) {
    state.currentJobId = jobId;
    navigateToPage('results');

    try {
        const results = await api.getJobResults(jobId);
        state.currentResults = results;
        renderResultsTab('overview');
    } catch (e) {
        console.error('Failed to load results:', e);
        elements.resultsContent.innerHTML = `<p style="color: var(--color-danger);">Failed to load results: ${e.message}</p>`;
    }
}

function renderResultsTab(tab) {
    const results = state.currentResults;
    if (!results) return;

    switch (tab) {
        case 'overview':
            renderOverviewTab(results);
            break;
        case 'sequential':
            renderSequentialTab(results);
            break;
        case 'load':
            renderLoadTab(results);
            break;
        case 'comparison':
            renderComparisonTab(results);
            break;
    }
}

function renderOverviewTab(results) {
    const aggregated = results.aggregated || [];

    // Group by provider
    const byProvider = {};
    aggregated.forEach(r => {
        if (!byProvider[r.provider_name]) {
            byProvider[r.provider_name] = [];
        }
        byProvider[r.provider_name].push(r);
    });

    // Calculate error summary per provider
    const errorSummary = {};
    Object.keys(byProvider).forEach(provider => {
        const providerResults = byProvider[provider];
        errorSummary[provider] = {
            totalTests: providerResults.length,
            totalErrors: providerResults.reduce((sum, r) => sum + (r.error_count || 0), 0),
            providerErrors: providerResults.reduce((sum, r) => sum + (r.provider_errors || 0), 0),
            paramErrors: providerResults.reduce((sum, r) => sum + (r.param_errors || 0), 0),
        };
    });

    elements.resultsContent.innerHTML = `
        <div class="error-summary">
            <h3>Error Analysis</h3>
            <div class="error-summary-grid">
                ${Object.keys(errorSummary).map(provider => {
                    const summary = errorSummary[provider];
                    const hasErrors = summary.totalErrors > 0;
                    return `
                        <div class="error-summary-card ${hasErrors ? 'has-errors' : 'no-errors'}">
                            <h4>${provider}</h4>
                            ${hasErrors ? `
                                <div class="error-breakdown">
                                    <div class="error-stat">
                                        <span class="error-label">Provider Errors:</span>
                                        <span class="error-value provider-error">${summary.providerErrors}</span>
                                    </div>
                                    <div class="error-stat">
                                        <span class="error-label">Param Errors:</span>
                                        <span class="error-value param-error">${summary.paramErrors}</span>
                                    </div>
                                    <div class="error-hint">
                                        ${summary.providerErrors > 0 ? 'Provider errors: timeouts, rate limits, connection issues' : ''}
                                        ${summary.paramErrors > 0 ? 'Param errors: check your test parameters' : ''}
                                    </div>
                                </div>
                            ` : '<span class="no-errors-badge">No errors</span>'}
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
        <div class="chart-container">
            <canvas id="overview-chart"></canvas>
        </div>
        <table class="results-table">
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Test</th>
                    <th>Category</th>
                    <th class="numeric">Cold (ms)</th>
                    <th class="numeric">Warm (ms)</th>
                    <th class="numeric">Cache Speedup</th>
                    <th class="numeric">Success Rate</th>
                    <th class="numeric">Errors</th>
                </tr>
            </thead>
            <tbody>
                ${aggregated.map(r => {
                    const errorTypes = r.error_breakdown ? Object.entries(r.error_breakdown).map(([k, v]) => `${k}: ${v}`).join(', ') : '';
                    const errorMsgs = r.error_messages && r.error_messages.length > 0 ? r.error_messages.join('\n') : '';
                    const fullErrorInfo = errorTypes + (errorMsgs ? '\n\nMessages:\n' + errorMsgs : '');
                    return `
                        <tr>
                            <td>${r.provider_name}</td>
                            <td>${r.test_name}</td>
                            <td><span class="test-category ${r.category}">${r.category}</span></td>
                            <td class="numeric">${formatMs(r.cold_ms)}</td>
                            <td class="numeric">${formatMs(r.warm_ms)}</td>
                            <td class="numeric">${r.cache_speedup ? r.cache_speedup.toFixed(2) + 'x' : '-'}</td>
                            <td class="numeric">${formatPercent(r.success_rate)}</td>
                            <td class="numeric ${r.error_count > 0 ? 'has-error' : ''}" title="${fullErrorInfo}">${r.error_count || 0}${r.error_messages && r.error_messages.length > 0 ? ' ⓘ' : ''}</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;

    // Create chart
    const ctx = document.getElementById('overview-chart').getContext('2d');
    const providers = Object.keys(byProvider);
    const tests = [...new Set(aggregated.map(r => r.test_name))];

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: tests,
            datasets: providers.map((provider, i) => ({
                label: provider,
                data: tests.map(test => {
                    const result = byProvider[provider].find(r => r.test_name === test);
                    return result?.warm_ms || null;
                }),
                backgroundColor: `hsla(${i * 360 / providers.length}, 70%, 50%, 0.7)`,
            })),
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#e7e9ea' },
                },
                title: {
                    display: true,
                    text: 'Warm Latency by Test (ms)',
                    color: '#e7e9ea',
                },
            },
            scales: {
                x: {
                    ticks: { color: '#8b98a5' },
                    grid: { color: '#2f3336' },
                },
                y: {
                    ticks: { color: '#8b98a5' },
                    grid: { color: '#2f3336' },
                },
            },
        },
    });
}

function renderSequentialTab(results) {
    const sequential = results.sequential || [];

    elements.resultsContent.innerHTML = `
        <table class="results-table">
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Test</th>
                    <th>Round</th>
                    <th class="numeric">Latency (ms)</th>
                    <th>Success</th>
                    <th>Error</th>
                </tr>
            </thead>
            <tbody>
                ${sequential.slice(0, 100).map(r => `
                    <tr>
                        <td>${r.provider_name || '-'}</td>
                        <td>${r.test_name || '-'}</td>
                        <td>${r.iteration_type || '-'}</td>
                        <td class="numeric">${formatMs(r.latency_ms)}</td>
                        <td>${r.success ? '✓' : '✗'}</td>
                        <td>${r.error_message || '-'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        ${sequential.length > 100 ? `<p style="color: var(--color-text-muted); margin-top: 1rem;">Showing first 100 of ${sequential.length} results</p>` : ''}
    `;
}

function renderLoadTab(results) {
    const loadTests = results.load_tests || [];

    elements.resultsContent.innerHTML = `
        <div class="chart-container">
            <canvas id="load-chart"></canvas>
        </div>
        <table class="results-table">
            <thead>
                <tr>
                    <th>Provider</th>
                    <th>Test</th>
                    <th class="numeric">Concurrency</th>
                    <th class="numeric">Req/s</th>
                    <th class="numeric">P50 (ms)</th>
                    <th class="numeric">P95 (ms)</th>
                    <th class="numeric">P99 (ms)</th>
                    <th class="numeric">Success Rate</th>
                </tr>
            </thead>
            <tbody>
                ${loadTests.map(r => `
                    <tr>
                        <td>${r.provider_name || '-'}</td>
                        <td>${r.test_name || '-'}</td>
                        <td class="numeric">${r.concurrency || '-'}</td>
                        <td class="numeric">${r.requests_per_second?.toFixed(1) || '-'}</td>
                        <td class="numeric">${formatMs(r.p50_ms)}</td>
                        <td class="numeric">${formatMs(r.p95_ms)}</td>
                        <td class="numeric">${formatMs(r.p99_ms)}</td>
                        <td class="numeric">${formatPercent(r.success_rate)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    if (loadTests.length > 0) {
        const ctx = document.getElementById('load-chart').getContext('2d');
        const providers = [...new Set(loadTests.map(r => r.provider_name))];

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: providers,
                datasets: [{
                    label: 'Requests/Second',
                    data: providers.map(p => {
                        const providerResults = loadTests.filter(r => r.provider_name === p);
                        return providerResults.reduce((sum, r) => sum + (r.requests_per_second || 0), 0) / providerResults.length;
                    }),
                    backgroundColor: 'rgba(29, 155, 240, 0.7)',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: {
                        display: true,
                        text: 'Average Requests per Second by Provider',
                        color: '#e7e9ea',
                    },
                },
                scales: {
                    x: { ticks: { color: '#8b98a5' }, grid: { color: '#2f3336' } },
                    y: { ticks: { color: '#8b98a5' }, grid: { color: '#2f3336' } },
                },
            },
        });
    }
}

function renderComparisonTab(results) {
    const aggregated = results.aggregated || [];
    const providers = [...new Set(aggregated.map(r => r.provider_name))];
    const tests = [...new Set(aggregated.map(r => r.test_name))];

    // Create comparison matrix
    const matrix = {};
    tests.forEach(test => {
        matrix[test] = {};
        providers.forEach(provider => {
            const result = aggregated.find(r => r.test_name === test && r.provider_name === provider);
            matrix[test][provider] = result?.warm_ms || null;
        });
    });

    elements.resultsContent.innerHTML = `
        <table class="results-table">
            <thead>
                <tr>
                    <th>Test</th>
                    ${providers.map(p => `<th class="numeric">${p}</th>`).join('')}
                    <th class="numeric">Winner</th>
                </tr>
            </thead>
            <tbody>
                ${tests.map(test => {
                    const values = providers.map(p => matrix[test][p]).filter(v => v !== null);
                    const min = Math.min(...values);
                    const winner = providers.find(p => matrix[test][p] === min);

                    return `
                        <tr>
                            <td>${test}</td>
                            ${providers.map(p => {
                                const value = matrix[test][p];
                                const isWinner = value === min && value !== null;
                                return `<td class="numeric" style="${isWinner ? 'color: #00ba7c; font-weight: bold;' : ''}">${formatMs(value)}</td>`;
                            }).join('')}
                            <td class="numeric" style="color: #00ba7c;">${winner || '-'}</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
    `;
}

// ============================================================================
// Chains Page
// ============================================================================

function setupChainsPage() {
    elements.btnAddChain.addEventListener('click', () => {
        openChainModal(null);
    });

    elements.btnSaveChain.addEventListener('click', saveChain);

    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            elements.chainModal.classList.add('hidden');
        });
    });
}

function renderChainsPage() {
    elements.chainsList.innerHTML = state.chains.map(chain => `
        <div class="chain-config-card" data-chain-id="${chain.chain_id}">
            <h3>
                ${chain.chain_name}
                ${chain.is_preset ? '<span class="chain-preset-badge">Preset</span>' : ''}
            </h3>
            <div class="chain-meta">
                <span>Chain ID: ${chain.chain_id}</span>
                <span>Archival: ${chain.archival_block_range?.[0]} - ${chain.archival_block_range?.[1]}</span>
            </div>
            <div class="chain-actions">
                <button class="btn btn-small btn-secondary btn-edit-chain">Edit</button>
                ${!chain.is_preset ? '<button class="btn btn-small btn-danger btn-delete-chain">Delete</button>' : ''}
            </div>
        </div>
    `).join('');

    elements.chainsList.querySelectorAll('.chain-config-card').forEach(card => {
        const chainId = parseInt(card.dataset.chainId);
        const chain = state.chains.find(c => c.chain_id === chainId);

        card.querySelector('.btn-edit-chain').addEventListener('click', () => {
            openChainModal(chain);
        });

        const deleteBtn = card.querySelector('.btn-delete-chain');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async () => {
                if (confirm(`Delete ${chain.chain_name}?`)) {
                    await api.deleteChain(chainId);
                    await loadChains();
                    renderChainsPage();
                }
            });
        }
    });
}

function openChainModal(chain) {
    const isEdit = !!chain;
    document.getElementById('chain-modal-title').textContent = isEdit ? 'Edit Chain' : 'Add Custom Chain';

    document.getElementById('chain-id').value = chain?.chain_id || '';
    document.getElementById('chain-name').value = chain?.chain_name || '';
    document.getElementById('chain-archival-start').value = chain?.archival_block_range?.[0] || '';
    document.getElementById('chain-archival-end').value = chain?.archival_block_range?.[1] || '';

    document.getElementById('chain-id').disabled = isEdit;

    elements.chainModal.classList.remove('hidden');
    elements.chainModal.dataset.editChainId = chain?.chain_id || '';
}

async function saveChain() {
    const chainId = parseInt(document.getElementById('chain-id').value);
    const chainData = {
        chain_id: chainId,
        chain_name: document.getElementById('chain-name').value,
        archival_block_range: [
            parseInt(document.getElementById('chain-archival-start').value),
            parseInt(document.getElementById('chain-archival-end').value),
        ],
        test_addresses: [],
        token_contracts: [],
        transaction_pool: [],
    };

    try {
        const editChainId = elements.chainModal.dataset.editChainId;
        if (editChainId) {
            await api.updateChain(parseInt(editChainId), chainData);
        } else {
            await api.createChain(chainData);
        }

        elements.chainModal.classList.add('hidden');
        await loadChains();
        renderChainsPage();
    } catch (e) {
        alert(`Failed to save chain: ${e.message}`);
    }
}

// ============================================================================
// Start
// ============================================================================

init();
