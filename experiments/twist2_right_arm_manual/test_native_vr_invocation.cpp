#include "native_vr_invocation.hpp"
#include <cassert>
int main(){
 const char* args[]={"candidate","eth0","policy.pt","--enable-actuation","--policy-seconds","3","--vr-relative-candidate"};
 assert(NativeVrInvocationValid(7,args,true));
 assert(!NativeVrInvocationValid(7,args,false));
 args[6]="--vr-right-arm";
 assert(NativeVrInvocationValid(7,args,false));
 assert(!NativeVrInvocationValid(7,args,true));
 args[3]="--dry-run";assert(!NativeVrInvocationValid(7,args,false));
 args[3]="--enable-actuation";args[4]="--wrong";assert(!NativeVrInvocationValid(7,args,false));
 args[4]="--policy-seconds";args[6]="--right-shoulder-forward-deg";assert(!NativeVrInvocationValid(7,args,false));
 assert(!NativeVrInvocationValid(0,nullptr,true));
 assert(!NativeVrInvocationValid(6,args,true));
 args[6]=nullptr;assert(!NativeVrInvocationValid(7,args,true));
}
