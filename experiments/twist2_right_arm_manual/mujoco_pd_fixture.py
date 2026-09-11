"""Preserve the source model's parent filter when its free pelvis is fixed.

MuJoCo does not apply parent-child collision filtering when the parent's weld
root is world. Removing the root joint therefore activates assembly contacts
that the original floating-base G1 model already excluded. Recreate ONLY those
three direct parent pairs in the in-memory fixture, not all self-collisions.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

ROOT_PARENT_PAIRS = (
    ("pelvis", "left_hip_pitch_link"),
    ("pelvis", "right_hip_pitch_link"),
    ("pelvis", "waist_yaw_link"),
)


def preserve_root_parent_filter(tree: ET.Element, pelvis: ET.Element) -> None:
    flag = tree.find("./option/flag")
    if flag is not None and flag.get("filterparent") == "disable":
        raise ValueError("Source parent filter disabled; cannot assume default exclusions")
    children = {body.get("name"): body for body in pelvis.findall("body")}
    if set(children) != {child for _, child in ROOT_PARENT_PAIRS}:
        raise ValueError("Source pelvis children changed; review fixture parent filtering")
    if any(body.find("joint") is None for body in children.values()):
        raise ValueError("Expected articulated direct pelvis children")
    contact = tree.find("contact")
    if contact is None:
        contact = ET.SubElement(tree, "contact")
    if contact.findall("pair"):
        raise ValueError("Explicit geom pairs require separate collision-filter review")
    existing = {frozenset((e.get("body1"), e.get("body2"))) for e in contact.findall("exclude")}
    for parent, child in ROOT_PARENT_PAIRS:
        if frozenset((parent, child)) not in existing:
            ET.SubElement(contact, "exclude", body1=parent, body2=child)
