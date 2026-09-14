"""Compile file/ring observer only, never hardware Controller or SDK."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from sysid_capture import read_episode

ROOT=Path(__file__).resolve().parent
CODE=r'''
#include "sysid_native_observer.hpp"
#include <limits>
int main(int argc,char** argv){
 if(argc!=2)return 1;
 sysid::Ring<3> ring;sysid::Frame frame;
 if(!ring.Push(frame)||!ring.Push(frame)||ring.Push(frame))return 2;
 if(!ring.Pop(frame)||!ring.Pop(frame)||ring.Pop(frame))return 3;
 sysid::Observer sink(argv[1],"generated-session","offline fixture","generated");
 for(unsigned k=0;k<12;++k){
   frame.target_ns=1000000+k*10000;frame.write_begin_ns=frame.target_ns+100;
   frame.write_end_ns=frame.target_ns+200;frame.state_receive_ns=frame.target_ns-100;
   for(unsigned j=0;j<29;++j){frame.target_q[j]=float(j)+.125F;frame.command_q[j]=float(j)+.25F;
     frame.q[j]=float(j)+.5F;frame.dq[j]=float(j)+.75F;frame.kp[j]=40;frame.kd[j]=5;frame.status[j]=j;}
   if(!sink.Offer(frame))return 4;
 }
 const auto receipt=sink.Finish();
 if(!receipt.at("complete").get<bool>()||receipt.at("written")!=12)return 5;
 std::printf("%s\n",receipt.dump().c_str());
 try{sysid::Observer duplicate(argv[1],"id","fixture","generated");return 6;}catch(...){}
 frame.q[0]=std::numeric_limits<float>::infinity();
 try{sysid::Encode(frame,0,"id","fixture","generated");return 7;}catch(...){}
 {sysid::Observer bad(std::string(argv[1])+".invalid","id","fixture","generated");
  if(!bad.Offer(frame))return 8;
  if(bad.Finish().at("complete").get<bool>())return 9;}
 return 0;
}
'''

class NativeTests(unittest.TestCase):
    def test_ring_worker_and_python_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            d=Path(folder);cpp=d/'test.cpp';exe=d/'test';trace=d/'trace.jsonl';cpp.write_text(CODE)
            subprocess.run(['g++','-std=c++17','-Wall','-Wextra','-Werror','-pthread','-I',str(ROOT),str(cpp),'-o',str(exe)],check=True,capture_output=True)
            run=subprocess.run([str(exe),str(trace)],check=True,capture_output=True,text=True,timeout=10)
            receipt=json.loads(run.stdout);receipt['sha256']=hashlib.sha256(trace.read_bytes()).hexdigest()
            trace.with_suffix('.receipt.json').write_text(json.dumps(receipt))
            rows=read_episode(trace);self.assertEqual(len(rows),12)
            for r in rows:
                self.assertEqual(r['provenance']['kind'],'generated')
                self.assertEqual(r['acceptance'],'unknown')
                self.assertEqual(r['command_q'],[j+.25 for j in range(29)])
                self.assertEqual(r['measured_q'],[j+.5 for j in range(29)])

    def test_control_equations_and_publisher_count_unchanged(self):
        source=ROOT/'twist2_mink_cycle_trial.cpp'
        current=source.read_text()
        original=subprocess.check_output(['git','show','b6a15db:experiments/twist2_right_arm_manual/twist2_mink_cycle_trial.cpp'],cwd=ROOT,text=True)
        start='    std::array<float,kDofs> kp{},kd{};'
        end='    publisher_->Write(command);'
        a=current[current.index(start):current.index(end)]
        a=a.replace('    const auto write_begin = Clock::now();\n','')
        self.assertEqual(a,original[original.index(start):original.index(end)])
        self.assertEqual(current.count('publisher_->Write(command)'),original.count('publisher_->Write(command)'))
        self.assertIn('(void)sysid_log_->Offer(observed)',current)
        self.assertIn('detached=std::move(sysid_log_)',current)


if __name__=='__main__':unittest.main()
