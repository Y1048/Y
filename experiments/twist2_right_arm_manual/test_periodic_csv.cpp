#include "periodic_csv.hpp"
#include <filesystem>
#include <iostream>
#include <sstream>
#include <atomic>
void check(bool value,const char* why){if(!value)throw std::runtime_error(why);}
std::string read(const std::filesystem::path& p){std::ifstream f(p);std::ostringstream s;s<<f.rdbuf();return s.str();}
int main(int argc,char** argv){try{
 check(argc==2,"temporary output directory required");
 const std::filesystem::path dir=argv[1];
 const auto path=dir/"periodic.csv";
 {
  PeriodicCsv<int> log(path.string(),"n\n",[](auto& s,int n){s<<n<<'\n';});
  log.Append(1);log.Append(2);
  bool visible=false;
  for(int n=0;n<100;++n){if(read(path)=="n\n1\n2\n"){visible=true;break;}std::this_thread::sleep_for(std::chrono::milliseconds(10));}
  check(visible,"not flushed while logger alive");
  log.Append(3);log.Finish();check(read(path)=="n\n1\n2\n3\n","finish lost data");
 }
 bool open_failed=false;
 try{PeriodicCsv<int> bad((dir/"missing"/"x.csv").string(),"n\n",[](auto&,int){});}catch(...){open_failed=true;}
 check(open_failed,"open failure ignored");
 {
  PeriodicCsv<int> bad((dir/"failure.csv").string(),"n\n",[](auto& s,int){s.setstate(std::ios::badbit);});
  bad.Append(1);bool caught=false;try{bad.Finish();}catch(...){caught=true;}
  check(caught,"write failure ignored");
 }
 {
  std::atomic<bool> entered{false},release{false};
  PeriodicCsv<int> full((dir/"full.csv").string(),"n\n",[&](auto& s,int n){entered=true;while(!release.load())std::this_thread::yield();s<<n<<'\n';});
  full.Append(0);while(!entered.load())std::this_thread::yield();
  for(int n=0;n<250;++n)full.Append(n);
  bool caught=false;try{full.Append(999);}catch(...){caught=true;}
  release=true;
  bool latched=false;try{full.Finish();}catch(...){latched=true;}
  check(caught&&latched,"overflow not latched");
 }
 std::cout<<"PASS periodic visibility, final drain, open/write failure, bounded overflow latch\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
