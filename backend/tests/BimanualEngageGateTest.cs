using System;
class BimanualEngageGateTest {
 static void Main() {
  int tests = 0;
  for (int bits=0; bits<64; ++bits) {
   bool fresh=(bits&1)!=0, ready=(bits&2)!=0, tracked=(bits&4)!=0,
    zones=(bits&8)!=0, pinch=(bits&16)!=0, leave=(bits&32)!=0;
   bool expected=bits==15;
   foreach(float l in new[]{0f,.99f,1f}) foreach(float r in new[]{0f,.99f,1f}) {
    bool actual=G1BimanualSimulationSender.CanEngage(fresh,ready,tracked,zones,pinch,leave,l,r);
    if(actual!=(expected && l==1 && r==1)) throw new Exception("gate mismatch "+bits);
    tests++;
   }
  }
  if(G1BimanualSimulationSender.TrackedMarkerDiameter!=.075f || G1BimanualSimulationSender.TargetMarkerDiameter!=.070f) throw new Exception("marker dimensions");
  double until=G1BimanualSimulationSender.RememberReady(10,double.NegativeInfinity,true,1);
  if(until!=14) throw new Exception("initial memory");
  if(G1BimanualSimulationSender.RememberReady(11,until,true,0)!=14) throw new Exception("sequential memory");
  if(!double.IsNegativeInfinity(G1BimanualSimulationSender.RememberReady(11,until,false,1))) throw new Exception("invalid tracking memory");
  if(15<until) throw new Exception("expiration");
  if(G1BimanualSimulationSender.CanEngage(true,true,true,false,false,false,1,1)) throw new Exception("must recheck current zones");
  for(int bits=0; bits<16; ++bits) {
   bool ready=(bits&1)!=0, tracked=(bits&2)!=0, zones=(bits&4)!=0, pinch=(bits&8)!=0;
   bool expected=ready && tracked && !zones && !pinch;
   if(G1BimanualSimulationSender.CanClearMustLeave(ready,tracked,zones,pinch)!=expected)
    throw new Exception("leave-zone clear mismatch "+bits);
   tests++;
  }
  Console.WriteLine("PASS: readiness memory, invalidation, expiration and final position gate");
  Console.WriteLine("PASS: "+tests+" engage gate cases; shared marker dimensions");
 }
}
