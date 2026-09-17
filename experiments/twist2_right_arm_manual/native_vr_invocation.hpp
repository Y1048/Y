#pragma once
#include <string_view>
// SDK-free entry contract shared by the initial guard and mode selection.
inline bool NativeVrInvocationValid(int argc,const char* const* argv,bool relative_candidate){
  if(argc!=7||!argv)return false;
  for(int i=0;i<argc;++i)if(!argv[i])return false;
  return std::string_view(argv[3])=="--enable-actuation"&&
    std::string_view(argv[4])=="--policy-seconds"&&
    std::string_view(argv[6])==(relative_candidate?"--vr-relative-candidate":"--vr-right-arm");
}
