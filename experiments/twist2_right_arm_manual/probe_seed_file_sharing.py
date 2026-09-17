"""Synthetic WSL/Windows file replacement probe. No SDK, DDS or robot IO."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

def Main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--writer",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--shared-read",action="store_true")
    args=p.parse_args()
    if args.writer:
        for i in range(500):
            with tempfile.NamedTemporaryFile(dir=args.writer.parent,delete=False) as f:
                temporary=Path(f.name)
                f.write(json.dumps(dict(sequence=i,padding="x"*6000)).encode())
                f.flush();os.fsync(f.fileno())
            os.replace(temporary,args.writer)
            time.sleep(.02)
        return
    root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/"MuJoCo_G1_Controller/scripts"))
    from g1_lowstate_seed import ReadSeedBytes
    directory=Path(tempfile.mkdtemp(prefix="seed-sharing-",dir=root/"logs/test_results"))
    path=directory/"probe.json"
    def Wsl(value):return "/mnt/"+value.drive[0].lower()+value.as_posix()[2:]
    child=subprocess.Popen(["wsl","-d","Ubuntu","--","/home/user/.venvs/g1-teleop/bin/python",
        "-B",Wsl(Path(__file__).resolve()),"--writer",Wsl(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    errors={};reads=0;seen=set();first_errors=[];start=time.monotonic()
    while child.poll() is None and time.monotonic()-start<25:
        try:
            data=json.loads(ReadSeedBytes(path) if args.shared_read else path.read_bytes())
            assert data["padding"]=="x"*6000
            reads+=1;seen.add(data["sequence"])
        except FileNotFoundError:pass
        except OSError as error:
            key=f"{type(error).__name__}:{error.errno}:{getattr(error,'winerror',None)}"
            errors[key]=errors.get(key,0)+1
            if len(first_errors)<3:first_errors.append(str(error))
        time.sleep(.001)
    if child.poll() is None:child.kill()
    out,err=child.communicate(timeout=5)
    result=dict(directory=str(directory),reads=reads,unique_updates=len(seen),errors=errors,
        first_errors=first_errors,writer_exit=child.returncode,stdout=out.decode(),stderr=err.decode())
    with args.output.open("x",encoding="utf-8") as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))

if __name__=="__main__":Main()
