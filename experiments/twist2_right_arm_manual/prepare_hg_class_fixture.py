"""Create test-only official class declarations without DDS traits/runtime."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def Prepare():
    folder=Path(__file__).parent/'vendor/unitree_hg_reference'
    manifest=json.loads((folder/'manifest.json').read_text())
    output='#pragma once\n#include <utility>\n'
    for name in ('IMUState_.hpp','MotorState_.hpp','LowState_.hpp'):
        raw=(folder/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['files'][name]['sha256']:
            raise ValueError('SDK source hash mismatch')
        text=raw.decode().split('#include "dds/topic/TopicTraits.hpp"')[0]
        output+='\n'.join(x for x in text.splitlines() if not x.startswith('#include "unitree/'))+'\n#endif\n'
    path=ROOT/'logs/test_results/hg_classes_only.hpp'
    path.write_text(output,encoding='utf-8')
    return path

if __name__=='__main__': print(Prepare())
