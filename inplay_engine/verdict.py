"""
inplay_engine/verdict.py
=========================
In-play decision engine. Takes a WPResult and returns:
  ADD    — place additional bet now (edge > threshold)
  HOLD   — sit on existing position, no action
  HEDGE  — lay existing bet to lock in profit
  EXIT   — close position early (situation changed)

Also calculates:
  - Additional stake for ADD
  - Lay stake for HEDGE (Betfair Green All calculation)
  - Expected P&L for each action
"""

import math, os, sys
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
from wp_lookup import MatchState, WPResult, lookup

# ── Thresholds ────────────────────────────────────────────────
ADD_EDGE_MIN      = 0.06    # need 6%+ edge to ADD (blended_wp - implied_wp)
HEDGE_ODDS_MAX    = 1.28    # GREEN UP when batting team odds drop below this
EXIT_EDGE_MIN     = -0.10   # EXIT if we're 10%+ wrong (situation changed badly)
HOLD_EDGE_MAX     = 0.05    # below 5% edge = HOLD (not worth acting)
MIN_SAMPLE_ADD    = 20      # don't ADD if sample size below this
WICKET_OVERREACT_WINDOW = 8 # balls after a wicket where overreaction most likely

@dataclass
class InPlayDecision:
    verdict:        str        # ADD / HOLD / HEDGE / EXIT
    reason:         str
    confidence:     str        # high / medium / low
    # position summary
    pre_match_stake: float
    pre_match_odds:  float
    pre_match_team:  str
    current_odds:    float
    # if ADD
    add_stake:      float = 0.0
    add_odds:       float = 0.0
    add_ev_pct:     float = 0.0
    add_profit_if_win: float = 0.0
    # if HEDGE
    lay_stake:      float = 0.0    # stake to lay on Betfair
    guaranteed_profit: float = 0.0  # locked in regardless of result
    # P&L scenarios
    pnl_if_batting_wins:  float = 0.0
    pnl_if_batting_loses: float = 0.0
    # risk
    daily_cap_remaining: float = 0.0
    total_exposure:       float = 0.0
    # breakdown
    wp_result:      Optional[WPResult] = None

def kelly_stake(wp: float, odds: float, bankroll: float, phase: int) -> float:
    """Quarter/Eighth Kelly stake."""
    b = odds - 1
    q = 1 - wp
    kf = max(0, (b * wp - q) / b)
    frac = 0.25 if phase == 1 else 0.125
    return round(bankroll * kf * frac, 2)

def hedge_lay_stake(back_stake: float, back_odds: float,
                    current_odds: float) -> tuple[float, float]:
    """
    Calculate Betfair Green All lay stake.
    Returns (lay_stake, guaranteed_profit_per_£1_stake).

    If you backed at 2.08 for £199, and odds are now 1.20:
    Lay stake = (back_stake × back_odds) / current_odds
    = (199 × 2.08) / 1.20 = 344.9 → lay £344.9

    Profit if batting team wins:  back_profit - lay_profit
    Profit if batting team loses: lay_stake - back_stake (net)
    """
    lay_stake = round((back_stake * back_odds) / current_odds, 2)
    # After green-up: profit is same either way
    profit_win  = round(back_stake * (back_odds - 1) - lay_stake * (current_odds - 1), 2)
    profit_lose = round(lay_stake - back_stake, 2)
    # These should be approximately equal
    guaranteed  = round(min(profit_win, profit_lose), 2)
    return lay_stake, guaranteed

