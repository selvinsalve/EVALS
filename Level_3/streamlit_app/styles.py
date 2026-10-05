"""Custom CSS styles for the Streamlit AI Order Assistant application."""

CUSTOM_CSS = """
<style>
/* Completely Hide Streamlit Left Pane / Sidebar */
[data-testid="stSidebar"], section[data-testid="stSidebar"], [data-testid="collapsedControl"] {
    display: none !important;
}

/* Main container styling */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 960px;
    margin: 0 auto;
}

/* Header aesthetics */
.app-header {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

.app-title {
    font-size: 2.1rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0;
    letter-spacing: -0.02em;
}

.app-subtitle {
    font-size: 1.05rem;
    color: #94a3b8;
    margin-top: 6px;
    margin-bottom: 0;
}

/* Badge styling */
.badge-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 0 14px 0;
}

.badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.025em;
    text-transform: uppercase;
}

.badge-order-api {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
}

.badge-rag {
    background-color: #1e1b4b;
    color: #818cf8;
    border: 1px solid #4f46e5;
}

.badge-intent {
    background-color: #312e81;
    color: #c7d2fe;
    border: 1px solid #4338ca;
}

.badge-demo {
    background-color: #451a03;
    color: #fbbf24;
    border: 1px solid #d97706;
}

/* Order Details Card */
.order-card {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 18px;
    margin: 14px 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.order-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 10px;
    margin-bottom: 12px;
}

.order-card-id {
    font-size: 1.15rem;
    font-weight: 700;
    color: #38bdf8;
}

.order-status-pill {
    padding: 3px 9px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 700;
}

.status-shipped { background: #0369a1; color: #e0f2fe; }
.status-delivered { background: #047857; color: #d1fae5; }
.status-delayed { background: #b45309; color: #fef3c7; }
.status-processing { background: #4338ca; color: #e0e7ff; }
.status-cancelled { background: #991b1b; color: #fee2e2; }
.status-placed { background: #374151; color: #f3f4f6; }

.order-detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
    font-size: 0.88rem;
    color: #cbd5e1;
    margin-bottom: 12px;
}

.order-items-list {
    background: #1e293b;
    border-radius: 6px;
    padding: 10px;
    margin-top: 8px;
    font-size: 0.85rem;
}

.source-item {
    background: #1e293b;
    border-left: 3px solid #6366f1;
    padding: 8px 12px;
    margin-bottom: 8px;
    border-radius: 0 6px 6px 0;
    font-size: 0.85rem;
}

/* Chat suggested chips */
.suggestion-chip {
    background: #1e293b;
    border: 1px solid #334155;
    color: #94a3b8;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.82rem;
    cursor: pointer;
    transition: all 0.2s ease;
}
.suggestion-chip:hover {
    border-color: #38bdf8;
    color: #38bdf8;
}
</style>
"""
