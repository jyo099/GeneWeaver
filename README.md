# GeneWeaver: GPU-Accelerated CRISPR Alignment Engine

High-throughput REST API and CUDA/NumPy vectorised sequence alignment service designed for rapid off-target detection in CRISPR-Cas9 guide RNA (gRNA) workflows.

## Architecture Overview
- **API Layer:** Asynchronous FastAPI service with OpenAPI documentation.
- **Alignment Engine:** Parallelised Hamming distance and mismatch scoring kernels.
- **Persistence & Caching:** PostgreSQL job tracking and Redis reference genome indexing.