def decide(state: MatchState) -> InPlayDecision:
    """
    Main entry point. Returns an InPlayDecision.
    """
    # Get win probability
    wp = lookup(state)

    phase = state.phase
    bankroll = state.bankroll
    daily_cap = round(bankroll * 0.05, 2)
    already_staked = state.pre_match_stake
    remaining_cap = max(0, daily_cap - already_staked)

    # Pre-match bet is on batting team or bowling team?
    pre_on_batting = (state.pre_match_team == state.batting_team)

    # P&L scenarios for current position only
    pnl_win  = round(state.pre_match_stake * (state.pre_match_odds - 1), 2) if pre_on_batting else \
                round(-state.pre_match_stake, 2)
    pnl_lose = round(-state.pre_match_stake, 2) if pre_on_batting else \
                round(state.pre_match_stake * (state.pre_match_odds - 1), 2)

    # ── HEDGE check ───────────────────────────────────────────
    # If betting team is winning heavily and odds collapsed
    if (pre_on_batting and state.betfair_odds <= HEDGE_ODDS_MAX
            and state.pre_match_stake > 0):
        lay_stake, guaranteed = hedge_lay_stake(
            state.pre_match_stake, state.pre_match_odds, state.betfair_odds
        )
        return InPlayDecision(
            verdict     = "HEDGE",
            reason      = (
                f"Odds collapsed to {state.betfair_odds} "
                f"(threshold {HEDGE_ODDS_MAX}). "
                f"Green up now — lock in €{guaranteed:.2f} guaranteed profit "
                f"regardless of result. Lay €{lay_stake:.2f} on Betfair."
            ),
            confidence  = "high",
            pre_match_stake = state.pre_match_stake,
            pre_match_odds  = state.pre_match_odds,
            pre_match_team  = state.pre_match_team,
            current_odds    = state.betfair_odds,
            lay_stake       = lay_stake,
            guaranteed_profit = guaranteed,
            pnl_if_batting_wins  = guaranteed,
            pnl_if_batting_loses = guaranteed,
            daily_cap_remaining  = remaining_cap,
            total_exposure       = already_staked,
            wp_result       = wp,
        )

    # ── EXIT check ────────────────────────────────────────────
    # If we bet on batting team but model now says they're big underdogs
    # AND market hasn't moved (so we can't hedge)
    if pre_on_batting and wp.edge < EXIT_EDGE_MIN:
        exit_reason = (
            f"Model WP dropped to {wp.blended_wp:.1%} "
            f"but market implies {wp.implied_wp:.1%}. "
            f"Gap: {wp.edge:+.1%} — situation fundamentally changed. "
            f"Exit now to limit loss rather than ride to the end."
        )
        return InPlayDecision(
            verdict     = "EXIT",
            reason      = exit_reason,
            confidence  = "medium",
            pre_match_stake = state.pre_match_stake,
            pre_match_odds  = state.pre_match_odds,
            pre_match_team  = state.pre_match_team,
            current_odds    = state.betfair_odds,
            pnl_if_batting_wins  = pnl_win,
            pnl_if_batting_loses = pnl_lose,
            daily_cap_remaining  = remaining_cap,
            total_exposure       = already_staked,
            wp_result       = wp,
        )

    # ── ADD check ─────────────────────────────────────────────
    can_add = (
        wp.edge >= ADD_EDGE_MIN
        and remaining_cap >= 10          # at least €10 capacity
        and wp.sample_size >= MIN_SAMPLE_ADD
        and not wp.fallback_used         # don't ADD on WASP fallback
        and (wp.balls_remaining > 10 if state.format in ("T20","T20I","100b")
             else wp.balls_remaining > 60)  # enough balls left
    )

    if can_add:
        # Kelly-size the additional bet
        add_stake = min(
            kelly_stake(wp.blended_wp, state.betfair_odds, bankroll, phase),
            remaining_cap
        )
        add_ev = round((wp.blended_wp * state.betfair_odds - 1) * 100, 1)
        add_profit = round(add_stake * (state.betfair_odds - 1), 2)

        total_exp = round(already_staked + add_stake, 2)
        pnl_win_total  = round(pnl_win + add_profit, 2)
        pnl_lose_total = round(pnl_lose - add_stake, 2)

        conf = wp.confidence if isinstance(wp.confidence, str) else "medium"
        conf_label = "high" if wp.sample_size >= 50 and wp.edge > 0.08 else "medium"

        return InPlayDecision(
            verdict     = "ADD",
            reason      = (
                f"Edge: {wp.edge:+.1%} (model {wp.blended_wp:.1%} vs "
                f"market {wp.implied_wp:.1%}). "
                f"Sample: {wp.sample_size} matches. "
                f"EV: {add_ev:+.1f}%. "
                f"Daily cap remaining: €{remaining_cap:.2f}."
            ),
            confidence  = conf_label,
            pre_match_stake = state.pre_match_stake,
            pre_match_odds  = state.pre_match_odds,
            pre_match_team  = state.pre_match_team,
            current_odds    = state.betfair_odds,
            add_stake       = add_stake,
            add_odds        = state.betfair_odds,
            add_ev_pct      = add_ev,
            add_profit_if_win = add_profit,
            pnl_if_batting_wins  = pnl_win_total,
            pnl_if_batting_loses = pnl_lose_total,
            daily_cap_remaining  = remaining_cap,
            total_exposure       = total_exp,
            wp_result       = wp,
        )

    # ── HOLD (default) ────────────────────────────────────────
    if wp.edge < 0:
        hold_reason = (
            f"Market {wp.implied_wp:.1%} > model {wp.blended_wp:.1%}. "
            f"No edge to add. Pre-match position valid — sit tight."
        )
    elif wp.fallback_used:
        hold_reason = (
            f"Edge {wp.edge:+.1%} but using WASP fallback "
            f"(thin data for this state). Don't ADD on uncertain data."
        )
    elif wp.sample_size < MIN_SAMPLE_ADD:
        hold_reason = (
            f"Edge {wp.edge:+.1%} but only {wp.sample_size} historical matches "
            f"in this state. Need {MIN_SAMPLE_ADD}+ to act. HOLD."
        )
    else:
        hold_reason = (
            f"Edge {wp.edge:+.1%} — below ADD threshold of "
            f"{ADD_EDGE_MIN:.0%}. Model: {wp.blended_wp:.1%}, "
            f"Market: {wp.implied_wp:.1%}. No action required."
        )

    return InPlayDecision(
        verdict     = "HOLD",
        reason      = hold_reason,
        confidence  = "high",
        pre_match_stake = state.pre_match_stake,
        pre_match_odds  = state.pre_match_odds,
        pre_match_team  = state.pre_match_team,
        current_odds    = state.betfair_odds,
        pnl_if_batting_wins  = pnl_win,
        pnl_if_batting_loses = pnl_lose,
        daily_cap_remaining  = remaining_cap,
        total_exposure       = already_staked,
        wp_result       = wp,
    )

