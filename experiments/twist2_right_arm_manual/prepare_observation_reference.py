"""Extract local reference observation code for SDK-free exact comparison tests."""
from pathlib import Path
import hashlib
import json
from prepare_hg_class_fixture import Prepare,ROOT


def PrepareObservation():
    Prepare()
    source=ROOT/'references/lower_body/twist2_deploy/cpp_g1_twist2/twist2_common.hpp'
    text=source.read_text()
    part=text[text.index('struct PolicyResult {'):text.index('inline std::array<float, kDofs> hybrid_target(')]
    prefix='''#pragma once
#include "hg_classes_only.hpp"
#include "offline_twist2_constants.hpp"
namespace reference {
using namespace offline_twist2;
using LowState=unitree_hg::msg::dds_::LowState_;
constexpr std::size_t kDofs=29,kSingleObservations=127,kMimicObservations=35,kObservations=1432,kHistory=10;
constexpr float kObservationLimit=100;
struct Policy {
 std::array<float,1432> observed{};
 std::array<float,29> infer(const std::array<float,1432>& obs,double* ms) { observed=obs;*ms=0;return {}; }
};
'''
    target=ROOT/'logs/test_results/observation_reference.hpp'
    target.write_text(prefix+part+'}\n')
    (target.parent/'observation_reference_source.json').write_text(json.dumps(dict(
        source=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        extracted='PolicyResult + ObservationHistory; fake Policy captures observation only'),indent=2)+'\n')
    return target

if __name__=='__main__': print(PrepareObservation())
