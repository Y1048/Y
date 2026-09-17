"""Exercise the real file handle across replacement, without robot IO."""
import os
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"MuJoCo_G1_Controller/scripts"))
from g1_lowstate_seed import ReadSeedBytes

def test_open_snapshot_allows_delete_sharing(tmp_path):
    path=tmp_path/"seed.json";path.write_bytes(b"old snapshot")
    new=tmp_path/"new.json";new.write_bytes(b"new snapshot")
    if os.name!="nt":pytest.skip("Windows handle sharing regression")
    original=os.fdopen
    def ReplaceWhileOpen(fd,*args,**kwargs):
        # Windows os.replace uses different rename semantics from WSL.
        # Exercise DELETE sharing here; the WSL probe tests atomic replacement.
        try:
            path.unlink()
            os.replace(new,path)
        except BaseException:
            os.close(fd)
            raise
        return original(fd,*args,**kwargs)
    with patch("os.fdopen",side_effect=ReplaceWhileOpen):
        assert ReadSeedBytes(path)==b"old snapshot"
    assert ReadSeedBytes(path)==b"new snapshot"
    path.unlink()  # Reader closes its handle.

def test_missing_and_oversized_file(tmp_path):
    path=tmp_path/"seed.json"
    with pytest.raises(FileNotFoundError):ReadSeedBytes(path)
    path.write_bytes(b"x"*20000)
    assert len(ReadSeedBytes(path))==16385
