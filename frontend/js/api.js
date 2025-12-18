/**
 * API Client for RPC Benchmarker
 */

const API_BASE = '/api';

class ApiClient {
    async request(method, endpoint, data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${API_BASE}${endpoint}`, options);

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'API request failed');
        }

        return response.json();
    }

    // Chain endpoints
    async listChains() {
        return this.request('GET', '/chains');
    }

    async getChain(chainId) {
        return this.request('GET', `/chains/${chainId}`);
    }

    async createChain(chainData) {
        return this.request('POST', '/chains', chainData);
    }

    async updateChain(chainId, updates) {
        return this.request('PUT', `/chains/${chainId}`, updates);
    }

    async deleteChain(chainId) {
        return this.request('DELETE', `/chains/${chainId}`);
    }

    // Provider validation
    async validateProviders(urls, expectedChainId) {
        return this.request('POST', '/providers/validate', {
            urls,
            expected_chain_id: expectedChainId,
        });
    }

    // Test cases
    async listTestCases() {
        return this.request('GET', '/test-cases');
    }

    // Parameters
    async randomizeParams(chainId) {
        return this.request('POST', `/params/randomize?chain_id=${chainId}`);
    }

    async validateParams(chainId, providerUrl, params) {
        return this.request('POST', `/params/validate?chain_id=${chainId}&provider_url=${encodeURIComponent(providerUrl)}`, params);
    }

    // Jobs
    async createJob(jobData) {
        return this.request('POST', '/jobs', jobData);
    }

    async listJobs(chainId = null, limit = 100) {
        let endpoint = `/jobs?limit=${limit}`;
        if (chainId) {
            endpoint += `&chain_id=${chainId}`;
        }
        return this.request('GET', endpoint);
    }

    async getJob(jobId) {
        return this.request('GET', `/jobs/${jobId}`);
    }

    async getJobResults(jobId) {
        return this.request('GET', `/jobs/${jobId}/results`);
    }

    async deleteJob(jobId) {
        return this.request('DELETE', `/jobs/${jobId}`);
    }

    async cancelJob(jobId) {
        return this.request('POST', `/jobs/${jobId}/cancel`);
    }

    // Progress (SSE)
    subscribeToProgress(jobId, onEvent, onError) {
        const eventSource = new EventSource(`${API_BASE}/jobs/${jobId}/progress`);

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                onEvent({ event: 'message', data });
            } catch (e) {
                console.error('Failed to parse SSE message:', e);
            }
        };

        // Job lifecycle events
        eventSource.addEventListener('job_started', (event) => {
            onEvent({ event: 'job_started', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('provider_started', (event) => {
            onEvent({ event: 'provider_started', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('provider_complete', (event) => {
            onEvent({ event: 'provider_complete', data: JSON.parse(event.data) });
        });

        // Test events (backend uses "test_started" not "test_start")
        eventSource.addEventListener('test_started', (event) => {
            onEvent({ event: 'test_start', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('test_complete', (event) => {
            onEvent({ event: 'test_complete', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('iteration_complete', (event) => {
            onEvent({ event: 'iteration_complete', data: JSON.parse(event.data) });
        });

        // Round events (for round-based testing)
        eventSource.addEventListener('round_started', (event) => {
            onEvent({ event: 'round_started', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('round_complete', (event) => {
            onEvent({ event: 'round_complete', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('sequential_complete', (event) => {
            onEvent({ event: 'sequential_complete', data: JSON.parse(event.data) });
        });

        // Load test events (backend uses "load_test_started" not "load_test_start")
        eventSource.addEventListener('load_test_started', (event) => {
            onEvent({ event: 'load_test_start', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('load_test_complete', (event) => {
            onEvent({ event: 'load_test_complete', data: JSON.parse(event.data) });
        });

        eventSource.addEventListener('job_complete', (event) => {
            onEvent({ event: 'job_complete', data: JSON.parse(event.data) });
            eventSource.close();
        });

        eventSource.addEventListener('error', (event) => {
            if (event.data) {
                onEvent({ event: 'error', data: JSON.parse(event.data) });
            }
        });

        eventSource.onerror = (error) => {
            if (onError) {
                onError(error);
            }
            eventSource.close();
        };

        return eventSource;
    }

    // Export URLs
    getExportJsonUrl(jobId) {
        return `${API_BASE}/export/${jobId}/json`;
    }

    getExportCsvUrl(jobId) {
        return `${API_BASE}/export/${jobId}/csv`;
    }

    // Import
    async importResults(file) {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE}/import`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || 'Import failed');
        }

        return response.json();
    }
}

export const api = new ApiClient();
