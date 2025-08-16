# logic.py — генератор графика (минимально жизнеспособный, без внешних библиотек оптимизации)
from datetime import date, timedelta
import calendar
from collections import Counter

WD_NAMES = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]

def month_days(year: int, month: int):
    cal = calendar.Calendar(firstweekday=0)
    return [d for d in cal.itermonthdates(year, month) if d.month == month]

def generate_schedule(employees, year: int, month: int, absences=None, fixed_events=None):
    """
    employees: list of dicts: {"name": str, "part_time": bool, "can_duty": bool, "can_support": bool}
    return: schedule[name][day] = {"shift": '1'|'2'|'В'|..., "duty": bool}
    """
    days = month_days(year, month)
    num_weekend_days = len([d for d in days if d.weekday()>=5])

    names = [e["name"] for e in employees]
    part_time = {e["name"]: e.get("part_time", False) for e in employees}
    can_duty = {e["name"]: e.get("can_duty", True) for e in employees}

    # назначаем выходные: у каждого ровно столько, сколько суббот+воскресений в месяце
    # стараемся давать парами, разносим по неделям
    weeks = []
    d0 = date(year, month, 1)
    start = d0 - timedelta(days=d0.weekday())
    end = date(year, month, calendar.monthrange(year, month)[1])
    cur = start
    while cur <= end:
        weeks.append([cur + timedelta(days=i) for i in range(7)])
        cur += timedelta(days=7)

    pair_patterns = [(5,6),(6,0),(1,2),(3,4),(0,1),(2,3),(4,5)]
    off = {n: set() for n in names}
    for i, n in enumerate(names):
        pairs_needed = num_weekend_days // 2
        pattern_idx = i % len(pair_patterns)
        assigned_pairs = 0
        for w in weeks:
            if assigned_pairs >= pairs_needed: break
            dow1, dow2 = pair_patterns[(pattern_idx + assigned_pairs) % len(pair_patterns)]
            d1, d2 = w[dow1], w[dow2]
            if d1.month == month and d2.month == month:
                off[n].add(d1); off[n].add(d2)
                assigned_pairs += 1
        # добить недостающее
        if len(off[n]) < num_weekend_days:
            need = num_weekend_days - len(off[n])
            candidates = [d for d in days if d not in off[n]]
            candidates.sort(key=lambda d: (d.weekday()>=5, d.day))
            off[n].update(candidates[:need])
        # подрезать излишки
        if len(off[n]) > num_weekend_days:
            off[n] = set(sorted(off[n])[:num_weekend_days])

    # результат
    result = {n: {d.day: {"shift":"", "duty":False} for d in days} for n in names}

    shift2_count = Counter()
    duty_count = Counter()
    prev_shift = {n: None for n in names}
    prev_duty2 = {n: False for n in names}

    for d in days:
        available = [n for n in names if d not in off[n]]
        regs = [n for n in available if not part_time.get(n, False)]
        parts = [n for n in available if part_time.get(n, False)]

        # целим ~45% во 2-ю смену, минимум 2 (если регуляров меньше — сколько есть)
        target_s2 = min(len(regs), max(2, round(0.45 * len(available)))) if regs else 0
        regs_sorted = sorted(regs, key=lambda n: (shift2_count[n], 1 if prev_shift[n]=="2" else 0))
        s2 = regs_sorted[:target_s2]
        s1 = [n for n in regs if n not in s2] + parts

        # если во 2-й 1 человек — перекинем из первой
        if len(s2) == 1 and len(s1) > 1:
            s1_regs = [n for n in s1 if n in regs]
            if s1_regs:
                move = sorted(s1_regs, key=lambda n: shift2_count[n])[0]
                s2.append(move); s1.remove(move)

        # смены
        for n in s1: result[n][d.day]["shift"] = "1"
        for n in s2: result[n][d.day]["shift"] = "2"; shift2_count[n]+=1
        for n in names:
            if d in off[n]: result[n][d.day]["shift"] = "В"

        # дежурства: по одному на смену среди «регуляров»
        duty1_candidates = [n for n in s1 if (n in regs) and can_duty.get(n, True) and not prev_duty2[n]]
        duty1_candidates.sort(key=lambda n: (duty_count[n], 1 if prev_shift[n]=="2" else 0))
        if duty1_candidates:
            n1 = duty1_candidates[0]
            result[n1][d.day]["duty"] = True; duty_count[n1]+=1

        duty2_candidates = [n for n in s2 if (n in regs) and can_duty.get(n, True)]
        duty2_candidates.sort(key=lambda n: (duty_count[n], 1 if prev_shift[n]=="2" else 0))
        if duty2_candidates:
            n2 = duty2_candidates[0]
            result[n2][d.day]["duty"] = True; duty_count[n2]+=1
            prev_duty2 = {k: False for k in prev_duty2}
            prev_duty2[n2] = True

        for n in names: prev_shift[n] = result[n][d.day]["shift"]

    return result
