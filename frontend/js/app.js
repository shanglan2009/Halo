/**
 * Halo - 中国股市投资分析系统 前端应用
 * 
 * 功能：
 * - 仪表盘（指数概览、宏观分析、快速推荐）
 * - 推荐列表（排序、筛选、详情）
 * - 股票池展示
 * - 定时自动刷新
 */

// ========== 配置 ==========
const API_BASE = '/api';
const REFRESH_INTERVAL = 5 * 60 * 1000; // 每5分钟自动刷新
const STOCK_POOL_API = `${API_BASE}/stocks/quality-pool`;
const RECOMMEND_API = `${API_BASE}/stocks/recommend`;
const INDEX_API = `${API_BASE}/index`;

// ========== 安全工具 ==========
/** HTML转义，防止XSS注入 */
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

// ========== 状态管理 ==========
const state = {
    currentTab: 'dashboard',
    recommendations: [],
    stockPool: [],
    indexData: {},
    isOnline: false,
    lastRefresh: null,
};

// ========== DOM引用 ==========
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initControls();
    initEventDelegation();
    loadAllData();
    startAutoRefresh();
});

// ========== 事件委托 (防XSS) ==========
function initEventDelegation() {
    document.addEventListener('click', (e) => {
        // 快速推荐卡片点击
        const recItem = e.target.closest('.quick-rec-item');
        if (recItem && recItem.dataset.symbol) {
            showStockDetail(recItem.dataset.symbol);
            return;
        }
        // 详情按钮点击
        const detailBtn = e.target.closest('.detail-btn');
        if (detailBtn && detailBtn.dataset.symbol) {
            showStockDetail(detailBtn.dataset.symbol);
            return;
        }
    });
}

