"""Local disk storage adapter for raw uploads."""
import hashlib
import pathlib

DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "uploads"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class StorageLocal:
    def __init__(self):
        self.base_dir = DATA_DIR

    async def save_file(self, incident_id: str, filename: str, content: bytes) -> tuple[str, str]:
        """Saves file to local disk, returns (uri, sha256_hash)."""
        sha256 = hashlib.sha256(content).hexdigest()
        inc_dir = self.base_dir / incident_id
        inc_dir.mkdir(parents=True, exist_ok=True)
        
        safe_filename = f"{sha256[:8]}_{filename}"
        file_path = inc_dir / safe_filename
        
        with open(file_path, "wb") as f:
            f.write(content)
            
        uri = f"/data/uploads/{incident_id}/{safe_filename}"
        return uri, sha256

    async def get_file(self, uri: str) -> bytes:
        relative_path = uri.lstrip("/")
        full_path = pathlib.Path(__file__).resolve().parents[2] / relative_path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {uri}")
        with open(full_path, "rb") as f:
            return f.read()
