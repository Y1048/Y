"""Local stdin/stdout CPU worker. No socket, SDK or robot access."""
import gc
import io
import json
import sys
import time
import torch
from offline_policy_adapter import ReadVerifiedPolicy
from replay_cpp_receiver_log import ROOT

torch.set_num_threads(1)
model=torch.jit.load(io.BytesIO(ReadVerifiedPolicy(
    ROOT/"references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt")),map_location="cpu").eval()
with torch.inference_mode():
    for _ in range(10): model(torch.zeros((1,1432),dtype=torch.float32))
    print(json.dumps(dict(ready=True,warmup=10,torch_version=torch.__version__)),flush=True)
    for line in sys.stdin:
        request=json.loads(line)
        request_id=request.get('request_id') if isinstance(request,dict) else None
        obs=request['observation'] if isinstance(request,dict) else request
        events=[]
        def Observe(phase, info):
            events.append(dict(phase=phase,generation=info["generation"],at=time.perf_counter()))
        gc.callbacks.append(Observe)
        try:
            t0=time.perf_counter()
            tensor=torch.tensor([obs],dtype=torch.float32)
            t1=time.perf_counter()
            raw=model(tensor)
            t2=time.perf_counter()
            action=raw.clamp(-2,2).tolist()[0]
            t3=time.perf_counter()
        finally:
            gc.callbacks.remove(Observe)
        print(json.dumps(dict(request_id=request_id,action=action,tensor_ms=(t1-t0)*1000,
            model_ms=(t2-t1)*1000,output_ms=(t3-t2)*1000,
            total_ms=(t3-t0)*1000,gc_events=events)),flush=True)
