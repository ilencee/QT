# 测试电阻选型方案 (不依赖 GUI)
import math

POWER_RATINGS = [0.125, 0.25, 0.5, 1, 2, 3, 5]
PACKAGES = {
    "0603":        {"w": 0.1,   "price": 1.0, "area": 1.0},
    "0805":        {"w": 0.125, "price": 1.3, "area": 1.8},
    "1206":        {"w": 0.25,  "price": 1.6, "area": 3.2},
    "2512":        {"w": 1.0,   "price": 4.5, "area": 7.5},
    "大功率贴片":   {"w": 2.0,   "price": 12,  "area": 16},
    "插件绕线电阻": {"w": 5.0,   "price": 6.0, "area": 22},
}
PARALLEL_PACKAGES = ("1206", "0805", "0603")


def select_power_rating(p):
    for r in POWER_RATINGS:
        if p <= r:
            return r
    return POWER_RATINGS[-1]


def select_package(rating):
    if rating <= 0.125:
        return "0603"
    if rating <= 0.25:
        return "0805"
    if rating <= 0.5:
        return "1206"
    if rating <= 1:
        return "2512"
    if rating <= 2:
        return "大功率贴片"
    return "插件绕线电阻"


def suggest_resistor_plan(p_r):
    if p_r <= 0:
        return "无需电阻"
    p_need = p_r * 2
    rating = select_power_rating(p_need)
    single_pkg = select_package(rating)
    single = PACKAGES.get(single_pkg)
    base = "1x%s (%gW)" % (single_pkg, rating)

    best = None
    for pkg in PARALLEL_PACKAGES:
        info = PACKAGES[pkg]
        n = math.ceil(p_need / info["w"])
        if not (2 <= n <= 8):
            continue
        cost = n * info["price"]
        area = n * info["area"]
        if best is None or (cost, area) < (best[3], best[4]):
            best = (pkg, n, info["w"], cost, area)
    if best is None or single is None:
        return base

    pkg, n, pw, cost, area = best
    scost, sarea = single["price"], single["area"]
    tags = []
    if cost <= scost * 0.95 and area <= sarea * 0.9:
        tags.append("更便宜更省空间")
    elif cost <= scost * 0.95:
        tags.append("更便宜")
    elif area <= sarea * 0.9:
        tags.append("更省空间")
    else:
        tags.append("成本/空间略增")
    return "%s | 替代 %dx%s 并联, 每颗 %gW (%s)" % (base, n, pkg, pw, ",".join(tags))


for p in [0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.0]:
    print("P_R=%.2fW -> %s" % (p, suggest_resistor_plan(p)))