// ========== 导航 ==========
function initNavigation() {
    $$('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tab = link.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tab) {
    state.currentTab = tab;
    
    $$('.nav-link').forEach(l => l.classList.remove('active'));
    $(`.nav-link[data-tab="${tab}"]`)?.classList.add('active');
    
    $$('.tab-content').forEach(c => c.classList.remove('active'));
    $(`#tab-${tab}`)?.classList.add('active');
    
    // 切换时加载对应数据
    if (tab === 'recommendations') loadRecommendations();
    if (tab === 'stock-pool') loadStockPool();
    if (tab === 'dashboard') loadDashboard();
}

// ========== 控件 ==========
function initControls() {
    $('#refresh-btn')?.addEventListener('click', () => {
        loadAllData(true);
    });
    
    $('#sector-filter')?.addEventListener('change', () => {
        loadRecommendations();
    });
}

// ========== 数据加载 ==========
async function loadAllData(forceRefresh = false) {
    updateStatus(false, '加载中...');
    
    await Promise.all([
        loadIndexData(),
        loadDashboard(),
        loadStockPool(),
    ]);
    
    updateStatus(true, `已连接 · ${formatTime(new Date())}`);
    state.lastRefresh = new Date();
}

async function loadIndexData() {
    try {
        const [shResp, szResp] = await Promise.all([
            fetch(`${INDEX_API}?index_code=sh000001`),
            fetch(`${INDEX_API}?index_code=sz399001`),
        ]);
        
        const shData = await shResp.json();
        const szData = await szResp.json();
        
        if (shData.success) updateIndexCard('sh', shData.data);
        if (szData.success) updateIndexCard('sz', szData.data);
        
        state.indexData = { sh: shData.data, sz: szData.data };
    } catch (err) {
        console.error('加载指数数据失败:', err);
    }
}

function updateIndexCard(prefix, data) {
    if (!data || !data.latest) return;
    
    const latest = data.latest;
    const returns = data.returns || {};
    
    // 价格
    const priceEl = $(`#${prefix}-price`);
    if (priceEl) priceEl.textContent = formatNumber(latest.close);
    
    // 涨跌幅（用1m returns近似当日涨跌）
    const change = returns['1m'] || 0;
    const changeEl = $(`#${prefix}-change`);
    if (changeEl) {
        const sign = change >= 0 ? '+' : '';
        changeEl.textContent = `${sign}${change.toFixed(2)}%`;
        changeEl.className = `index-change ${change >= 0 ? 'up' : 'down'}`;
    }
    
    // 各周期收益
    ['1m', '3m', '1y'].forEach(period => {
        const el = $(`#${prefix}-${period}`);
        if (el && returns[period] !== undefined) {
            const val = returns[period];
            const sign = val >= 0 ? '+' : '';
            el.textContent = `${sign}${val.toFixed(2)}%`;
            el.style.color = val >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
        }
    });
}

async function loadDashboard() {
    if (state.currentTab !== 'dashboard') return;
    
    const container = $('#quick-recommendations');
    if (!container) return;
    
    try {
        const resp = await fetch(`${RECOMMEND_API}?limit=5&refresh=false`);
        const json = await resp.json();
        
        if (json.success && json.data.recommendations) {
            state.recommendations = json.data.recommendations;
            renderQuickRecommendations(json.data.recommendations);
            $('#rec-count') && ($('#rec-count').textContent = `${json.data.recommendations.length} 只`);
        } else {
            container.innerHTML = '<div class="loading">暂无推荐数据</div>';
        }
    } catch (err) {
        container.innerHTML = '<div class="loading">数据加载失败，请稍后重试</div>';
        console.error('加载推荐数据失败:', err);
    }
}

function renderQuickRecommendations(recs) {
    const container = $('#quick-recommendations');
    if (!container) return;
    
    if (!recs || recs.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h3>暂无符合条件的推荐</h3>
                <p>当前市场可能没有同时满足选股条件+买入时机的标的。<br>宁缺毋滥，请耐心等待更好的机会。</p>
            </div>`;
        return;
    }
    
    container.innerHTML = recs.map((rec, i) => {
        const scoreClass = rec.final_score >= 75 ? 'score-high' : 
                          rec.final_score >= 60 ? 'score-mid' : 'score-low';
        const badgeClass = rec.is_recommended ? 'badge-strong' : 
                          rec.final_score >= 60 ? 'badge-watch' : 'badge-wait';
        const sym = escapeHtml(rec.symbol);
        const name = escapeHtml(rec.name);
        const recText = escapeHtml(rec.recommendation);
        
        return `
            <div class="quick-rec-item" data-symbol="${sym}" role="button" tabindex="0">
                <div class="quick-rec-left">
                    <span class="quick-rec-rank">#${i + 1}</span>
                    <div>
                        <div class="quick-rec-name">${name}</div>
                        <div class="quick-rec-sector">${sym}</div>
                    </div>
                </div>
                <div class="quick-rec-right">
                    <div class="quick-rec-score ${scoreClass}">${rec.final_score.toFixed(1)}</div>
                    <div class="quick-rec-badge ${badgeClass}">${recText}</div>
                </div>
            </div>`;
    }).join('');
}

async function loadRecommendations() {
    if (state.currentTab !== 'recommendations') return;
    
    const tbody = $('#recommendations-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">加载中...</td></tr>';
    
    const sector = $('#sector-filter')?.value || '';
    
    try {
        const params = new URLSearchParams({ limit: '30', refresh: 'true' });
        if (sector) params.set('sector', sector);
        
        const resp = await fetch(`${RECOMMEND_API}?${params}`);
        const json = await resp.json();
        
        if (json.success && json.data.recommendations) {
            state.recommendations = json.data.recommendations;
            renderRecommendationsTable(json.data.recommendations);
            $('#rec-count') && ($('#rec-count').textContent = `${json.data.total} 只`);
        } else {
            tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">加载失败</td></tr>';
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-cell">数据加载失败</td></tr>';
        console.error('加载推荐列表失败:', err);
    }
}

function renderRecommendationsTable(recs) {
    const tbody = $('#recommendations-tbody');
    if (!tbody) return;
    
    if (!recs || recs.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="8">
                <div class="empty-state">
                    <div class="empty-icon">🔍</div>
                    <h3>暂无符合条件的推荐</h3>
                    <p>宁缺毋滥，请耐心等待更好的机会。</p>
                </div>
            </td></tr>`;
        return;
    }
    
    tbody.innerHTML = recs.map((rec, i) => {
        const scoreClass = rec.final_score >= 75 ? 'score-high' : 
                          rec.final_score >= 60 ? 'score-mid' : 'score-low';
        const iasClass = rec.ias_score >= 70 ? 'score-high' : 
                        rec.ias_score >= 55 ? 'score-mid' : 'score-low';
        const timingClass = rec.timing_score >= 70 ? 'score-high' : 
                           rec.timing_score >= 50 ? 'score-mid' : 'score-low';
        
        let badgeClass = 'badge-wait';
        if (rec.is_recommended) badgeClass = 'badge-strong';
        else if (rec.final_score >= 70) badgeClass = 'badge-recommend';
        else if (rec.final_score >= 55) badgeClass = 'badge-watch';
        else if (rec.final_score < 40) badgeClass = 'badge-reject';
        
        const features = rec.features || {};
        const featCount = features.passed_count || 0;
        const sym = escapeHtml(rec.symbol);
        const name = escapeHtml(rec.name);
        const recText = escapeHtml(rec.recommendation);
        
        return `
            <tr>
                <td class="rank">#${i + 1}</td>
                <td>
                    <span class="symbol-cell">${name}</span><br>
                    <span class="name-cell">${sym}</span>
                </td>
                <td class="${scoreClass}">${rec.final_score.toFixed(1)}</td>
                <td class="${iasClass}">${rec.ias_score.toFixed(1)}</td>
                <td class="${timingClass}">${rec.timing_score.toFixed(1)}</td>
                <td>
                    <span style="color: ${featCount >= 5 ? 'var(--accent-green)' : 'var(--accent-yellow)'}">
                        ${featCount}/7
                    </span>
                </td>
                <td><span class="recommendation-badge ${badgeClass}">${recText}</span></td>
                <td>
                    <button class="btn btn-secondary btn-sm detail-btn" data-symbol="${sym}">
                        📋 详情
                    </button>
                </td>
            </tr>`;
    }).join('');
}

async function loadStockPool() {
    if (state.currentTab !== 'stock-pool') return;
    
    const tbody = $('#pool-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">加载中...</td></tr>';
    
    try {
        const resp = await fetch(STOCK_POOL_API);
        const json = await resp.json();
        
        if (json.success && json.data.pool) {
            state.stockPool = json.data.pool;
            renderStockPoolTable(json.data.pool);
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">加载失败</td></tr>';
    }
}

function renderStockPoolTable(pool) {
    const tbody = $('#pool-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = pool.map(stock => `
        <tr>
            <td><code>${escapeHtml(stock.symbol)}</code></td>
            <td><strong>${escapeHtml(stock.name)}</strong></td>
            <td>${escapeHtml(stock.sector)}</td>
            <td>${stock.dividend_yield.toFixed(1)}%</td>
            <td>${stock.state_ownership.toFixed(1)}%</td>
            <td style="font-size:0.85rem;color:var(--text-secondary)">${escapeHtml(stock.reason)}</td>
        </tr>
    `).join('');
}

// ========== 股票详情Modal ==========
async function showStockDetail(symbol) {
    const modal = $('#stock-modal');
    const body = $('#modal-body');
    const title = $('#modal-title');
    
    if (!modal || !body) return;
    
    modal.classList.add('active');
    body.innerHTML = '<div class="loading">加载详情中...</div>';
    title.textContent = `股票详情 - ${symbol}`;
    
    try {
        const resp = await fetch(`${API_BASE}/stocks/${symbol}?refresh=false`);
        const json = await resp.json();
        
        if (json.success) {
            renderStockDetail(json.data);
        } else {
            body.innerHTML = `<div class="empty-state"><p>${json.message || '加载失败'}</p></div>`;
        }
    } catch (err) {
        body.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function renderStockDetail(data) {
    const body = $('#modal-body');
    const title = $('#modal-title');
    if (!body) return;
    
    title.textContent = `${escapeHtml(data.name)} (${escapeHtml(data.symbol)})`;
    
    const ias = data.ias_details || {};
    const timing = data.timing_details || {};
    const features = data.features || {};
    const ics = data.ics || {};
    const recText = escapeHtml(data.recommendation);
    const timingRating = escapeHtml(timing.rating || '--');
    const reasonText = escapeHtml(data.reason || '');
    
    body.innerHTML = `
        <div style="margin-bottom: 20px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <h3 style="font-size:1.4rem;">综合评分: ${data.final_score.toFixed(1)}</h3>
                <span class="recommendation-badge ${data.is_recommended ? 'badge-strong' : 'badge-wait'}">
                    ${recText}
                </span>
            </div>
        </div>
        
        <h4 style="color:var(--accent-blue);margin-bottom:12px;">📊 IAS评分详情 (权重50%)</h4>
        ${renderScoreBar('IAS总分', data.ias_score, 100)}
        ${renderScoreBar('行业Alpha (25%)', ias.industry_score || 0, 100)}
        ${renderScoreBar('公司Alpha (30%)', ias.company_score || 0, 100)}
        ${renderScoreBar('资金Alpha (25%)', ias.capital_score || 0, 100)}
        ${renderScoreBar('趋势Alpha (20%)', ias.momentum_score || 0, 100)}
        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:16px;">
            事件修正: ${ias.event_adjustment || 0}分 | 
            通过双重过滤: ${ias.passed ? '✅' : '❌'}
        </p>
        
        <h4 style="color:var(--accent-orange);margin-bottom:12px;">⏱️ 买入时机评估 (权重50%)</h4>
        ${renderScoreBar('时机总分', timing.normalized_score || 0, 100)}
        ${renderScoreBar('历史PE分位', (timing.details?.historical_pe_score || 0) * 5, 100)}
        ${renderScoreBar('行业PE比较', (timing.details?.industry_pe_score || 0) * 10, 100)}
        ${renderScoreBar('均线位置', (timing.details?.ma_position_score || 0) * 10, 100)}
        ${renderScoreBar('FCF收益率', (timing.details?.fcf_yield_score || 0) * 10, 100)}
        <p style="font-size:0.85rem;color:var(--text-muted);margin-bottom:16px;">
            评级: ${timingRating} | 
            买入区域: ${timing.is_buy_zone ? '✅ 是' : '❌ 否'}
        </p>
        
        <h4 style="color:var(--accent-purple);margin-bottom:12px;">🎯 7大选股特征</h4>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.85rem;margin-bottom:16px;">
            ${renderFeatureItem('1. 资产随时间增值', features.asset_appreciation)}
            ${renderFeatureItem('2. 产品恒久需求', features.timeless_demand)}
            ${renderFeatureItem('3. 内生性增长', features.endogenous_growth)}
            ${renderFeatureItem('4. 高分红率', features.high_dividend)}
            ${renderFeatureItem('5. 国有资本加仓', features.state_capital)}
            ${renderFeatureItem('6. 未来趋势受益', features.future_trend)}
            ${renderFeatureItem('7. 符合政策方向', features.policy_aligned)}
        </div>
        <p style="font-size:0.85rem;">匹配: ${features.passed_count || 0}/7</p>
        
        <h4 style="color:var(--accent-yellow);margin-bottom:12px;">🏛️ 机构一致性 (ICS)</h4>
        ${renderScoreBar('ICS评分', ics.ics_score || 0, 100)}
        <p style="font-size:0.85rem;color:var(--text-muted);">
            核心股票池: ${ics.is_core ? '✅ 是' : '❌ 否'} (需 ≥80)
        </p>
        
        ${reasonText ? `<div style="margin-top:16px;padding:12px;background:var(--bg-secondary);border-radius:8px;">
            <strong>💡 推荐理由：</strong>${reasonText}
        </div>` : ''}
        
        <div class="disclaimer" style="margin-top:16px;">
            ⚠️ 本分析仅供研究参考，不构成投资建议。市场有风险，投资需谨慎。
        </div>
    `;
}

function renderScoreBar(label, score, max) {
    const pct = Math.min(100, Math.max(0, (score / max) * 100));
    const colorClass = pct >= 70 ? 'high' : pct >= 40 ? 'mid' : 'low';
    return `
        <div class="score-bar-container">
            <div class="score-bar-label">
                <span>${label}</span>
                <span>${score.toFixed(1)} / ${max}</span>
            </div>
            <div class="score-bar">
                <div class="score-bar-fill ${colorClass}" style="width:${pct}%"></div>
            </div>
        </div>`;
}

function renderFeatureItem(label, passed) {
    return `<div>${passed ? '✅' : '❌'} ${label}</div>`;
}

function closeModal() {
    $('#stock-modal')?.classList.remove('active');
}

// Modal点击外部关闭
document.addEventListener('click', (e) => {
    if (e.target === $('#stock-modal')) {
        closeModal();
    }
});

// ESC关闭
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
});

// ========== 状态更新 ==========
function updateStatus(online, text) {
    state.isOnline = online;
    const dot = $('#status-dot');
    const textEl = $('#status-text');
    
    if (dot) {
        dot.className = `status-dot ${online ? 'online' : 'offline'}`;
    }
    if (textEl) {
        textEl.textContent = text;
    }
}

// ========== 自动刷新 ==========
function startAutoRefresh() {
    setInterval(() => {
        if (state.currentTab === 'dashboard') {
            loadDashboard();
            loadIndexData();
        }
    }, REFRESH_INTERVAL);
    
    // 接近交易时间时刷新更频繁
    checkTradingHours();
}

function checkTradingHours() {
    // 北京时间 9:25, 13:05, 14:50 对应 UTC 1:25, 5:05, 6:50
    // 在接近这些时间时触发刷新
    const now = new Date();
    const utcHour = now.getUTCHours();
    const utcMin = now.getUTCMinutes();
    
    const refreshTimes = [
        { h: 1, m: 25 },  // 9:25 CST
        { h: 5, m: 5 },   // 13:05 CST
        { h: 6, m: 50 },  // 14:50 CST
    ];
    
    for (const t of refreshTimes) {
        if (utcHour === t.h && Math.abs(utcMin - t.m) <= 2) {
            loadAllData(true);
            break;
        }
    }
    
    setTimeout(checkTradingHours, 60000); // 每分钟检查一次
}

// ========== 工具函数 ==========
function formatNumber(num) {
    if (num === null || num === undefined || isNaN(num)) return '--';
    return Number(num).toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

function formatTime(date) {
    return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}

// 导出到全局作用域
window.showStockDetail = showStockDetail;
window.closeModal = closeModal;
