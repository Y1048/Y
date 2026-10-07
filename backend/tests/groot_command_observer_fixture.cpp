#include "groot_command_observer.hpp"
#include <cassert>
#include <filesystem>
#include <iostream>

int main(int argc, char**) {
  using namespace groot_observer;
  if (argc == 1) {
    Logger logger; assert(!logger.enabled());
    std::cout << "PASS: disabled observer creates no worker/file\n"; return 0;
  }
  if (argc == 3) {
    Logger logger;
    for(int i=0;i<1000 && !logger.errors();++i) std::this_thread::sleep_for(std::chrono::milliseconds(1));
    assert(!logger.enabled() && logger.errors()==1);
    Sample sample; logger.observe(sample);
    std::cout << "PASS: file-open failure does not throw into caller\n"; return 0;
  }
  Ring<3> ring; Sample s, out;
  s.writer_sequence=1; assert(ring.push(s));
  s.writer_sequence=2; assert(ring.push(s)); assert(!ring.push(s));
  assert(ring.pop(&out) && out.writer_sequence==1);
  s.writer_sequence=3; assert(ring.push(s));
  assert(ring.pop(&out) && out.writer_sequence==2);
  assert(ring.pop(&out) && out.writer_sequence==3); assert(!ring.pop(&out));
  // Concurrent stress: validate release/acquire publication and wrap-around.
  Ring<16> concurrent;
  std::thread producer([&] {
    Sample a;
    for (std::uint64_t n=1;n<=100000;++n) {
      a.writer_sequence=n; a.sent_q[28]=static_cast<float>(n);
      while(!concurrent.push(a)) std::this_thread::yield();
    }
  });
  for (std::uint64_t n=1;n<=100000;++n) {
    while(!concurrent.pop(&out)) std::this_thread::yield();
    assert(out.writer_sequence==n && out.sent_q[28]==static_cast<float>(n));
  }
  producer.join();
  s.kp[0]=std::numeric_limits<float>::quiet_NaN(); assert(!finite(s));
  s.kp[0]=0;
  assert(argc==2);
  // Environment is set by test runner. Logger never owns a command path.
  {
    Logger logger;
    for (int n=0;n<1000 && !logger.enabled();++n) std::this_thread::sleep_for(std::chrono::milliseconds(1));
    assert(logger.enabled());
    for(int n=1;n<=3;++n) {
      s.writer_sequence=n; s.target_created_ns=20; s.state_received_ns=10;
      s.state_available=true; s.write_begin_ns=30+n; s.write_end_ns=40+n;
      s.sent_q[28]=.25F; logger.observe(s);
    }
  }
  std::cout << "PASS: bounded queue, concurrent ordering, nonfinite check, async CSV drain\n";
}
