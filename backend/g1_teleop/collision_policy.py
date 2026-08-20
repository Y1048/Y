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

    Robot links separated by at most two edges in the kinematic tree are treated
    as structural neighbors. Their collision geometry can legitimately overlap
    around joints, so those contacts are not actionable self-collisions.
    Contacts spanning three or more kinematic edges remain collision candidates.
    """

    def __init__(
        self,
        *,
        right_arm_body_ids: Iterable[int],
        robot_body_ids: Iterable[int],
        body_parent_ids: Iterable[int],
        ignored_pairs: Iterable[PairKey] = (),
        structural_neighbor_distance: int = 2,
    ) -> None:
        if structural_neighbor_distance < 1:
            raise ValueError("structural_neighbor_distance must be >= 1")
        self.right_arm_body_ids = {int(value) for value in right_arm_body_ids}
        self.robot_body_ids = {int(value) for value in robot_body_ids}
        self.body_parent_ids = tuple(int(value) for value in body_parent_ids)
        self.ignored_pairs = {canonical_pair(*pair) for pair in ignored_pairs}
        self.structural_neighbor_distance = int(structural_neighbor_distance)

    @classmethod
    def from_model(
        cls,
        model,
        right_arm_body_ids: Iterable[int],
        *,
        ignored_pairs: Iterable[PairKey] = (),
        structural_neighbor_distance: int = 2,
    ) -> "RightArmCollisionPolicy":
        robot_body_ids = range(1, int(model.nbody))
        return cls(
            right_arm_body_ids=right_arm_body_ids,
            robot_body_ids=robot_body_ids,
            body_parent_ids=model.body_parentid,
            ignored_pairs=ignored_pairs,
            structural_neighbor_distance=structural_neighbor_distance,
        )

    def _ancestor_distances(self, body_id: int) -> dict[int, int]:
        body = int(body_id)
        if body < 0 or body >= len(self.body_parent_ids):
            return {}

        distances: dict[int, int] = {}
        distance = 0
        current = body
        while current not in distances:
            distances[current] = distance
            if current == 0:
                break
            parent = self.body_parent_ids[current]
            if parent < 0 or parent >= len(self.body_parent_ids) or parent == current:
                break
            current = parent
            distance += 1
        return distances

    def kinematic_distance(self, first_body: int, second_body: int) -> int | None:
        """Return edge distance in the body tree, or None for invalid/disconnected ids."""
        first = int(first_body)
        second = int(second_body)
        first_ancestors = self._ancestor_distances(first)
        second_ancestors = self._ancestor_distances(second)
        common = set(first_ancestors).intersection(second_ancestors)
        if not common:
            return None
        return min(
            first_ancestors[ancestor] + second_ancestors[ancestor]
            for ancestor in common
        )

    def are_directly_connected(self, first_body: int, second_body: int) -> bool:
        return self.kinematic_distance(first_body, second_body) in {0, 1}

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

        distance = self.kinematic_distance(first, second)
        if distance == 1:
            return "adjacent"
        if distance is not None and distance <= self.structural_neighbor_distance:
            return "near_adjacent"

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
