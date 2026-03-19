# sage-solver-cloud

Runtime UI and job state server for the Sage optimization platform.

sage-solver-cloud is the visual and persistence layer of Sage. It is not used directly — it is accessed through sage-solver-mcp, which writes job state as blobs and registers live UI pages. Claude and other MCP clients interact with Sage through sage-solver-mcp; sage-solver-cloud serves the job dashboard and persists solver state across sessions.

## Architecture

```
sage-solver-mcp → sage-solver-cloud (this server)
                         ↓
                   blob store (job state, notifications, indexes)
                   page server (job dashboard, detail views)
                   REST API (read/write by mcp layer)
```

## Quick start

```bash
pip install -e ".[dev]"
python -m sage_cloud

# Server starts at http://localhost:8000
# API key is printed to stdout on first run
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| SAGE_CLOUD_HOST | localhost | Bind address |
| SAGE_CLOUD_PORT | 8000 | HTTP port |
| SAGE_CLOUD_API_KEY | auto-generated | API key for X-Sage-Key header |
| SAGE_CLOUD_BLOB_DIR | ~/.sage-cloud/artifacts | Blob storage directory |
| SAGE_CLOUD_LOG_LEVEL | INFO | Log verbosity |

## Integration

sage-solver-mcp connects via HTTP using the X-Sage-Key header.
See SCHEMAS.md for the job blob schema.
See API.md for the endpoint reference.

## Pages

| Route | Description |
|---|---|
| / | Sage Cloud landing page |
| /apps/sage-jobs | Solver job dashboard |
| /apps/sage-artifacts | Artifact browser |

## Development

```bash
pytest tests/ -v   # 260+ tests
```
