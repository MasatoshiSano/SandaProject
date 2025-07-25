// 共通JavaScript機能
(function() {
    'use strict';

    // 現在時刻の表示
    function updateCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleString('ja-JP', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        const timeElement = document.getElementById('current-time');
        if (timeElement) {
            timeElement.textContent = timeString;
        }
    }

    // WebSocket接続管理
    class WebSocketManager {
        constructor(url) {
            this.url = url;
            this.socket = null;
            this.reconnectAttempts = 0;
            this.maxReconnectAttempts = 5;
            this.reconnectInterval = 1000;
            this.callbacks = {};
        }

        connect() {
            try {
                this.socket = new WebSocket(this.url);
                this.setupEventHandlers();
            } catch (error) {
                console.error('WebSocket connection error:', error);
                this.handleReconnect();
            }
        }

        setupEventHandlers() {
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.onOpen();
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };

            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                this.handleReconnect();
            };

            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }

        handleMessage(data) {
            const callback = this.callbacks[data.type];
            if (callback) {
                callback(data);
            }
        }

        handleReconnect() {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                
                setTimeout(() => {
                    this.connect();
                }, this.reconnectInterval * this.reconnectAttempts);
            } else {
                console.error('Max reconnection attempts reached');
            }
        }

        send(data) {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.socket.send(JSON.stringify(data));
            }
        }

        on(type, callback) {
            this.callbacks[type] = callback;
        }

        onOpen() {
            // Override in subclasses
        }

        disconnect() {
            if (this.socket) {
                this.socket.close();
            }
        }
    }

    // チャート管理
    class ChartManager {
        constructor() {
            this.charts = {};
        }

        createChart(canvasId, config) {
            const ctx = document.getElementById(canvasId);
            if (!ctx) {
                console.error(`Canvas element with id '${canvasId}' not found`);
                return null;
            }

            // 既存のチャートを破棄
            if (this.charts[canvasId]) {
                this.charts[canvasId].destroy();
            }

            // 新しいチャートを作成
            this.charts[canvasId] = new Chart(ctx, config);
            return this.charts[canvasId];
        }

        updateChart(canvasId, data) {
            const chart = this.charts[canvasId];
            if (chart) {
                chart.data = data;
                chart.update();
            }
        }

        destroyChart(canvasId) {
            const chart = this.charts[canvasId];
            if (chart) {
                chart.destroy();
                delete this.charts[canvasId];
            }
        }

        destroyAllCharts() {
            Object.keys(this.charts).forEach(canvasId => {
                this.destroyChart(canvasId);
            });
        }
    }

    // ユーティリティ関数
    const Utils = {
        // 数値のフォーマット
        formatNumber: function(num, decimals = 0) {
            return new Intl.NumberFormat('ja-JP', {
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            }).format(num);
        },

        // パーセンテージのフォーマット
        formatPercentage: function(value, decimals = 1) {
            return this.formatNumber(value, decimals) + '%';
        },

        // 日付のフォーマット
        formatDate: function(date, format = 'YYYY-MM-DD') {
            const d = new Date(date);
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            
            return format
                .replace('YYYY', year)
                .replace('MM', month)
                .replace('DD', day);
        },

        // 時間のフォーマット
        formatTime: function(date, format = 'HH:mm') {
            const d = new Date(date);
            const hours = String(d.getHours()).padStart(2, '0');
            const minutes = String(d.getMinutes()).padStart(2, '0');
            const seconds = String(d.getSeconds()).padStart(2, '0');
            
            return format
                .replace('HH', hours)
                .replace('mm', minutes)
                .replace('ss', seconds);
        },

        // 達成率に基づく色の取得
        getAchievementColor: function(rate) {
            if (rate >= 100) return 'success';
            if (rate >= 80) return 'warning';
            return 'danger';
        },

        // ローディング表示
        showLoading: function(element) {
            if (typeof element === 'string') {
                element = document.getElementById(element);
            }
            if (element) {
                element.innerHTML = '<div class="loading"></div>';
            }
        },

        // エラー表示
        showError: function(element, message) {
            if (typeof element === 'string') {
                element = document.getElementById(element);
            }
            if (element) {
                element.innerHTML = `<div class="alert alert-danger">${message}</div>`;
            }
        },

        // CSRF トークンの取得
        getCSRFToken: function() {
            return document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        },

        // Ajax リクエスト
        ajax: function(url, options = {}) {
            const defaults = {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            };

            const config = Object.assign(defaults, options);
            
            return fetch(url, config)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                });
        }
    };

    // グローバルオブジェクトとして公開
    window.WebSocketManager = WebSocketManager;
    window.ChartManager = ChartManager;
    window.Utils = Utils;

    // 初期化
    document.addEventListener('DOMContentLoaded', function() {
        // 時計の更新を開始
        updateCurrentTime();
        setInterval(updateCurrentTime, 1000);

        // フォームの改善
        setupFormEnhancements();

        // テーブルの改善
        setupTableEnhancements();
    });

    // フォーム機能の改善
    function setupFormEnhancements() {
        // 数値入力フィールドの改善
        document.querySelectorAll('input[type="number"]').forEach(input => {
            input.addEventListener('wheel', function(e) {
                e.preventDefault();
            });
        });

        // 日付入力フィールドの改善
        document.querySelectorAll('input[type="date"]').forEach(input => {
            if (!input.value) {
                input.value = new Date().toISOString().split('T')[0];
            }
        });

        // フォーム送信時のローディング表示
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', function() {
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<span class="loading me-2"></span>送信中...';
                }
            });
        });
    }

    // テーブル機能の改善
    function setupTableEnhancements() {
        // テーブルの行クリック機能
        document.querySelectorAll('table tbody tr[data-href]').forEach(row => {
            row.style.cursor = 'pointer';
            row.addEventListener('click', function() {
                window.location.href = this.dataset.href;
            });
        });

        // テーブルのソート機能（簡易版）
        document.querySelectorAll('th[data-sort]').forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', function() {
                // ソート機能の実装（必要に応じて）
                console.log('Sort by:', this.dataset.sort);
            });
        });
    }

})(); 