def print_decision(d: InPlayDecision):
    icons = {"ADD":"✅","HOLD":"⏸","HEDGE":"🔄","EXIT":"🛑"}
    colours = {"ADD":"WIN","HOLD":"INFO","HEDGE":"INFO","EXIT":"EXIT"}
    print(f"\n  {'─'*55}")
    print(f"  {icons.get(d.verdict,'?')} IN-PLAY VERDICT: {d.verdict}")
    print(f"  {'─'*55}")
    print(f"  Reason: {d.reason}")
    print(f"  Confidence: {d.confidence.upper()}")
    print()
    if d.verdict == "ADD":
        print(f"  ADD €{d.add_stake:.2f} on {d.pre_match_team} @ {d.add_odds}")
        print(f"  EV: {d.add_ev_pct:+.1f}%")
        print(f"  Total exposure: €{d.total_exposure:.2f} "
              f"(cap remaining after: €{d.daily_cap_remaining - d.add_stake:.2f})")
        print(f"  Combined P&L:")
        print(f"    If batting team wins:  +€{d.pnl_if_batting_wins:.2f}")
        print(f"    If batting team loses: -€{abs(d.pnl_if_batting_loses):.2f}")
    elif d.verdict == "HEDGE":
        print(f"  Lay €{d.lay_stake:.2f} on Betfair (Green All)")
        print(f"  Guaranteed profit: €{d.guaranteed_profit:.2f} ✓")
        print(f"  (No matter what happens, you lock in €{d.guaranteed_profit:.2f})")
    elif d.verdict == "EXIT":
        print(f"  Exit pre-match position now")
        print(f"  Current P&L if batting wins: +€{d.pnl_if_batting_wins:.2f}")
        print(f"  Current P&L if batting loses: -€{abs(d.pnl_if_batting_loses):.2f}")
    else:  # HOLD
        print(f"  Keep pre-match bet at €{d.pre_match_stake:.2f} @ {d.pre_match_odds}")
        print(f"  Do nothing. Let the match play out.")
        print(f"  P&L if batting wins:  +€{d.pnl_if_batting_wins:.2f}")
        print(f"  P&L if batting loses: -€{abs(d.pnl_if_batting_loses):.2f}")

    if d.wp_result:
        wp = d.wp_result
        print(f"\n  WP breakdown:")
        print(f"    Historical: {wp.historical_wp:.1%}  ELO: {wp.elo_wp:.1%}  "
              f"Blended: {wp.blended_wp:.1%}  Market: {wp.implied_wp:.1%}")

if __name__ == "__main__":
    # Test all 4 verdicts

    print("="*58)
    print("  IN-PLAY VERDICT ENGINE — TEST CASES")
    print("="*58)

    # 1. MI London 51/3 chasing 144 in 56 balls — should HOLD
    s1 = MatchState("T20", 2, "MI London", "Sunrisers Leeds",
                    44, 51, 3, 144, betfair_odds=2.95,
                    pre_match_stake=199, pre_match_odds=1.95,
                    pre_match_team="MI London", bankroll=5334, phase=1)
    print("\nTest 1: MI London 51/3, 56 balls left, Betfair 2.95")
    d1 = decide(s1)
    print_decision(d1)

    # 2. After wicket falls, market overreacts — should ADD
    s2 = MatchState("ODI", 2, "India", "England",
                    150, 120, 4, 260, betfair_odds=2.80,
                    pre_match_stake=167, pre_match_odds=2.08,
                    pre_match_team="India", bankroll=5500, phase=1)
    print("\nTest 2: India 120/4 chasing 260, 150 balls left, Betfair 2.80 (overreaction?)")
    d2 = decide(s2)
    print_decision(d2)

    # 3. Team cruising — should HEDGE
    s3 = MatchState("T20", 2, "MI London", "Sunrisers Leeds",
                    100, 130, 1, 144, betfair_odds=1.10,
                    pre_match_stake=199, pre_match_odds=1.95,
                    pre_match_team="MI London", bankroll=5334, phase=1)
    print("\nTest 3: MI London 130/1, 14 runs to win in 20 balls, Betfair 1.10")
    d3 = decide(s3)
    print_decision(d3)

    # 4. Batting team collapsing — should EXIT
    s4 = MatchState("T20I", 2, "India", "England",
                    90, 60, 8, 165, betfair_odds=6.00,
                    pre_match_stake=167, pre_match_odds=2.08,
                    pre_match_team="India", bankroll=5500, phase=1)
    print("\nTest 4: India 60/8 chasing 165 in 30 balls, Betfair 6.00")
    d4 = decide(s4)
    print_decision(d4)
