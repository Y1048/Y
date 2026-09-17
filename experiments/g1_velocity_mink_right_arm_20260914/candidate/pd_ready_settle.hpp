#pragma once
#include <array>
#include <cmath>
#include <stdexcept>

// Local trial defaults, not experimentally validated hardware limits.
// Only arms are assessed; existing full-body checks remain authoritative.
class PdReadySettle {
  double started=-1, previous_now=-1, previous_receipt=-1, quiet_since=-1;
  bool failed=false;
  [[noreturn]] void Fail(const char* reason) {
    failed=true;
    throw std::runtime_error(reason);
  }
public:
  static constexpr double error_limit=.10, speed_limit=.10;
  static constexpr double window=1., timeout=10., max_gap=.06;
  bool Update(double now,double receipt,const std::array<double,29>& q,
              const std::array<double,29>& dq,const std::array<double,29>& target) {
    if(failed)Fail("pd_settle_stopped");
    if(!std::isfinite(now)||!std::isfinite(receipt)||receipt<0||receipt>now||
       now<previous_now||receipt<previous_receipt)Fail("pd_settle_clock");
    previous_now=now;
    if(started<0)started=now;
    if(now-started>=timeout)Fail("pd_settle_timeout");
    if(now-receipt>max_gap)Fail("pd_settle_stale");
    bool quiet=true;
    for(int i=15;i<29;++i) {
      if(!std::isfinite(q[i])||!std::isfinite(dq[i])||!std::isfinite(target[i]))
        Fail("pd_settle_nonfinite");
      quiet=quiet&&std::abs(q[i]-target[i])<=error_limit&&std::abs(dq[i])<=speed_limit;
    }
    if(!quiet)quiet_since=-1;
    if(receipt==previous_receipt)return false;
    if(previous_receipt>=0&&receipt-previous_receipt>max_gap)quiet_since=-1;
    previous_receipt=receipt;
    if(!quiet)return false;
    if(quiet_since<0)quiet_since=receipt;
    return receipt-quiet_since>=window;
  }
};
