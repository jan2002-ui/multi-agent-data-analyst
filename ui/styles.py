"""Global CSS for the dashboard (dark, card-based, no external assets)."""

CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.6rem; max-width: 1280px;}
html, body, [class*="css"] {font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;}

.hero {background: linear-gradient(135deg,#312e81 0%,#4f46e5 55%,#0891b2 130%); border-radius: 20px;
       padding: 30px 36px; margin-bottom: 22px; box-shadow: 0 18px 50px -20px rgba(79,70,229,.7);}
.hero h1 {margin: 0 0 6px; font-size: 2rem; letter-spacing: -.02em; color: #fff;}
.hero p {margin: 0; color: rgba(255,255,255,.82); font-size: 1rem;}
.badges {margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap;}
.badge {background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.22); color: #fff;
        padding: 3px 12px; border-radius: 999px; font-size: .78rem; backdrop-filter: blur(4px);}

.kpis {display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; margin: 6px 0 22px;}
.kpi {background: #121A33; border: 1px solid rgba(148,163,184,.16); border-radius: 16px; padding: 16px 18px;
      transition: transform .15s, border-color .15s;}
.kpi:hover {transform: translateY(-2px); border-color: rgba(99,102,241,.6);}
.kpi .label {color: #94A3B8; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em;}
.kpi .value {color: #F8FAFC; font-size: 1.65rem; font-weight: 700; margin-top: 4px; letter-spacing: -.02em;}
.kpi .sub {color: #64748B; font-size: .78rem; margin-top: 2px;}

.insight {background: #121A33; border: 1px solid rgba(148,163,184,.14); border-left: 5px solid #6366F1;
          border-radius: 14px; padding: 14px 18px; margin-bottom: 10px;}
.insight.critical {border-left-color: #FB7185;} .insight.warning {border-left-color: #F59E0B;}
.insight.opportunity {border-left-color: #22D3EE;} .insight.positive {border-left-color: #34D399;}
.insight .top {display: flex; justify-content: space-between; align-items: center; gap: 10px;}
.insight .title {font-weight: 650; color: #F1F5F9;}
.insight .area {font-size: .7rem; text-transform: uppercase; letter-spacing: .08em; color: #94A3B8; white-space: nowrap;}
.insight .detail {color: #CBD5E1; font-size: .92rem; margin-top: 4px;}
.insight .action {color: #A5B4FC; font-size: .85rem; margin-top: 6px; font-weight: 600;}

.summary {background: linear-gradient(180deg,#121A33,#0F1730); border: 1px solid rgba(99,102,241,.35);
          border-radius: 16px; padding: 18px 22px; color: #E2E8F0; font-size: 1.02rem; line-height: 1.6; margin-bottom: 18px;}
.summary small {color: #94A3B8;}

.section-title {font-size: 1.15rem; font-weight: 650; margin: 8px 0 2px; color: #F1F5F9;}
.section-caption {color: #94A3B8; font-size: .88rem; margin-bottom: 10px;}
.pill {display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem; font-weight: 600;}
.pill.success {background: rgba(52,211,153,.16); color: #34D399;} .pill.skipped {background: rgba(148,163,184,.16); color: #CBD5E1;}
.pill.failed {background: rgba(251,113,133,.16); color: #FB7185;}

button[data-baseweb="tab"] {font-weight: 600;}
div[data-testid="stSidebar"] {border-right: 1px solid rgba(148,163,184,.12);}
.sidebar-brand {font-size: 1.15rem; font-weight: 700; color: #F8FAFC;} .sidebar-sub {color: #94A3B8; font-size: .8rem; margin-bottom: 8px;}
</style>
"""
