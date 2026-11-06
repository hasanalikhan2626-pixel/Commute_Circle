"""Evaluation surveys (proposal 14.8, 15).

* SUS: the standard 10-item System Usability Scale (Brooke, 1996), answers 1-5.
  Score = 2.5 x (sum over odd items of (a - 1) + sum over even items of (5 - a)), 0-100.
* Safety: three 1-5 statements about feeling safe; score = mean.
* Spending: monthly commute spend in PKR, once when joining ("before") and again after at
  least two weeks of travelling with a circle ("after").
"""
from __future__ import annotations

SUS_ITEMS = (
    "I think that I would like to use CommuteCircle frequently.",
    "I found CommuteCircle unnecessarily complex.",
    "I thought CommuteCircle was easy to use.",
    "I think that I would need the support of a technical person to be able to use CommuteCircle.",
    "I found the various functions in CommuteCircle were well integrated.",
    "I thought there was too much inconsistency in CommuteCircle.",
    "I would imagine that most people would learn to use CommuteCircle very quickly.",
    "I found CommuteCircle very cumbersome to use.",
    "I felt very confident using CommuteCircle.",
    "I needed to learn a lot of things before I could get going with CommuteCircle.",
)
SAFETY_ITEMS = (
    "I feel safe travelling to campus with my circle.",
    "I feel safer with my circle than taking a ride-hailing car alone.",
    "Knowing everyone is a verified BIC student makes me more willing to carpool.",
)
AFTER_MIN_TRIPS = 5  # SUS, safety and "after" spending are asked once a student has this many trips


def sus_score(answers: list[int]) -> float:
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS needs 10 answers from 1 to 5")
    odd = sum(a - 1 for a in answers[0::2])
    even = sum(5 - a for a in answers[1::2])
    return (odd + even) * 2.5


def safety_score(answers: list[int]) -> float:
    if len(answers) != len(SAFETY_ITEMS) or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError(f"Safety needs {len(SAFETY_ITEMS)} answers from 1 to 5")
    return round(sum(answers) / len(answers), 2)
