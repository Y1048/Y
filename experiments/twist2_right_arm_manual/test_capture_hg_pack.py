import ast
from pathlib import Path
import struct
from types import SimpleNamespace as N
import unittest
from capture_hg_readonly import Pack,FORMAT,SelectInterface

class PackingTests(unittest.TestCase):
 def test_interface_renumbering_and_fail_closed(self):
  g1=dict(ifname='eth3',operstate='UP',flags=['UP','LOWER_UP'],
          addr_info=[dict(local='192.168.123.99',prefixlen=24)])
  wifi=dict(g1,ifname='eth2',addr_info=[dict(local='192.168.133.103',prefixlen=24)])
  self.assertEqual(SelectInterface([wifi,g1]),'eth3')
  for rows in ([wifi],[g1,dict(g1,ifname='eth4')],[dict(g1,operstate='DOWN')]):
   with self.assertRaises(ValueError):SelectInterface(rows)
 def test_matches_installed_sdk_pack(self):
  source=Path(r"\\wsl.localhost\Ubuntu\home\user\unitree_sdk2_python\unitree_sdk2py\utils\crc.py").read_text()
  cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=="CRC")
  method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="__PackHGLowState")
  method.args.args[1].annotation=None
  namespace={"struct":struct}
  exec(compile(ast.Module(body=[method],type_ignores=[]),"<reviewed-sdk-pack>","exec"),namespace)
  fake=N(__packFmtHGLowState=FORMAT,__Trans=lambda b:b)
  for tick in (0,123,0xffffffff):
   state=N(version=[1,2],mode_pr=0,mode_machine=5,tick=tick,
    imu_state=N(quaternion=[1.,0.,0.,0.],gyroscope=[.1,.2,.3],accelerometer=[0.,0.,9.8],rpy=[.01,.02,.03],temperature=25),
    motor_state=[N(mode=1,q=i*.01,dq=-.1,ddq=.2,tau_est=.3,temperature=[20,21],
        vol=48.,sensor=[1,2],motorstate=0,reserve=[3,4,5,6]) for i in range(35)],
    wireless_remote=[0]*40,reserve=[0]*4,crc=123456)
   packed=Pack(state)
   self.assertEqual(len(packed),2092)
   self.assertEqual(packed,namespace["__PackHGLowState"](fake,state))
   self.assertEqual(struct.unpack_from("<I",packed,12)[0],tick)
   self.assertEqual(struct.unpack_from("<I",packed,2088)[0],123456)

if __name__=="__main__":unittest.main()
