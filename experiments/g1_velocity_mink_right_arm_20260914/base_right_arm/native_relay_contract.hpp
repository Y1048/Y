#pragma once
#include "vendor/json.hpp"
#include <string>

// Per-run relay binding, not cryptographic authentication. IP filtering is separate.
inline bool NativeRelayTokenValid(const std::string& token){
 if(token.size()<16||token.size()>128)return false;
 for(unsigned char c:token)
  if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')))return false;
 return true;
}
inline void ValidateNativeRelay(const std::string& payload,const std::string& token){
 if(!NativeRelayTokenValid(token))throw std::runtime_error("invalid relay token configuration");
 const auto value=nlohmann::json::parse(payload);
 if(value.at("command_provenance")!="live_mink"||value.value("simulation_only",false))
  throw std::runtime_error("native_live_provenance_required");
 if(value.at("relay_token")!=token)throw std::runtime_error("native_relay_token_mismatch");
 const auto session=value.at("session_id").get<std::string>();
 if(session.empty()||session.rfind("replay-",0)==0)
  throw std::runtime_error("native_live_session_required");
 // Full schema, duplicate keys, order and timeout checks remain in the adapter.
}
