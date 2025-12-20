#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Dec 20 10:32:06 2025

@author: normanhjellegjerde
"""

pairs = ("PNC", "BAC") # Change this

    
class Strategy:
    def __init__(self, **kwargs):
        self.s1 = pairs[0]
        self.s2 = pairs[1]

        self.lookback = int(kwargs.get("lookback", 600))   # minutes  (10 hours)
        self.entry_z = float(kwargs.get("entry_z", 1.0))

        self.state = 0  # -1 short spread, 0 flat, +1 long spread
        self.leg = 0    # which leg to place next when entering/exiting

        self.q1 = float(kwargs.get("q1", 1))  # shares of s1 per leg
        # q2 is sized each time from k

    def generate_signal(self, team, bars, current_prices):
        d1 = bars.get(self.s1)
        d2 = bars.get(self.s2)
        if d1 is None or d2 is None:
            return None

        c1 = d1.get("close") or []
        c2 = d2.get("close") or []
        if len(c1) < self.lookback or len(c2) < self.lookback:
            return None

        c1 = [float(x) for x in c1[-self.lookback:] if x is not None]
        c2 = [float(x) for x in c2[-self.lookback:] if x is not None]
        n = min(len(c1), len(c2))
        if n < 50:
            return None 
        c1 = c1[-n:]
        c2 = c2[-n:]

        # k = cov(x,y)/var(x)
        mx = sum(c2) / n
        my = sum(c1) / n
        varx = sum((x - mx) ** 2 for x in c2)
        if varx <= 0:
            return None
        cov = sum((c2[i] - mx) * (c1[i] - my) for i in range(n))
        k = cov / varx
        if k == 0:
            return None

        # --- spread + z-score ---
        spread = [c1[i] - k * c2[i] for i in range(n)]
        m = sum(spread) / n
        v = sum((x - m) ** 2 for x in spread) / max(1, n - 1)
        s = v ** 0.5
        if s <= 1e-9:
            return None
        z = (spread[-1] - m) / s

        # --- prices (use current_prices first like example) ---
        p1 = current_prices.get(self.s1)
        p2 = current_prices.get(self.s2)
        if p1 is None:
            p1 = c1[-1]
        if p2 is None:
            p2 = c2[-1]
        p1 = float(p1)
        p2 = float(p2)
        if p1 <= 0 or p2 <= 0:
            return None

        # --- decide desired state ---
        desired = self.state
        if z >= self.entry_z:
            desired = -1  # short spread: sell s1, buy s2
        elif z <= -self.entry_z:
            desired = +1  # long spread: buy s1, sell s2
        else:
            # exit at zero-cross
            if self.state == +1 and z >= 0:
                desired = 0
            if self.state == -1 and z <= 0:
                desired = 0

        # If no change, do nothing
        if desired == self.state:
            return None

        # --- size second leg from k (simple) ---
        q1 = self.q1
        q2 = abs(k) * q1  # crude hedge sizing; works as a starting point

        # --- place ONE order per minute by alternating legs ---
        # entering long spread (+1): buy s1, sell s2
        # entering short spread (-1): sell s1, buy s2
        # exiting to 0: flatten by reversing current state

        action1 = None
        action2 = None

        if desired == +1:
            action1 = "buy"
            action2 = "sell"
        elif desired == -1:
            action1 = "sell"
            action2 = "buy"
        else:
            # exit: reverse current position
            if self.state == +1:
                action1 = "sell"
                action2 = "buy"
            elif self.state == -1:
                action1 = "buy"
                action2 = "sell"
            else:
                return None

        # alternate leg 0 then 1
        if self.leg == 0:
            self.leg = 1
            self.state = desired
            return {
                "symbol": self.s1,
                "action": action1,
                "quantity": float(q1),
                "price": float(p1),
                "order_type": "market",
                "time_in_force": "day",
                "reason": f"z={z:.2f}, k={k:.3f}, leg1",
            }
        else:
            self.leg = 0
            self.state = desired
            return {
                "symbol": self.s2,
                "action": action2,
                "quantity": float(q2),
                "price": float(p2),
                "order_type": "market",
                "time_in_force": "day",
                "reason": f"z={z:.2f}, k={k:.3f}, leg2",
            }
