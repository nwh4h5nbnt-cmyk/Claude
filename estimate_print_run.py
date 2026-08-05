#!/usr/bin/env python3
"""
How many cards of each rank to print for the first rollout.

Two things decide this, and the second matters more than people expect:

  1. Drop-off  — most people who join never finish their first card.
  2. Time      — a rank takes weeks of visits to clear, so nobody can reach
                 LVL 8 in your first few months no matter how keen they are.

The second constraint is what makes high-rank cards nearly free: you cannot
need many when nobody has had time to earn them.

This simulates individual members visiting the bar, collecting stamps and
levelling up, and counts the cards actually handed out before the rollout
window closes.

    python3 estimate_print_run.py
    python3 estimate_print_run.py --signups 500 --weeks 39 --stamps-per-card 8
"""

import argparse
import random
import statistics

# --- What kind of drinker joins your scheme ---------------------------------
# Share of members, and how many visits a week each type makes. A single
# average would understate the keen minority, and it is the keen minority who
# generate demand for the high ranks.

SEGMENTS = [
    ("casual",   0.60, 0.4),
    ("regular",  0.30, 1.3),
    ("diehard",  0.10, 2.8),
]

# Chance per week that a member quietly stops caring and never comes back to
# the scheme. Compounds, so it is the main source of drop-off over time.
WEEKLY_CHURN = 0.05

# Not everyone who fills the signup form walks to the bar to collect a card.
PICKUP_RATE = 0.80

MAX_LEVEL = 10


def simulate_member(weeks_available, stamps_per_card, stamps_per_visit, rng):
    """Returns the highest level this member reaches. 0 means they never
    collected their LVL 1 card."""
    if rng.random() > PICKUP_RATE:
        return 0

    visits_per_week = rng.choices(
        [s[2] for s in SEGMENTS], weights=[s[1] for s in SEGMENTS]
    )[0]
    # Real people are not metronomes.
    visits_per_week *= rng.uniform(0.6, 1.4)

    level = 1          # collecting the first card is level 1
    stamps = 0

    for _ in range(int(weeks_available)):
        if rng.random() < WEEKLY_CHURN:
            break

        visits = rng.poisson(visits_per_week) if hasattr(rng, "poisson") else _poisson(visits_per_week, rng)
        stamps += visits * stamps_per_visit

        while stamps >= stamps_per_card and level < MAX_LEVEL:
            stamps -= stamps_per_card
            level += 1

        if level >= MAX_LEVEL:
            break

    return level


def _poisson(lam, rng):
    """Small Poisson draw, so visits arrive in clumps like real weeks do."""
    if lam <= 0:
        return 0
    import math
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1
        if k > 40:
            return k


def run(signups, weeks, stamps_per_card, stamps_per_visit, launch_share, trials, seed):
    rng = random.Random(seed)
    totals = {lvl: [] for lvl in range(1, MAX_LEVEL + 1)}

    for _ in range(trials):
        counts = {lvl: 0 for lvl in range(1, MAX_LEVEL + 1)}

        for i in range(signups):
            # Launch buzz brings a chunk of signups in the first month; the
            # rest trickle in across the window and so have less time to climb.
            if rng.random() < launch_share:
                joined_week = rng.uniform(0, 4)
            else:
                joined_week = rng.uniform(0, weeks)

            reached = simulate_member(
                max(0, weeks - joined_week), stamps_per_card, stamps_per_visit, rng
            )
            # Reaching level N means being handed one card of every level up to N.
            for lvl in range(1, reached + 1):
                counts[lvl] += 1

        for lvl in range(1, MAX_LEVEL + 1):
            totals[lvl].append(counts[lvl])

    return totals


def round_up(n):
    """Printers price in bands, and running out is far worse than overprinting."""
    if n <= 25:
        return 25
    if n <= 50:
        return 50
    for step in (25, 50, 100):
        if n <= step * 10:
            return int((n + step - 1) // step * step)
    return int((n + 99) // 100 * 100)


def main():
    p = argparse.ArgumentParser(description="Estimate first-run print quantities.")
    p.add_argument("--signups", type=int, default=250, help="Total signups over the window.")
    p.add_argument("--weeks", type=int, default=26, help="How long before you reprint.")
    p.add_argument("--stamps-per-card", type=int, default=6)
    p.add_argument("--stamps-per-visit", type=int, default=1)
    p.add_argument("--launch-share", type=float, default=0.35,
                   help="Fraction of signups arriving in the first month.")
    p.add_argument("--buffer", type=float, default=1.25,
                   help="Safety margin on top of the median. 1.25 = 25 percent spare.")
    p.add_argument("--trials", type=int, default=400)
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()

    totals = run(args.signups, args.weeks, args.stamps_per_card,
                 args.stamps_per_visit, args.launch_share, args.trials, args.seed)

    print(f"\n{args.signups} signups over {args.weeks} weeks · "
          f"{args.stamps_per_card} stamps per card · "
          f"{args.stamps_per_visit} stamp(s) per visit")
    print(f"{args.trials} simulated rollouts · {int((args.buffer - 1) * 100)}% safety buffer\n")

    print(f"{'Rank':<6}{'typical':>9}{'busy case':>11}{'PRINT':>9}   ")
    print("-" * 44)

    plan = {}
    for lvl in range(1, MAX_LEVEL + 1):
        vals = sorted(totals[lvl])
        median = statistics.median(vals)
        p90 = vals[int(0.90 * len(vals))]
        target = round_up(max(median * args.buffer, p90))
        plan[lvl] = target
        bar = "#" * min(30, int(median / max(1, args.signups) * 60))
        print(f"LVL {lvl:<3}{median:>9.0f}{p90:>11.0f}{target:>9}   {bar}")

    print("-" * 44)
    print(f"{'TOTAL':<6}{'':>9}{'':>11}{sum(plan.values()):>9}\n")

    first_wave = sum(plan[l] for l in range(1, 5))
    print(f"Print now (LVL 1-4):  {first_wave} cards")
    print(f"Print later (LVL 5+): {sum(plan.values()) - first_wave} cards — "
          f"months away, and cheap to add once you\n"
          f"                      know your real numbers.\n")


if __name__ == "__main__":
    main()
