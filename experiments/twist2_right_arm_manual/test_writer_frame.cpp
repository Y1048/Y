#include "writer_frame.hpp"
#include <atomic>
#include <iostream>
#include <sstream>
#include <thread>
#include <algorithm>
#include <stdexcept>
void check(bool x,const char* why){if(!x)throw std::runtime_error(why);}
int main(){try{
 WriterFrameStore store;check(!store.Read().valid,"initial frame valid");
 std::atomic<bool> done{false};
 std::thread producer([&](){for(int n=1;n<=10000;++n){WriterFrame f;f.state_tick=n;f.q.fill(static_cast<float>(n));f.target.fill(static_cast<float>(n)+.25F);store.Publish(f);}done=true;});
 bool coherent=true;std::uint64_t previous=0;
 do{const auto f=store.Read();if(f.valid){coherent=coherent&&f.sequence>=previous&&f.sequence==f.state_tick;previous=f.sequence;for(int i=0;i<29;++i)coherent=coherent&&f.q[i]==static_cast<float>(f.state_tick)&&f.target[i]==f.q[i]+.25F;}}while(!done.load());
 producer.join();check(coherent,"torn snapshot");check(store.Read().sequence==10000,"lost publication");
 std::ostringstream header,row;WriterFrameHeader(header);WriterFrameRow(row,store.Read());
 const auto h=header.str(),r=row.str();
 check(std::count(h.begin(),h.end(),',')==241,"header columns");
 check(std::count(r.begin(),r.end(),',')==241,"row columns");
 std::cout<<"PASS empty frame, 10000 coherent concurrent publications, final sequence, CSV shape\n";
}catch(const std::exception& e){std::cerr<<e.what();return 1;}}
