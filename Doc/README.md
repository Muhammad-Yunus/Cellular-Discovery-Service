# Documentation Folder

This folder contains comprehensive documentation for the RTL-SDR LTE Network Discovery Web Backend project.

## Available Documents

| File | Description |
|------|-------------|
| `API.md` | Complete API reference with endpoint specifications, request/response examples, and error codes |
| `DEPLOYMENT.md` | Step-by-step deployment guide including systemd setup, environment configuration, and troubleshooting |
| `ARCHITECTURE.md` | Detailed architectural overview explaining layer responsibilities, dependency rules, and data flow |
| `CONTRIBUTING.md` (optional) | Guidelines for contributing to the project |

## Read Also

- [`AGENT.md`](../../AGENT.md) - Project specification from the original requirement
- [`requirements.txt`](../../backend/requirements.txt) - Python dependencies
- [OpenAPI Docs](http://localhost:8000/docs) - Auto-generated interactive API documentation (live server)

---

## Quick Start

```bash
# Run backend and view live docs
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Visit http://localhost:8000/docs in browser
```
