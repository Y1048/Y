#pragma once
#include <chrono>
#include <condition_variable>
#include <deque>
#include <fstream>
#include <functional>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>

// Disk I/O stays off the control thread. Overflow or write failure latches.
// flush() protects against process exit after flushing, not power loss.
template<class T> class PeriodicCsv {
 std::ofstream stream;
 std::function<void(std::ostream&, const T&)> encode;
 std::mutex mutex;
 std::condition_variable wake;
 std::deque<T> queue;
 std::thread worker;
 bool closing=false;
 std::string error;
 void Run() noexcept {
  try {
   auto next=std::chrono::steady_clock::now()+std::chrono::milliseconds(250);
   for(;;){
    std::deque<T> batch; bool done;
    {
     std::unique_lock<std::mutex> lock(mutex);
     wake.wait_until(lock,next,[&](){return closing||!queue.empty();});
     batch.swap(queue);done=closing;
    }
    for(const auto& item:batch)encode(stream,item);
    if(done||std::chrono::steady_clock::now()>=next){
     stream.flush();next=std::chrono::steady_clock::now()+std::chrono::milliseconds(250);
    }
    if(done){stream.close();return;}
   }
  }catch(...){std::lock_guard<std::mutex> lock(mutex);error="csv_write_failed";}
 }
public:
 PeriodicCsv(const std::string& path,const std::string& header,
             std::function<void(std::ostream&,const T&)> writer):encode(writer){
  stream.exceptions(std::ios::failbit|std::ios::badbit);
  stream.open(path);stream<<header;stream.flush();
  worker=std::thread([this](){Run();});
 }
 PeriodicCsv(const PeriodicCsv&)=delete;
 PeriodicCsv& operator=(const PeriodicCsv&)=delete;
 void Append(const T& item){
  std::lock_guard<std::mutex> lock(mutex);
  if(!error.empty())throw std::runtime_error(error);
  if(closing)throw std::runtime_error("csv_closed");
  if(queue.size()>=250){error="csv_queue_overflow";throw std::runtime_error(error);}
  queue.push_back(item);wake.notify_one();
 }
 void Finish(){
  {std::lock_guard<std::mutex> lock(mutex);closing=true;wake.notify_one();}
  if(worker.joinable())worker.join();
  std::lock_guard<std::mutex> lock(mutex);
  if(!error.empty())throw std::runtime_error(error);
 }
 ~PeriodicCsv(){try{Finish();}catch(...){}}
};
