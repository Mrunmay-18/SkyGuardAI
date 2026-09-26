"""
app.py — SkyGuard AI Dashboard (Streamlit)

A light-themed, professional monitoring dashboard for the SkyGuard AI
AWS anomaly-detection prototype. Reads pre-computed results from the
frozen detection pipeline — no ML logic runs inside this file.

Data sources:
  data/test_injected_aws.csv   — 15-minute AWS readings
  data/station_metadata.csv    — station coordinates
  outputs/alerts.json           — 10 detected alerts from the pipeline

Run with:
  streamlit run app.py

Requirements: streamlit>=1.61, plotly>=5.24, pandas, numpy
"""

import json
import os

import numpy as np
import pandas as pd

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import streamlit as st
except ImportError:
    raise ImportError("Streamlit is required. Install with: pip install streamlit")

# ──────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SkyGuard AI — AWS Anomaly Monitor",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────
# CSS — injected once at the top (light theme)
# ──────────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
/* Main background */
.stApp { background-color: #FFFFFF; }

/* Cards */
.skyguard-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 8px;
}
.skyguard-card-gray {
    background-color: #F7F9FC;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    margin-bottom: 8px;
}

/* Metric card with colored left border */
.metric-card {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-left: 4px solid #1E3A8A;
    border-radius: 8px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.metric-card-green  { border-left-color: #10B981; }
.metric-card-amber  { border-left-color: #F59E0B; }
.metric-card-red    { border-left-color: #EF4444; }

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #1F2937;
    line-height: 1.2;
}
.metric-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #6B7280;
    margin-top: 4px;
}

/* Severity badges */
.sev-high   { background:#EF4444; color:#fff; padding:2px 12px; border-radius:12px; font-size:0.8rem; font-weight:600; }
.sev-medium { background:#F59E0B; color:#1F2937; padding:2px 12px; border-radius:12px; font-size:0.8rem; font-weight:600; }
.sev-low    { background:#1E3A8A; color:#fff; padding:2px 12px; border-radius:12px; font-size:0.8rem; font-weight:600; }
.sev-critical { background:#991B1B; color:#fff; padding:2px 12px; border-radius:12px; font-size:0.8rem; font-weight:600; }

/* Section spacing */
.section-gap { margin-top: 24px; }

/* Headers */
h1 { font-size: 2rem !important; color: #1F2937 !important; }
h2 { font-size: 1.4rem !important; color: #1F2937 !important; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    padding: 8px 16px;
    border-radius: 6px 6px 0 0;
    border: 1px solid #E5E7EB;
    border-bottom: none;
    background-color: #F7F9FC;
}
.stTabs [aria-selected="true"] {
    background-color: #FFFFFF !important;
    border-bottom: 2px solid #1E3A8A !important;
    font-weight: 600;
}

/* Button styling */
.stButton > button {
    background-color: #1E3A8A;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: 500;
}
.stButton > button:hover {
    background-color: #1E40AF;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────
COLORS = {
    "primary": "#1E3A8A",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "text": "#1F2937",
    "muted": "#6B7280",
    "grid": "#E5E7EB",
    "card_bg": "#F7F9FC",
}

TIME_RANGES = {
    "15 min": pd.Timedelta(minutes=15),
    "30 min": pd.Timedelta(minutes=30),
    "1 hr": pd.Timedelta(hours=1),
    "6 hr": pd.Timedelta(hours=6),
    "24 hr": pd.Timedelta(hours=24),
    "Full": None,
}

DATA_PATH = "data/test_injected_aws.csv"
META_PATH = "data/station_metadata.csv"
ALERTS_PATH = "outputs/alerts.json"


# ──────────────────────────────────────────────────────────────────────
# Cached data loaders
# ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load_raw_data():
    """Load 15-minute AWS readings."""
    df = pd.read_csv(DATA_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@st.cache_data
def load_metadata():
    """Load station coordinates."""
    return pd.read_csv(META_PATH)


@st.cache_data
def load_alerts():
    """Load pre-computed alerts. Returns empty list if file missing."""
    if not os.path.exists(ALERTS_PATH):
        return []
    with open(ALERTS_PATH, "r") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────
def severity_badge(severity: str) -> str:
    """Return HTML for a severity badge pill."""
    sev = severity.lower()
    css_class = {
        "critical": "sev-critical",
        "high": "sev-high",
        "medium": "sev-medium",
        "low": "sev-low",
    }.get(sev, "sev-low")
    return f'<span class="{css_class}">{severity}</span>'


def metric_card(value, label, emoji="", border_class=""):
    """Render a metric card via HTML."""
    border = f"metric-card {border_class}".strip()
    st.markdown(
        f"""<div class="{border}">
        <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:1.5rem;">{emoji}</span>
            <div>
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>
        </div>
        </div>""",
        unsafe_allow_html=True,
    )


def filter_by_time_range(df: pd.DataFrame, selected_range: str) -> pd.DataFrame:
    """Filter DataFrame to the last N minutes of data."""
    delta = TIME_RANGES.get(selected_range)
    if delta is None or selected_range == "Full":
        return df
    max_ts = df["timestamp"].max()
    min_ts = max_ts - delta
    return df[df["timestamp"] >= min_ts].copy()


def make_timeseries_plot(df: pd.DataFrame, col: str, title: str,
                         color: str, unit: str):
    """Create a Plotly time-series chart with anomaly markers."""
    if not PLOTLY_AVAILABLE:
        # Fallback: st.line_chart
        st.subheader(title)
        plot_df = df[["timestamp", col]].set_index("timestamp")
        st.line_chart(plot_df, use_container_width=True)
        return

    fig = go.Figure()

    # Main line.
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df[col],
        mode="lines",
        name=col.capitalize(),
        line=dict(color=color, width=1.5),
        hovertemplate="<b>%{x}</b><br>" + f"{col.capitalize()}: %{{y:.2f}} {unit}<extra></extra>",
    ))

    # Anomaly markers.
    anom = df[df.get("is_anomaly", 0) == 1]
    if len(anom) > 0:
        fig.add_trace(go.Scatter(
            x=anom["timestamp"], y=anom[col],
            mode="markers",
            name="Anomaly",
            marker=dict(color=COLORS["danger"], size=6, symbol="x"),
            hovertemplate="<b>ANOMALY</b><br>%{x}<br>" + f"{col.capitalize()}: %{{y:.2f}} {unit}<extra></extra>",
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title=f"{col.capitalize()} ({unit})",
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=COLORS["text"], size=12),
        xaxis=dict(gridcolor=COLORS["grid"], showline=False),
        yaxis=dict(gridcolor=COLORS["grid"], showline=False),
        margin=dict(l=40, r=20, t=40, b=40),
        height=320,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def make_station_map(metadata: pd.DataFrame, alerts: list):
    """Create a station scatter map."""
    if not PLOTLY_AVAILABLE:
        st.warning("Plotly not available — map skipped.")
        return

    # Merge alert count per station.
    alert_counts = {}
    for a in alerts:
        sid = a.get("station_id", "")
        alert_counts[sid] = alert_counts.get(sid, 0) + 1

    metadata = metadata.copy()
    metadata["alert_count"] = metadata["station_id"].map(
        lambda s: alert_counts.get(s, 0)
    )
    metadata["status_text"] = metadata.apply(
        lambda r: f"{r['station_id']}<br>Alerts: {r['alert_count']}",
        axis=1,
    )

    fig = px.scatter_mapbox(
        metadata,
        lat="latitude",
        lon="longitude",
        hover_name="station_id",
        hover_data={"status_text": True, "latitude": ":.4f", "longitude": ":.4f"},
        size="alert_count",
        size_max=15,
        color="alert_count",
        color_continuous_scale=["#10B981", "#F59E0B", "#EF4444"],
        zoom=9,
        height=400,
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)


# ──────────────────────────────────────────────────────────────────────
# Tab builders
# ──────────────────────────────────────────────────────────────────────
def build_overview_tab(raw_df, metadata, alerts, time_range):
    """Tab 1: Overview — metrics + map + sensor status + controls."""
    filtered = filter_by_time_range(raw_df, time_range)

    # Top metric cards.
    n_stations = raw_df["station_id"].nunique()
    n_rows = len(filtered)
    n_anomalies = int((filtered.get("is_anomaly", 0) == 1).sum())
    n_alerts = len(alerts)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card(n_stations, "Stations Active", "🛰️", "metric-card-green")
    with col2:
        metric_card(n_rows, "Observations", "📊", "")
    with col3:
        metric_card(n_anomalies, "Anomalies", "⚠️", "metric-card-amber")
    with col4:
        metric_card(n_alerts, "Alerts", "🔔", "metric-card-red")

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    # Station map + sensor status.
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Station Map")
        make_station_map(metadata, alerts)

    with right:
        st.subheader("Sensor Status")
        for sid in sorted(raw_df["station_id"].unique()):
            st_df = filtered[filtered["station_id"] == sid]
            n_anom = int((st_df.get("is_anomaly", 0) == 1).sum())
            status = "HEALTH" if n_anom == 0 else ("WATCH" if n_anom < 10 else "ALERT")
            color = COLORS["success"] if status == "HEALTH" else (
                COLORS["warning"] if status == "WATCH" else COLORS["danger"]
            )
            st.markdown(
                f"""<div class="skyguard-card-gray" style="display:flex;
                justify-content:space-between;align-items:center;">
                <span style="font-weight:600;color:{COLORS['text']};">{sid}</span>
                <span style="color:{color};font-weight:600;font-size:0.85rem;">
                ● {status}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    # Export + replay.
    ecol1, ecol2, ecol3 = st.columns([1, 1, 2])
    with ecol1:
        csv_data = filtered.to_csv(index=False).encode()
        st.download_button("📄 Export CSV", data=csv_data,
                           file_name="skyguard_export.csv", mime="text/csv")
    with ecol2:
        json_data = json.dumps(alerts, indent=2).encode()
        st.download_button("🔗 Export JSON", data=json_data,
                           file_name="skyguard_alerts.json", mime="application/json")
    with ecol3:
        st.markdown(
            f'<div style="padding-top:8px;color:{COLORS["muted"]};font-size:0.85rem;">'
            f"Showing {len(filtered)} rows | Range: {time_range}</div>",
            unsafe_allow_html=True,
        )


def build_alerts_tab(alerts):
    """Tab 2: Alerts — table + detail panel."""
    if not alerts:
        st.info("No alerts file found. Run the detection pipeline to generate outputs/alerts.json.")
        return

    # Alerts table.
    st.subheader("Detected Alerts")
    alerts_df = pd.DataFrame(alerts)
    display_cols = ["station_id", "timestamp", "anomaly_type", "severity",
                    "confidence", "status"]
    st.dataframe(alerts_df[display_cols], use_container_width=True, hide_index=True)

    # Alert selection.
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.subheader("Alert Detail")

    # Use selectbox for selection (works in all Streamlit versions).
    options = [f"{i+1}. {a['station_id']} | {a['timestamp']} | {a['anomaly_type']} | {a['severity']}"
               for i, a in enumerate(alerts)]
    selected_idx = st.selectbox("Select an alert:", range(len(options)),
                               format_func=lambda i: options[i])
    alert = alerts[selected_idx]

    # Detail panel.
    badge = severity_badge(alert.get("severity", "Low"))
    left, right = st.columns([2, 1])
    with left:
        st.markdown(
            f"""<div class="skyguard-card">
            <h3>{alert['station_id']} — {alert['anomaly_type']}</h3>
            <p><b>Timestamp:</b> {alert['timestamp']}</p>
            <p><b>Status:</b> {alert.get('status', 'N/A')} &nbsp; {badge}</p>
            <p><b>Confidence:</b> {alert.get('confidence', 'N/A')}/100</p>
            <p><b>Sensor Health:</b> {alert.get('sensor_health', 'N/A')}</p>
            </div>""",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"""<div class="skyguard-card-gray">
            <h3>📊 Reading</h3>
            <p>🌡️ Temperature: <b>{alert.get('temperature', 'N/A')} °C</b></p>
            <p>🌀 Pressure: <b>{alert.get('pressure', 'N/A')} hPa</b></p>
            <p>💧 Humidity: <b>{alert.get('humidity', 'N/A')} %</b></p>
            </div>""",
            unsafe_allow_html=True,
        )

    # Reasons.
    st.markdown(
        f"""<div class="skyguard-card">
        <h3>🔍 Evidence & Reasons</h3>
        <ul>""",
        unsafe_allow_html=True,
    )
    for reason in alert.get("reasons", []):
        st.markdown(f"<li>{reason}</li>", unsafe_allow_html=True)
    st.markdown("</ul></div>", unsafe_allow_html=True)

    # Recommendation.
    st.markdown(
        f"""<div class="skyguard-card-gray" style="border-left:4px solid {COLORS['primary']};">
        <h3>🔧 Recommendation</h3>
        <p>{alert.get('maintenance_recommendation', 'Review manually.')}</p>
        </div>""",
        unsafe_allow_html=True,
    )
    
    # Self-healing corrected values.
    if alert.get("corrected_temperature") is not None:
        st.markdown("**🩹 Suggested Corrected Reading (self-healing):**")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric(
            "Corrected Temp",
            f"{alert['corrected_temperature']} °C",
            f"{alert['corrected_temperature'] - alert['temperature']:+.2f}",
        )
        cc2.metric(
            "Corrected Pressure",
            f"{alert['corrected_pressure']} hPa",
            f"{alert['corrected_pressure'] - alert['pressure']:+.2f}",
        )
        cc3.metric(
            "Corrected Humidity",
            f"{alert['corrected_humidity']} %",
            f"{alert['corrected_humidity'] - alert['humidity']:+.2f}",
        )
        st.caption(
            f"Correction confidence: {alert['correction_confidence']}/100 — "
            f"{alert['correction_basis']}"
        )

    # Replay control.
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.subheader("Replay Alerts")
    if "replay_idx" not in st.session_state:
        st.session_state["replay_idx"] = 0
    rcol1, rcol2, rcol3 = st.columns([1, 2, 1])
    with rcol1:
        if st.button("⏮ Previous"):
            st.session_state["replay_idx"] = (st.session_state["replay_idx"] - 1) % len(alerts)
    with rcol3:
        if st.button("Next ▶"):
            st.session_state["replay_idx"] = (st.session_state["replay_idx"] + 1) % len(alerts)
    with rcol2:
        ri = st.session_state["replay_idx"]
        ra = alerts[ri]
        st.markdown(
            f"""<div class="skyguard-card">
            <b>Alert {ri+1}/{len(alerts)}</b> — {ra['station_id']} |
            {ra['timestamp']} | {ra['anomaly_type']} | {severity_badge(ra.get('severity','Low'))}
            </div>""",
            unsafe_allow_html=True,
        )


def build_live_data_tab(raw_df, time_range):
    """Tab 3: Live Data — T/H/P charts + filtered feed table."""
    filtered = filter_by_time_range(raw_df, time_range)

    st.subheader("Time-Series Charts")
    make_timeseries_plot(filtered, "temperature", "Temperature",
                         COLORS["danger"], "°C")
    make_timeseries_plot(filtered, "humidity", "Humidity",
                         COLORS["primary"], "%")
    make_timeseries_plot(filtered, "pressure", "Pressure",
                         COLORS["success"], "hPa")

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.subheader("Raw Feed (filtered)")
    display_cols = ["timestamp", "station_id", "temperature", "pressure",
                    "humidity", "is_anomaly", "anomaly_type"]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available], use_container_width=True, hide_index=True)


def build_genuine_events_tab(raw_df):
    """Tab 4: Genuine Events — isolated fault vs. regional weather."""
    st.subheader("Genuine Weather Event vs. Isolated Sensor Fault")
    st.markdown(
        f"""<p style="color:{COLORS["muted"]};">
        This panel contrasts two scenarios the SkyGuard AI pipeline must distinguish:
        a sensor-specific fault (one station deviates) vs. a genuine regional
        weather event (multiple stations change together).
        </p>""",
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)

    # Left: isolated sensor fault.
    with left:
        st.markdown(
            f"""<div class="skyguard-card" style="border-left:4px solid {COLORS['danger']};">
            <h3>🔴 Isolated Sensor Fault</h3>
            <p style="color:{COLORS["muted"]};">One station deviates; neighbours remain stable.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        # Find a temperature spike example.
        spike = raw_df[(raw_df.get("anomaly_type", "") == "temperature_spike")].head(5)
        if len(spike) > 0:
            st.dataframe(spike[["timestamp", "station_id", "temperature",
                               "anomaly_type"]], use_container_width=True,
                         hide_index=True)
            st.markdown(
                f"""<div style="background:#FEF2F2;padding:10px;border-radius:6px;
                color:{COLORS['danger']};font-size:0.85rem;">
                ⚠️ Only one station shows the spike — neighbours are unaffected.
                This pattern is consistent with a sensor fault.
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.info("No isolated fault examples in the current dataset.")

    # Right: regional weather event.
    with right:
        st.markdown(
            f"""<div class="skyguard-card" style="border-left:4px solid {COLORS['success']};">
            <h3>🟢 Genuine Regional Weather Event</h3>
            <p style="color:{COLORS["muted"]};">Multiple stations change together — not a sensor fault.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        weather = raw_df[(raw_df.get("anomaly_type", "") == "normal_weather_event")].head(5)
        if len(weather) > 0:
            st.dataframe(weather[["timestamp", "station_id", "temperature",
                                 "anomaly_type"]], use_container_width=True,
                         hide_index=True)
            st.markdown(
                f"""<div style="background:#ECFDF5;padding:10px;border-radius:6px;
                color:{COLORS['success']};font-size:0.85rem;">
                ✅ Multiple stations show the same temperature shift — this is
                a genuine weather event, not a sensor fault.
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.info("No weather event examples in the current dataset.")


# ──────────────────────────────────────────────────────────────────────
# Main app
# ──────────────────────────────────────────────────────────────────────
def main():
    # Header.
    st.markdown(
        f"""<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <span style="font-size:2rem;">🛰️</span>
        <h1 style="margin:0;">SkyGuard AI — AWS Anomaly Monitor</h1>
        </div>
        <p style="color:{COLORS['muted']};font-size:0.9rem;">
        AI-powered anomaly detection for Automatic Weather Stations •
        India Meteorological Department (IMD) prototype
        </p>""",
        unsafe_allow_html=True,
    )

    # Load data.
    try:
        raw_df = load_raw_data()
    except FileNotFoundError:
        st.error(f"Data file not found: {DATA_PATH}")
        return

    try:
        metadata = load_metadata()
    except FileNotFoundError:
        st.error(f"Metadata file not found: {META_PATH}")
        return

    alerts = load_alerts()

    # Time range selector (shared across tabs).
    st.markdown(
        f"""<div class="skyguard-card-gray" style="display:flex;
        align-items:center;gap:16px;">
        <span style="font-weight:600;color:{COLORS['text']};">⏱ Time Range:</span>
        </div>""",
        unsafe_allow_html=True,
    )
    time_range = st.radio(
        "Select time range:",
        list(TIME_RANGES.keys()),
        horizontal=True,
        label_visibility="collapsed",
    )

    # Tabs.
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview",
        "🚨 Alerts",
        "📈 Live Data",
        "🌦 Genuine Events",
    ])

    with tab1:
        build_overview_tab(raw_df, metadata, alerts, time_range)

    with tab2:
        build_alerts_tab(alerts)

    with tab3:
        build_live_data_tab(raw_df, time_range)

    with tab4:
        build_genuine_events_tab(raw_df)

    # Footer.
    st.markdown(
        f"""<div style="margin-top:32px;padding-top:12px;border-top:1px solid {COLORS['grid']};
        color:{COLORS['muted']};font-size:0.8rem;text-align:center;">
        SkyGuard AI Prototype — Thresholds are operational heuristics, not official standards.
        Detection pipeline is frozen; this dashboard displays pre-computed results only.
        </div>""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()