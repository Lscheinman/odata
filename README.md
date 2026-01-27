# Generic SAP OData Proxy (FastAPI)

This project exposes a **generic, schema-agnostic HTTP API** for querying SAP OData services.
It does **not** hardcode entity sets, fields, or services. Where SAP allows it, metadata is discovered dynamically.

The proxy is designed for:
- debugging
- analytics
- agents (LLMs, planners, maintenance copilots)
- internal tooling

⚠️ This is a **power tool**. Treat access accordingly.

---

## 1. Prerequisites

- Python **3.10+**
- Network access to your SAP system
- An SAP user with OData authorization
- (Optional) VPN access to SAP

---

## 2. Project layout (minimal)

```
.
├── main.py
├── client_odata.py
├── session_odata.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 3. Install dependencies

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install requirements:

```bash
pip install -r requirements.txt
```

---

## 4. Environment configuration

Copy the example env file:

```bash
cp .env.example .env
```

### Example `.env.example`

```env
SAP_ODATA_BASE_URL=https://your-sap-host/sap/opu/odata/sap/
SAP_CLIENT=100

SAP_USERNAME=YOUR_SAP_USERNAME
SAP_PASSWORD=YOUR_SAP_PASSWORD

FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000

ODATA_PROXY_API_KEY=
```

Notes:
- `ODATA_PROXY_API_KEY` protects **this proxy**, not SAP.
- Leave it empty for local debugging.

---

## 5. Starting the server (debug mode)

Run:

```bash
python main.py
```

Swagger UI:

```
http://localhost:8000/docs
```

---

## 6. Core API endpoints

### Query any entity set

```
GET /odata/{service}/{entity_set}
```

Example:

```
GET /odata/API_EQUIPMENT/EquipmentSet?$top=5
```

---

### Discover entity sets in a service

```
GET /discover/entity-sets?service=API_EQUIPMENT
```

---

### Discover fields for an entity set

```
GET /discover/fields?service=API_EQUIPMENT&entity_set=EquipmentSet
```

---

### Discover all services (best-effort)

```
GET /discover/services
```

This may fail depending on SAP system configuration. This is normal.

---

## 7. Authentication model

### SAP authentication
Handled internally (cookies, CSRF, session reuse).

### Proxy authentication (optional)
If `ODATA_PROXY_API_KEY` is set, clients must send:

```
X-API-Key: <value>
```

---

## 8. What this proxy does NOT do

- No schema invention
- No caching
- No business logic
- No authorization bypass

It is transparent plumbing.

---

## 9. Security warning

Do not expose publicly without:
- API key
- HTTPS
- Read-only SAP user
- Rate limiting

---

## 10. Next steps

- Safe query mode
- Metadata caching
- LLM-oriented query validation
