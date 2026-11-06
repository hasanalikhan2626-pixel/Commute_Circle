"""Populate the database with synthetic students for development and demos.

    python -m app.seed            # 60 students + admin
    python -m app.seed --n 200    # larger pool for algorithm benchmarks

All data is fictional. Default logins (printed at the end):
    admin@bic.edu.pk / admin12345
    student1@bic.edu.pk .. studentN@bic.edu.pk / student123
"""
from __future__ import annotations

import argparse
import random

from .areas import AREAS
from .db import Base, SessionLocal, engine
from .models import Gender, Profile, Role, User
from .security import hash_password

FIRST_F = ["Ayesha", "Fatima", "Zainab", "Hira", "Maryam", "Areeba", "Sana", "Mahnoor", "Iqra", "Alina", "Hafsa", "Noor"]
FIRST_M = ["Ahmed", "Ali", "Hamza", "Usman", "Bilal", "Saad", "Hassan", "Omar", "Faizan", "Raza", "Taha", "Zaid"]
LAST = ["Khan", "Siddiqui", "Qureshi", "Sheikh", "Hussain", "Malik", "Ansari", "Baig", "Mirza", "Raza", "Abbasi", "Shah"]
# Weight areas so some neighbourhoods are dense (realistic) and some sparse.
POPULAR = ["Gulshan-e-Iqbal", "DHA Phase 6", "PECHS", "Clifton", "North Nazimabad", "Gulistan-e-Johar",
           "Bahadurabad", "Federal B Area"]
TIMETABLES = [
    (("mon", "tue", "wed", "thu"), "08:30", "14:30"),
    (("mon", "wed", "fri"), "09:00", "15:00"),
    (("tue", "thu"), "10:00", "16:00"),
    (("mon", "tue", "wed", "thu", "fri"), "08:00", "13:00"),
    (("mon", "tue", "thu", "fri"), "11:00", "17:00"),
]


def _shift(t: str, rng: random.Random) -> str:
    h, m = map(int, t.split(":"))
    total = h * 60 + m + rng.choice([-15, 0, 0, 0, 15])
    return f"{total // 60:02d}:{total % 60:02d}"


def make_students(n: int, seed: int = 42):
    rng = random.Random(seed)
    out = []
    for i in range(1, n + 1):
        female = rng.random() < 0.5
        name = f"{rng.choice(FIRST_F if female else FIRST_M)} {rng.choice(LAST)}"
        area = rng.choice(POPULAR) if rng.random() < 0.75 else rng.choice(sorted(AREAS))
        days, arrive, leave = rng.choice(TIMETABLES)
        days = [d for d in days if rng.random() > 0.1] or list(days)
        has_car = rng.random() < 0.35
        out.append(dict(
            email=f"student{i}@bic.edu.pk", full_name=name, phone=f"+92300{rng.randrange(10**6, 10**7)}",
            profile=dict(
                area=area, gender=Gender.female if female else Gender.male,
                same_gender_only=female and rng.random() < 0.4,
                has_car=has_car, seats=rng.choice([2, 3, 4]) if has_car else 0,
                schedule={d: {"arrive": _shift(arrive, rng), "leave": leave} for d in days},
                pickup_landmark=f"Near {area} main gate",
            ),
        ))
    return out


def seed(n: int = 60, reset: bool = True) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        db.add(User(email="admin@bic.edu.pk", full_name="Transport Office", role=Role.admin,
                    password_hash=hash_password("admin12345")))
        pw = hash_password("student123")
        for s in make_students(n):
            u = User(email=s["email"], full_name=s["full_name"], phone=s["phone"], password_hash=pw)
            u.profile = Profile(**s["profile"])
            db.add(u)
        db.commit()
    finally:
        db.close()
    print(f"Seeded {n} students.\n  admin@bic.edu.pk / admin12345\n  student1..{n}@bic.edu.pk / student123")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    seed(ap.parse_args().n)
