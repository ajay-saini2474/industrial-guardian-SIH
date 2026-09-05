"""
INDUSTRIAL GUARDIAN
SIH-ready explainable predictive-maintenance dashboard.

Demo highlights:
- On-premise / edge-first architecture banner
- Explainable AI: every score has visible contributing signals
- Maintenance workflow: acknowledge -> assign -> schedule -> close
- Spare inventory and technician simulation
- Downtime-cost / avoided-loss estimation
- Hindi + English technician alerts
- Incident history and CSV export

This is a simulation/demo. Replace the sensor layer with MQTT, OPC-UA,
REST, SQL or an edge gateway in production.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ---------------------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Industrial Guardian",
    page_icon="🛡️",
    layout="wide",
)

MACHINES = {
    "Engine-01": {
        "temp": 70, "oil": 4.3, "vib": 0.20, "rpm": 1500,
        "criticality": "Medium", "hourly_loss": 18000,
    },
    "Engine-02": {
        "temp": 88, "oil": 3.0, "vib": 0.55, "rpm": 1620,
        "criticality": "High", "hourly_loss": 42000,
    },
    "Pump-03": {
        "temp": 104, "oil": 1.9, "vib": 0.85, "rpm": 1800,
        "criticality": "Critical", "hourly_loss": 65000,
    },
    "Pump-01": {
        "temp": 65, "oil": 4.6, "vib": 0.18, "rpm": 1400,
        "criticality": "Low", "hourly_loss": 12000,
    },
    "Engine-04": {
        "temp": 74, "oil": 4.0, "vib": 0.25, "rpm": 1550,
        "criticality": "Medium", "hourly_loss": 25000,
    },
}

TECHNICIANS = [
    {"name": "Ravi Kumar", "skill": "Mechanical", "status": "Available"},
    {"name": "Neha Sharma", "skill": "Electrical", "status": "Available"},
    {"name": "Amit Singh", "skill": "Lubrication", "status": "On another job"},
]

INVENTORY = {
    "Bearing": {"available": 8, "reorder": 3},
    "Seal Kit": {"available": 12, "reorder": 4},
    "Lubricant": {"available": 25, "reorder": 8},
    "Cooling Fan": {"available": 2, "reorder": 2},
    "Temperature Sensor": {"available": 6, "reorder": 2},
}

CSS = """
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
.hero {
    padding: 24px;
    border-radius: 18px;
    background: linear-gradient(135deg, #102a43, #1f4e79);
    color: white;
    margin-bottom: 18px;
}
.hero h1 {margin: 0; font-size: 2.1rem;}
.hero p {margin: 8px 0 0; opacity: .9;}
.card {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
}
.explain {
    border-left: 5px solid #2f80ed;
    background: rgba(47,128,237,.08);
    padding: 14px;
    border-radius: 10px;
}
.critical {
    border-left: 5px solid #e74c3c;
    background: rgba(231,76,60,.10);
    padding: 14px;
    border-radius: 10px;
}
.warning {
    border-left: 5px solid #f2c94c;
    background: rgba(242,201,76,.12);
    padding: 14px;
    border-radius: 10px;
}
.success {
    border-left: 5px solid #27ae60;
    background: rgba(39,174,96,.10);
    padding: 14px;
    border-radius: 10px;
}
.small {font-size: .86rem; opacity: .78;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 2. SESSION STATE
# ---------------------------------------------------------------------

def init_state() -> None:
    defaults = {
        "tick": 0,
        "page": "Mission Control",
        "selected_machine": "Pump-03",
        "acknowledged": set(),
        "work_orders": [],
        "incidents": [
            {
                "date": "04 Sep",
                "machine": "Engine-02",
                "problem": "Oil pressure drop",
                "severity": "High",
                "technician": "Ravi Kumar",
                "status": "Closed",
                "saved": 84000,
            },
            {
                "date": "03 Sep",
                "machine": "Pump-01",
                "problem": "High vibration",
                "severity": "Medium",
                "technician": "Neha Sharma",
                "status": "Closed",
                "saved": 36000,
            },
        ],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


# ---------------------------------------------------------------------
# 3. SENSOR + EXPLAINABLE AI LAYER
# ---------------------------------------------------------------------

def vibration_label(value: float) -> str:
    if value < 0.30:
        return "Normal"
    if value < 0.60:
        return "Moderate"
    if value < 0.80:
        return "High"
    return "Very High"


def live_reading(machine: str) -> Dict:
    cfg = MACHINES[machine]
    rng = np.random.default_rng(
        abs(hash(machine + str(st.session_state.tick))) % (2**32)
    )
    temp = cfg["temp"] + rng.normal(0, 1.2)
    oil = max(.1, cfg["oil"] + rng.normal(0, .10))
    vib = max(0, cfg["vib"] + rng.normal(0, .03))
    rpm = cfg["rpm"] + rng.normal(0, 15)

    return {
        "temperature": round(float(temp), 1),
        "oil_pressure": round(float(oil), 2),
        "vibration_value": round(float(vib), 2),
        "vibration": vibration_label(float(vib)),
        "rpm": round(float(rpm)),
    }


def explainable_assessment(reading: Dict) -> Dict:
    temp = reading["temperature"]
    oil = reading["oil_pressure"]
    vib = reading["vibration"]

    contributions = []
    score = 0

    if temp >= 100:
        contributions.append(("Temperature", 40, f"{temp}°C is in the critical band"))
        score += 40
    elif temp >= 85:
        contributions.append(("Temperature", 20, f"{temp}°C is above the normal band"))
        score += 20

    if oil < 2:
        contributions.append(("Oil pressure", 40, f"{oil} bar indicates a major drop"))
        score += 40
    elif oil < 3.5:
        contributions.append(("Oil pressure", 20, f"{oil} bar is below the normal band"))
        score += 20

    vib_score = {
        "Normal": 0,
        "Moderate": 10,
        "High": 20,
        "Very High": 30,
    }[vib]
    if vib_score:
        contributions.append(("Vibration", vib_score, f"Vibration is {vib.lower()}"))
        score += vib_score

    score = min(score, 100)
    hot, low_oil, high_vib = temp >= 85, oil < 3.5, vib in ("High", "Very High")

    if hot and low_oil:
        fault = "Possible lubrication-system fault / oil leakage"
        action = "Inspect oil lines, seals, lubricant level and pressure sensor."
        part = "Seal Kit"
        technician_skill = "Lubrication"
    elif high_vib and hot:
        fault = "Possible mechanical wear with overheating"
        action = "Inspect bearing, shaft alignment, load and cooling system."
        part = "Bearing"
        technician_skill = "Mechanical"
    elif high_vib:
        fault = "Possible bearing wear / misalignment"
        action = "Run vibration analysis and inspect bearing housing."
        part = "Bearing"
        technician_skill = "Mechanical"
    elif hot:
        fault = "Possible cooling-system fault"
        action = "Check coolant flow, fan, radiator and thermal sensor."
        part = "Cooling Fan"
        technician_skill = "Electrical"
    elif low_oil:
        fault = "Possible oil-level drop / seal leakage"
        action = "Check oil level, seals and visible leakage."
        part = "Lubricant"
        technician_skill = "Lubrication"
    else:
        fault = "No significant fault pattern detected"
        action = "Continue routine monitoring."
        part = "None"
        technician_skill = "Mechanical"

    if score >= 55:
        status, level, window = "Critical", "High", "Immediately"
    elif score >= 25:
        status, level, window = "Warning", "Medium", "Within 2 hours"
    else:
        status, level, window = "Normal", "Low", "Routine schedule"

    return {
        **reading,
        "risk_score": score,
        "health_score": 100 - score,
        "status": status,
        "risk_level": level,
        "predicted_fault": fault,
        "recommended_action": action,
        "inspection_window": window,
        "part": part,
        "technician_skill": technician_skill,
        "contributions": contributions,
    }


def all_assessments() -> Dict[str, Dict]:
    return {
        name: explainable_assessment(live_reading(name))
        for name in MACHINES
    }


# ---------------------------------------------------------------------
# 4. BUSINESS / CLOSED-LOOP FUNCTIONS
# ---------------------------------------------------------------------

def matching_technician(skill: str) -> Dict:
    available = [t for t in TECHNICIANS if t["status"] == "Available"]
    exact = [t for t in available if t["skill"] == skill]
    return (exact or available or TECHNICIANS)[0]


def create_work_order(machine: str, assessment: Dict) -> None:
    tech = matching_technician(assessment["technician_skill"])
    hours = 4 if assessment["status"] == "Critical" else 2
    avoided_loss = MACHINES[machine]["hourly_loss"] * hours

    st.session_state.work_orders.append({
        "created": datetime.now().strftime("%d %b %H:%M"),
        "machine": machine,
        "fault": assessment["predicted_fault"],
        "part": assessment["part"],
        "technician": tech["name"],
        "status": "Assigned",
        "estimated_hours": hours,
        "avoided_loss": avoided_loss,
    })

    st.session_state.incidents.insert(0, {
        "date": datetime.now().strftime("%d %b"),
        "machine": machine,
        "problem": assessment["predicted_fault"],
        "severity": assessment["risk_level"],
        "technician": tech["name"],
        "status": "Open",
        "saved": avoided_loss,
    })


def technician_message(machine: str, a: Dict, hindi: bool) -> str:
    if hindi:
        return (
            f"⚠️ {machine}: संभावित समस्या — {a['predicted_fault']}. "
            f"तुरंत निरीक्षण करें। अनुमानित जोखिम {a['risk_score']}%."
        )
    return (
        f"⚠️ {machine}: {a['predicted_fault']}. "
        f"Inspect now. Estimated risk score: {a['risk_score']}%."
    )


# ---------------------------------------------------------------------
# 5. UI HELPERS
# ---------------------------------------------------------------------

def metric_row(assessments: Dict[str, Dict]) -> None:
    counts = {"Normal": 0, "Warning": 0, "Critical": 0}
    for a in assessments.values():
        counts[a["status"]] += 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Machines monitored", len(assessments))
    c2.metric("🟢 Normal", counts["Normal"])
    c3.metric("🟡 Warning", counts["Warning"])
    c4.metric("🔴 Critical", counts["Critical"])


def status_box(machine: str, a: Dict) -> None:
    css_class = {
        "Critical": "critical",
        "Warning": "warning",
        "Normal": "success",
    }[a["status"]]

    st.markdown(
        f"""
        <div class="{css_class}">
        <b>{machine}</b> — <b>{a['status']}</b><br>
        Risk score: <b>{a['risk_score']}/100</b> · Health: <b>{a['health_score']}%</b><br>
        Fault: {a['predicted_fault']}<br>
        <span class="small">Inspection window: {a['inspection_window']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_explanation(a: Dict) -> None:
    st.markdown("#### Why did the AI raise this alert?")
    if not a["contributions"]:
        st.markdown(
            '<div class="success">All monitored signals are inside their normal bands.</div>',
            unsafe_allow_html=True,
        )
        return

    rows = [
        {"Signal": name, "Score added": points, "Reason": reason}
        for name, points, reason in a["contributions"]
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown(
        f"""
        <div class="explain">
        <b>Reasoning trail:</b>
        {a['predicted_fault']} was selected because the abnormal signals
        produced a combined score of <b>{a['risk_score']}/100</b>.
        This is an explainable demo model, not a black-box prediction.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# 6. PAGES
# ---------------------------------------------------------------------

def page_mission_control(assessments: Dict[str, Dict]) -> None:
    st.markdown(
        """
        <div class="hero">
        <h1>🛡️ Industrial Guardian</h1>
        <p>Explainable predictive maintenance for Indian industries — edge-first,
        offline-capable and action-oriented.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        "🔐 Data-sovereignty mode: this demo runs locally. In deployment, "
        "sensor data can remain inside the plant or edge gateway."
    )
    metric_row(assessments)

    st.subheader("Live machine health")
    cols = st.columns(3)
    for index, (machine, a) in enumerate(assessments.items()):
        with cols[index % 3]:
            status_box(machine, a)
            if st.button(f"Open {machine}", key=f"open_{machine}"):
                st.session_state.selected_machine = machine
                st.session_state.page = "Explainable AI"
                st.rerun()


def page_alerts(assessments: Dict[str, Dict]) -> None:
    st.title("🚨 Intelligent Alerts")
    active = {
        name: a for name, a in assessments.items()
        if a["status"] != "Normal"
    }

    if not active:
        st.success("No active alerts. All machines are operating normally.")
        return

    hindi = st.toggle("Hindi technician alert", value=True)

    for machine, a in active.items():
        status_box(machine, a)
        st.caption(technician_message(machine, a, hindi))

        c1, c2, c3 = st.columns(3)
        acknowledged = machine in st.session_state.acknowledged

        with c1:
            if st.button(
                "Acknowledge" if not acknowledged else "Acknowledged",
                key=f"ack_{machine}",
                disabled=acknowledged,
            ):
                st.session_state.acknowledged.add(machine)
                st.rerun()

        with c2:
            if st.button("Create work order", key=f"wo_{machine}"):
                create_work_order(machine, a)
                st.success("Technician assigned and work order created.")

        with c3:
            if st.button("Emergency shutdown (demo)", key=f"shutdown_{machine}"):
                st.session_state.incidents.insert(0, {
                    "date": datetime.now().strftime("%d %b"),
                    "machine": machine,
                    "problem": a["predicted_fault"],
                    "severity": "Critical",
                    "technician": "Control Room",
                    "status": "Shutdown",
                    "saved": 0,
                })
                st.warning("Simulation shutdown logged in incident history.")

        st.divider()


def page_explainable_ai(assessments: Dict[str, Dict]) -> None:
    st.title("🤖 Explainable AI Engine")
    machine = st.selectbox(
        "Select machine",
        list(MACHINES),
        index=list(MACHINES).index(st.session_state.selected_machine),
    )
    st.session_state.selected_machine = machine
    a = assessments[machine]

    status_box(machine, a)
    render_explanation(a)

    st.markdown("#### Decision output")
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Predicted fault:**", a["predicted_fault"])
        st.write("**Recommended action:**", a["recommended_action"])
    with c2:
        st.write("**Risk level:**", a["risk_level"])
        st.write("**Inspection window:**", a["inspection_window"])

    st.caption(
        "Production upgrade path: replace the scoring function with an ML model "
        "while keeping the same input/output contract and explanation interface."
    )


def page_machine_detail(assessments: Dict[str, Dict]) -> None:
    st.title("📟 Machine Digital Record")
    machine = st.selectbox("Machine", list(MACHINES))
    a = assessments[machine]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temperature", f"{a['temperature']} °C")
    c2.metric("Oil pressure", f"{a['oil_pressure']} bar")
    c3.metric("Vibration", a["vibration"])
    c4.metric("RPM", a["rpm"])

    rng = np.random.default_rng(abs(hash(machine)) % (2**32))
    times = pd.date_range(end=datetime.now(), periods=48, freq="30min")
    cfg = MACHINES[machine]
    history = pd.DataFrame({
        "Time": times,
        "Temperature": cfg["temp"] + np.linspace(0, cfg["temp"] * .03, 48)
        + rng.normal(0, 1, 48),
        "Oil pressure": cfg["oil"] + rng.normal(0, .08, 48),
        "Vibration": cfg["vib"] + rng.normal(0, .03, 48),
    })

    fig = go.Figure()
    for column in ["Temperature", "Oil pressure", "Vibration"]:
        fig.add_trace(go.Scatter(
            x=history["Time"], y=history[column],
            mode="lines", name=column,
        ))
    fig.update_layout(
        title="Last 24-hour sensor trend",
        height=380,
        margin=dict(l=10, r=10, t=45, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)

    render_explanation(a)


def page_maintenance(assessments: Dict[str, Dict]) -> None:
    st.title("🛠️ Closed-loop Maintenance")
    st.caption("Prediction becomes an operational task instead of a passive alert.")

    if not st.session_state.work_orders:
        st.info("No work orders yet. Create one from the Alerts page.")
    else:
        for index, order in enumerate(st.session_state.work_orders):
            with st.container(border=True):
                st.write(
                    f"**{order['machine']}** · {order['fault']} · "
                    f"Technician: **{order['technician']}**"
                )
                st.write(
                    f"Spare part: {order['part']} · Status: {order['status']} · "
                    f"Estimated avoided loss: ₹{order['avoided_loss']:,}"
                )
                if order["status"] != "Closed":
                    if st.button("Close work order", key=f"close_{index}"):
                        order["status"] = "Closed"
                        st.success("Work order closed.")
                        st.rerun()

    st.subheader("Spare-part readiness")
    inventory_rows = []
    for part, item in INVENTORY.items():
        inventory_rows.append({
            "Part": part,
            "Available": item["available"],
            "Reorder level": item["reorder"],
            "Status": "Reorder required"
            if item["available"] <= item["reorder"] else "Ready",
        })
    st.dataframe(pd.DataFrame(inventory_rows), use_container_width=True, hide_index=True)


def page_risk_analytics(assessments: Dict[str, Dict]) -> None:
    st.title("📊 Risk & Business")
    rows = []
    for machine, a in assessments.items():
        rows.append({
            "Machine": machine,
            "Risk score": a["risk_score"],
            "Health": a["health_score"],
            "Hourly downtime cost": MACHINES[machine]["hourly_loss"],
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    fig = go.Figure(go.Bar(
        x=df["Machine"], y=df["Risk score"],
        text=df["Risk score"], textposition="outside",
    ))
    fig.update_layout(
        title="Current explainable risk score by machine",
        yaxis_title="Risk score",
        yaxis_range=[0, 110],
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

    total_saved = sum(int(i["saved"]) for i in st.session_state.incidents)
    st.metric("Estimated downtime loss avoided", f"₹{total_saved:,}")
    st.caption(
        "The avoided-loss value is a transparent demo estimate based on machine "
        "criticality and the simulated maintenance window."
    )


def page_incidents() -> None:
    st.title("📋 Incident History")
    df = pd.DataFrame(st.session_state.incidents)
    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Export incident history",
        data=csv,
        file_name="industrial_guardian_incidents.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------
# 7. MAIN NAVIGATION
# ---------------------------------------------------------------------

def main() -> None:
    st.session_state.tick += 1

    with st.sidebar:
        st.title("🛡️ Industrial Guardian")
        st.caption("SIH prototype · predictive maintenance")
        pages = [
            "Mission Control",
            "Intelligent Alerts",
            "Explainable AI",
            "Machine Detail",
            "Closed-loop Maintenance",
            "Risk Analytics",
            "Incident History",
        ]
        st.session_state.page = st.radio(
            "Navigation",
            pages,
            index=pages.index(st.session_state.page),
        )

        st.divider()
        st.markdown("**Architecture**")
        st.write("Sensor → Edge gateway → Local AI → Dashboard")
        st.success("No external cloud required for this demo.")

        if st.button("Refresh live data"):
            st.rerun()

    assessments = all_assessments()
    page = st.session_state.page

    if page == "Mission Control":
        page_mission_control(assessments)
    elif page == "Intelligent Alerts":
        page_alerts(assessments)
    elif page == "Explainable AI":
        page_explainable_ai(assessments)
    elif page == "Machine Detail":
        page_machine_detail(assessments)
    elif page == "Closed-loop Maintenance":
        page_maintenance(assessments)
    elif page == "Risk Analytics":
        page_risk_analytics(assessments)
    elif page == "Incident History":
        page_incidents()


if __name__ == "__main__":
    main()
