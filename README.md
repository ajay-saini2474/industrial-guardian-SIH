# Industrial Guardian

SIH-ready explainable predictive-maintenance dashboard — built with Streamlit.

## Features
- Explainable AI risk scoring for each machine
- Alert acknowledgment and work-order workflow
- Spare-part inventory tracking
- Hindi + English technician alerts
- Incident history with CSV export

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

Note: this is a simulation/demo. Replace the sensor layer with MQTT, OPC-UA, REST, SQL, or an edge gateway for production use.
