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
  if(G1BimanualSimulationSender.TrackedMarkerDiameter!=.060f || G1BimanualSimulationSender.TargetMarkerDiameter!=.055f) throw new Exception("marker dimensions");
  Console.WriteLine("PASS: "+tests+" engage gate cases; shared marker dimensions");
 }
}
