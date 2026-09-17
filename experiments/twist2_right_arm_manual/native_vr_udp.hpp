#pragma once
#include "native_vr_policy_adapter.hpp"
#include "native_relay_contract.hpp"
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <cstdlib>

// Linux-only ingress for the separate native draft. No publisher/mode operations.
class NativeVrUdp {
 int socket_=-1;
 in_addr source_{};
 std::string relay_token_;
public:
 NativeVrUdp(){
  const char* bind_ip=std::getenv("G1_VR_BIND_IPV4");
  const char* source_ip=std::getenv("G1_VR_SOURCE_IPV4");
  const char* port_text=std::getenv("G1_VR_UDP_PORT");
  const char* token=std::getenv("G1_VR_RELAY_TOKEN");
  if(!token||!NativeRelayTokenValid(token))throw std::runtime_error("explicit VR relay token required");
  relay_token_=token;
  if(!bind_ip||!source_ip||!port_text)throw std::runtime_error("explicit VR bind/source IPv4 and port required");
  sockaddr_in bind_address{};bind_address.sin_family=AF_INET;
  if(inet_pton(AF_INET,bind_ip,&bind_address.sin_addr)!=1||inet_pton(AF_INET,source_ip,&source_)!=1)
   throw std::runtime_error("invalid VR IPv4");
  const std::string port_string(port_text);std::size_t end=0;const int port=std::stoi(port_string,&end);
  if(end!=port_string.size()||port<1024||port>65535)throw std::runtime_error("invalid VR port");
  bind_address.sin_port=htons(static_cast<std::uint16_t>(port));
  socket_=::socket(AF_INET,SOCK_DGRAM|SOCK_NONBLOCK,0);
  if(socket_<0)throw std::runtime_error("VR socket failed");
  // No SO_REUSEADDR: a conflicting local receiver must cause startup failure.
  if(::bind(socket_,reinterpret_cast<sockaddr*>(&bind_address),sizeof(bind_address))!=0){
   ::close(socket_);socket_=-1;throw std::runtime_error("VR bind failed");
  }
 }
 NativeVrUdp(const NativeVrUdp&)=delete;
 NativeVrUdp& operator=(const NativeVrUdp&)=delete;
 ~NativeVrUdp(){if(socket_>=0)::close(socket_);}
 template<class Target,class ClockFunction> void Drain(Target& target,ClockFunction now){
  for(int n=0;n<=64;++n){
   char data[16385];sockaddr_in sender{};socklen_t length=sizeof(sender);
   const auto size=recvfrom(socket_,data,sizeof(data),0,reinterpret_cast<sockaddr*>(&sender),&length);
   if(size<0){if(errno==EAGAIN||errno==EWOULDBLOCK)return;throw std::runtime_error("VR receive failed");}
   if(n==64)throw std::runtime_error("VR receive batch overflow");
   if(sender.sin_addr.s_addr!=source_.s_addr)throw std::runtime_error("unexpected VR sender");
   const std::string payload(data,static_cast<std::size_t>(size));
   ValidateNativeRelay(payload,relay_token_);
   if(!target.Receive(payload,now()))
    throw std::runtime_error(target.Poll(now()));
  }
 }
};
