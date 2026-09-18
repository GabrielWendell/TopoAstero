# Raw tier

Raw payloads are immutable external bytes. Do not commit them. Store exact archive/product IDs,
retrieval query/time, file size, SHA-256, terms, and citation in `data/manifests/`. A changed upstream
file becomes a new manifest record even if its filename is unchanged.

