"""Shared body-pair collision policy for G1 right-arm analysis and control."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


PairKey = tuple[int, int]
PairStatus = str


def canonical_pair(first_body: int, second_body: int) -> PairKey:
    first = int(first_body)
    second = int(second_body)
    return (first, second) if first <= second else (second, first)


@dataclass(frozen=True)
class ContactPairObservation:
    first_body: int
    second_body: int
    status: PairStatus

    @property
    def pair(self) -> PairKey:
        return canonical_pair(self.first_body, self.second_body)


class RightArmCollisionPolicy:
    """Classify MuJoCo contacts that are relevant to right-arm safety.

    Direct parent-child body pairs are ignored because connected robot links can
    share or overlap collision geometry around a joint without representing an
    actionable self-collision. Non-adjacent right-arm contacts and contacts
    between the right arm and another robot body remain collision events.
    """

    def __init__(
        self,
        *,
        right_arm_body_ids: Iterable[int],
        robot_body_ids: Iterable[int],
        body_parent_ids: Iterable[int],
        ignored_pairs: Iterable[PairKey] = (),
    ) -> None:
        self.right_arm_body_ids = {int(value) for value in right_arm_body_ids}
        self.robot_body_ids = {int(value) for value in robot_body_ids}
        self.body_parent_ids = tuple(int(value) for value in body_parent_ids)
        self.ignored_pairs = {canonical_pair(*pair) for pair in ignored_pairs}

    @classmethod
    def from_model(
        cls,
        model,
        right_arm_body_ids: Iterable[int],
        *,
        ignored_pairs: Iterable[PairKey] = (),
    ) -> "RightArmCollisionPolicy":
        robot_body_ids = range(1, int(model.nbody))
        return cls(
            right_arm_body_ids=right_arm_body_ids,
            robot_body_ids=robot_body_ids,
            body_parent_ids=model.body_parentid,
            ignored_pairs=ignored_pairs,
        )

    def are_directly_connected(self, first_body: int, second_body: int) -> bool:
        first = int(first_body)
        second = int(second_body)
        if first == second:
            return True
        if first < 0 or second < 0:
            return False
        if first >= len(self.body_parent_ids) or second >= len(self.body_parent_ids):
            return False
        return (
            self.body_parent_ids[first] == second
            or self.body_parent_ids[second] == first
        )

    def classify_body_pair(self, first_body: int, second_body: int) -> PairStatus:
        first = int(first_body)
        second = int(second_body)
        pair = canonical_pair(first, second)

        if first == second:
            return "same_body"
        if pair in self.ignored_pairs:
            return "ignored_pair"

        first_is_arm = first in self.right_arm_body_ids
        second_is_arm = second in self.right_arm_body_ids
        if not (first_is_arm or second_is_arm):
            return "irrelevant"

        if first not in self.robot_body_ids or second not in self.robot_body_ids:
            return "environment"

        if self.are_directly_connected(first, second):
            return "adjacent"

        if first_is_arm and second_is_arm:
            return "right_arm_self_collision"
        return "right_arm_robot_collision"

    def observe_contacts(self, model, data) -> list[ContactPairObservation]:
        observations: list[ContactPairObservation] = []
        for contact_index in range(int(data.ncon)):
            contact = data.contact[contact_index]
            first_body = int(model.geom_bodyid[contact.geom1])
            second_body = int(model.geom_bodyid[contact.geom2])
            observations.append(
                ContactPairObservation(
                    first_body=first_body,
                    second_body=second_body,
                    status=self.classify_body_pair(first_body, second_body),
                )
            )
        return observations

    def has_collision(self, model, data) -> bool:
        return any(
            observation.status
            in {"right_arm_self_collision", "right_arm_robot_collision"}
            for observation in self.observe_contacts(model, data)
        )

    def count_contacts(self, model, data) -> Counter[tuple[PairKey, PairStatus]]:
        counter: Counter[tuple[PairKey, PairStatus]] = Counter()
        for observation in self.observe_contacts(model, data):
            counter[(observation.pair, observation.status)] += 1
        return counter
