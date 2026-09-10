#pragma once
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

struct PdGainOptions {
  std::array<float,29> kp,kd;
};
// Parse before Policy or Controller construction. Limits are input bounds,
// not certified gains. Only PD mode can override right-arm joints 22..28.
inline PdGainOptions ParsePdGainOptions(int argc,const char* const* argv,
    const std::array<float,29>& kp,const std::array<float,29>& kd) {
  PdGainOptions result{kp,kd};
  if(argc<7)throw std::runtime_error("missing trial mode");
  const std::string mode=argv[6];
  const bool pd=mode=="--pd-reach-trial"||mode=="--pd-sweep-trial";
  const bool handoff_only=mode=="--handoff-only-trial";
  if(!pd&&!handoff_only&&mode!="--udp-right-arm")
    throw std::runtime_error("unknown trial mode");
  if(handoff_only&&argc!=7)
    throw std::runtime_error("handoff-only trial does not accept PD gains");
  if(!pd && argc!=7)throw std::runtime_error("PD gains require --pd-reach-trial");
  std::array<bool,29> seen_p{},seen_d{};
  const auto value_of=[](const std::string& text,bool p){
    std::size_t count=0;
    const float value=std::stof(text,&count);
    if(count!=text.size()||!std::isfinite(value)||value<(p?1.F:.1F)||value>(p?100.F:20.F))
      throw std::runtime_error("PD gain input bounds: Kp 1..100, Kd 0.1..20 (not validated hardware gains)");
    return value;
  };
  for(int i=7;i<argc;i+=2){
    const std::string name=argv[i];
    if(i+1>=argc)throw std::runtime_error("missing PD gain value");
    if(name=="--pd-gain"){
      const std::string text=argv[i+1];
      const auto first=text.find(':'),last=text.rfind(':');
      if(first==std::string::npos||first==last||text.find(':',first+1)!=last)
        throw std::runtime_error("--pd-gain requires joint:Kp:Kd");
      const auto joint_text=text.substr(0,first);
      if(joint_text.empty()||joint_text.find_first_not_of("0123456789")!=std::string::npos)
        throw std::runtime_error("invalid PD joint");
      const int joint=std::stoi(joint_text);
      if(joint<22||joint>28)throw std::runtime_error("PD joint must be 22..28");
      if(seen_p[joint]||seen_d[joint])throw std::runtime_error("duplicate PD joint or shoulder alias conflict");
      result.kp[joint]=value_of(text.substr(first+1,last-first-1),true);
      result.kd[joint]=value_of(text.substr(last+1),false);
      seen_p[joint]=seen_d[joint]=true;
      continue;
    }
    const bool p=name=="--right-shoulder-kp",d=name=="--right-shoulder-kd";
    if(!p&&!d)throw std::runtime_error("unknown PD gain option: "+name);
    if((p&&seen_p[22])||(d&&seen_d[22]))throw std::runtime_error("duplicate PD gain option");
    const float value=value_of(argv[i+1],p);
    if(p){result.kp[22]=value;seen_p[22]=true;}
    else {result.kd[22]=value;seen_d[22]=true;}
  }
  return result;
}
