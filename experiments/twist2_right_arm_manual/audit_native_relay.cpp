// Offline stdin audit only: no sockets, SDK, publisher or robot connection.
#include "native_relay_contract.hpp"
#include <iostream>

int main(int argc,char** argv){
 try{
  if(argc!=2)throw std::runtime_error("expected relay token argument");
  if(!NativeRelayTokenValid(argv[1]))throw std::runtime_error("invalid token");
  std::string packet;std::size_t count=0;
  while(std::getline(std::cin,packet)){
   ValidateNativeRelay(packet,argv[1]);++count;
  }
  if(!count)throw std::runtime_error("empty capture");
  std::cout<<"PASS native relay contract packets="<<count<<'\n';
 }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
