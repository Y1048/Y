"""Offline, hash-pinned patch preparation; never deploys or runs the actuator."""
from pathlib import Path
import argparse
import difflib
import hashlib

BASE_SHA256 = '882c661dba7478519ea5dab0cd4cd57c7fb2da58cc5b32514dc476eb5706d311'

def instrument(raw: bytes) -> str:
    # SSH source is LF; Windows retrieval may have translated CRLF only.
    raw = raw.replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise ValueError('onboard source changed; inspect and rebase explicitly')
    text = raw.decode('utf-8').replace('\r\n', '\n')
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('non-unique instrumentation anchor: ' + old[:70])
        text = text.replace(old, new)
    replace('#include "external_controller_bridge.hpp"', '#include "external_controller_bridge.hpp"\n#include "groot_command_observer.hpp"')
    replace('bool try_snapshot(LowState* state, double* age_ms) const noexcept {',
            'bool try_snapshot(LowState* state, double* age_ms,\n                    std::int64_t* receipt_ns = nullptr) const noexcept {')
    replace('      *state = state_;', '      *state = state_;\n      if (receipt_ns) *receipt_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(received_.time_since_epoch()).count();')
    replace('struct DesiredCommand {\n', 'struct DesiredCommand {\n  groot_external::CommandSnapshot observed_input{};\n  std::int64_t input_observed_ns{0};\n')
    replace('  StateReader& reader_;', '  groot_observer::Logger command_observer_;\n  StateReader& reader_;')
    replace('          const bool have_state = reader_.try_snapshot(&state, &age_ms);',
            '          std::int64_t state_received_ns = 0;\n          const bool have_state = reader_.try_snapshot(&state, &age_ms, &state_received_ns);')
    replace('          publisher_->Write(command);\n          write_count_.fetch_add(1);', '''          const auto observed_write_begin = groot_observer::monotonic_ns();
          publisher_->Write(command);
          const auto observed_write_end = groot_observer::monotonic_ns();
          write_count_.fetch_add(1);
          // Observe const snapshots only, after the existing Write returns.
          if (command_observer_.enabled()) {
            groot_observer::Sample sample;
            sample.writer_sequence = write_count_.load();
            sample.input_sequence = desired.observed_input.seq;
            sample.input_source_timestamp = desired.observed_input.source_timestamp;
            sample.input_valid = desired.observed_input.valid;
            sample.arms_specified = desired.observed_input.arms_specified;
            sample.arms_active = desired.observed_input.arms_active;
            sample.input_observed_ns = desired.input_observed_ns;
            sample.target_created_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(desired.created.time_since_epoch()).count();
            sample.state_received_ns = state_received_ns;
            sample.state_available = have_state;
            sample.write_begin_ns = observed_write_begin;
            sample.write_end_ns = observed_write_end;
            sample.safe_stand = safe_stand_.load();
            sample.damping = damping_.load();
            sample.received_arm_q = desired.observed_input.arm_position;
            sample.target_q = desired.target;
            for (std::size_t i=0; i<kDofs; ++i) {
              const auto& motor = command.motor_cmd()[i];
              sample.sent_q[i]=motor.q(); sample.sent_dq[i]=motor.dq();
              sample.kp[i]=motor.kp(); sample.kd[i]=motor.kd();
              sample.tau_ff[i]=motor.tau();
              sample.measured_q[i]=state.motor_state()[i].q();
              sample.measured_dq[i]=state.motor_state()[i].dq();
              sample.tau_est[i]=state.motor_state()[i].tau_est();
            }
            command_observer_.observe(sample);
          }''')
    replace('      if (external) {\n        const groot_external::CommandSnapshot snapshot =',
            '      groot_external::CommandSnapshot observed_input{};\n      std::int64_t input_observed_ns = 0;\n      if (external) {\n        const groot_external::CommandSnapshot snapshot =')
    replace('            external->command_snapshot();\n        command = snapshot.velocity;',
            '            external->command_snapshot();\n        observed_input = snapshot;\n        input_observed_ns = groot_observer::monotonic_ns();\n        command = snapshot.velocity;')
    replace('      desired.created = Clock::now();\n      desired.target = hold_target;',
            '      desired.created = Clock::now();\n      desired.observed_input = observed_input;\n      desired.input_observed_ns = input_observed_ns;\n      desired.target = hold_target;')
    return text

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    if args.output.exists():
        raise ValueError('output already exists; refusing overwrite')
    raw=args.source.read_bytes()
    result=instrument(raw)
    original=raw.decode('utf-8').replace('\r\n','\n')
    patch=''.join(difflib.unified_diff(original.splitlines(True),result.splitlines(True),
                  'a/src/g1_balance_actuator.cpp','b/src/g1_balance_actuator.cpp'))
    args.output.mkdir(parents=True)
    (args.output/'groot_command_observer.patch').write_text(patch,encoding='utf-8')
    (args.output/'g1_balance_actuator.cpp').write_text(result,encoding='utf-8')
    (args.output/'groot_command_observer.hpp').write_bytes(Path(__file__).with_name('groot_command_observer.hpp').read_bytes())
    print('OFFLINE ONLY: prepared source/header/patch; not deployed or executed.')

if __name__=='__main__': main()
