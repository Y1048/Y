"""Atomic simulation seed delivery; no DDS imports in this helper."""
import json
import os
from pathlib import Path
import sys
import tempfile

SCRIPTS=Path(__file__).resolve().parents[2]/"MuJoCo_G1_Controller/scripts"
if str(SCRIPTS) not in sys.path:sys.path.insert(0,str(SCRIPTS))
from g1_lowstate_seed import ReadSeed

class SeedWriter:
    """Owns a new seed path in a caller-reserved per-session directory."""
    def __init__(self,path,session,names):
        self.path=Path(path);self.session=session;self.names=list(names)
        if not session or not session.strip():raise ValueError("session")
        if self.path.exists():raise FileExistsError(self.path)
        self.last_receipt=None

    def invalidate(self):
        self.path.unlink(missing_ok=True)

    def write(self,packed,received_at_unix_s,now):
        temporary=None
        try:
            if self.last_receipt is not None and received_at_unix_s<=self.last_receipt:
                raise ValueError("non_increasing_seed_receipt")
            seed=dict(schema="g1.mink.lowstate_seed.v1",session_id=self.session,
                joint_names=self.names,received_at_unix_s=received_at_unix_s,
                representation="sdk_crc_packed_le2092_b95a5304",packed_hex=packed.hex())
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",
                    dir=self.path.parent,prefix=".seed-",suffix=".tmp",delete=False) as f:
                temporary=Path(f.name)
                json.dump(seed,f,allow_nan=False);f.flush();os.fsync(f.fileno())
            ReadSeed(temporary,self.session,self.names,now=now)
            os.replace(temporary,self.path)
            self.last_receipt=received_at_unix_s
        except Exception:
            self.invalidate()
            raise
        finally:
            if temporary is not None:temporary.unlink(missing_ok=True)
