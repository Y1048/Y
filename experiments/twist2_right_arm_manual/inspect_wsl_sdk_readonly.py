"""Read-only WSL SDK inventory. No SDK imports, DDS, robot contact or file writes."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

RELATIVE_FILES=(
 "include/unitree/idl/hg/LowState_.hpp",
 "include/unitree/idl/hg/MotorState_.hpp",
 "include/unitree/idl/hg/IMUState_.hpp",
 "unitree_sdk2py/idl/unitree_hg/msg/dds_/_LowState_.py",
 "unitree_sdk2py/idl/unitree_hg/msg/dds_/_MotorState_.py",
 "unitree_sdk2py/idl/unitree_hg/msg/dds_/_IMUState_.py",
 "unitree_sdk2py/utils/crc.py",
 "unitree_sdk2py/core/channel.py",
)
def Inspect(root):
    """Only exact source paths; no recursive walk or execution of discovered files."""
    root=Path(root)
    records=[]
    for relative in RELATIVE_FILES:
        path=root/relative
        if path.is_file():
            data=path.read_bytes()
            records.append(dict(path=str(path.resolve()),size=len(data),
                                sha256=hashlib.sha256(data).hexdigest()))
    return records

def Main():
    roots={Path("/home/user/unitree_sdk2"),Path("/home/user/unitree_sdk2_python"),
           Path("/home/user/unitree_sdk2/build"),Path("/usr/local"),Path("/usr")}
    distributions=[]
    for dist in importlib.metadata.distributions():
        name=dist.metadata.get("Name","")
        if "unitree" in name.lower() or "cyclonedds" in name.lower():
            root=Path(dist.locate_file(""))
            roots.add(root)
            distributions.append(dict(name=name,version=dist.version,root=str(root)))
            # Editable-install metadata contains a location only; do not import it.
            direct=dist.read_text("direct_url.json")
            if direct:
                from urllib.parse import urlparse,unquote
                url=urlparse(json.loads(direct).get("url",""))
                if url.scheme=="file" and url.netloc in ("","localhost"):
                    roots.add(Path(unquote(url.path)))
    sources=[]
    for root in sorted(roots,key=str):sources.extend(Inspect(root))
    network=subprocess.run(["ip","-j","address","show"],capture_output=True,text=True,timeout=5)
    if network.returncode:raise RuntimeError("ip address inspection failed")
    print(json.dumps(dict(schema="twist2.sdk_inventory.v1",platform=platform.platform(),
        distributions=distributions,inspected_roots=[str(p) for p in sorted(roots,key=str)],
        sources=sources,interfaces=json.loads(network.stdout),
        sdk_imported=False,dds_initialized=False,robot_contacted=False,
        deployment_abi_verified=False),indent=2))

if __name__=="__main__":Main()
