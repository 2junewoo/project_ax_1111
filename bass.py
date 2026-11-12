"""하트 바디 미니 베이스 기타 (4현). 바디는 base.py 의 하트를 같은 크기로 씀.

크기 기준: 하트 폭 77mm ≈ 실제 베이스 바디 폭(약 340mm)의 0.226배.
  스케일 길이(너트~브리지) 864mm → 195mm, 전체 길이 약 261mm.

출력: stl/
  - 베이스기타_바디.stl   바디 + 픽업 + 브리지 + 노브 + 바디 위 줄. 뒷면을 바닥에 놓고 출력
  - 베이스기타_넥.stl     넥 + 지판 + 프렛 + 헤드 + 줄감개 + 넥 위 줄. 뒷면을 바닥에 놓고 출력
  - 베이스기타_전체.stl   합친 모양 (미리보기·레진용, FDM이면 넥 밑에 서포트 필요)
바디 윗면의 넥 포켓에 넥 끝(힐)을 끼우면 조립됨 (볼트온 넥처럼).
바디에 빼빼로 꽂는 구멍 3개 (pepero.py 의 <종류>_세움.stl 손잡이가 들어감), 바디·헤드에 '11.11'.
줄은 지판·헤드 위에 얹혀 있거나 픽업·브리지 사이를 짧게 건너서 서포트 없이 출력 가능.

--parts 옵션: 색깔별 부품을 build/parts/ 에 따로 저장 (Blender 미리보기용).
"""
from pathlib import Path
import math
import sys

import manifold3d
import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold

from base import slab, text
from pepero import to_trimesh

ROOT = Path(__file__).parent
OUT = ROOT / "stl"

# --- 바디 ---
BODY_H = 12.0           # 바디 두께
POCKET_D = 3.0          # 넥 포켓 깊이
FIT = 0.15              # 넥-포켓 틈 (한쪽)

# --- 넥 / 지판 ---
SCALE_LEN = 195.0
BRIDGE_Y = -16.0                    # 새들(줄 받침) 위치
NUT_Y = BRIDGE_Y + SCALE_LEN        # 179
HEEL_Y = 8.0                        # 넥 끝 (바디 포켓 안)
NECK_Z0 = BODY_H - POCKET_D         # 넥 뒷면 높이 = 9
NECK_T = 5.0                        # 넥 두께
FB_T = 1.2                          # 지판 두께
FB_TOP = NECK_Z0 + NECK_T + FB_T    # 15.2
W_NUT, W_HEEL = 9.0, 14.5
FRETS = 24
HEAD_LEN = 48.0

# --- 줄 ---
STRING_R = [0.55, 0.5, 0.45, 0.4]       # E A D G
PITCH_NUT, PITCH_BRIDGE = 2.2, 4.3
POSTS_DY = [9.0, 19.0, 29.0, 39.0]      # 줄감개 위치 (너트에서, E가 가장 가까움)
POST_X = -4.5
SINK = 0.6         # 줄을 바닥면에 살짝 묻어서 붙임 (딱 닿기만 하면 메시가 갈라짐)

SEG = 32

# --- 빼빼로 꽂는 구멍 (pepero.py 의 세움 버전 손잡이 지름 6mm) ---
PEPERO_SOCKET = 9.0     # 구멍 깊이 (바디 12mm, 바닥 3mm 남김)
HOLE_R = 3.0 + 0.25
PEPERO_HOLES = {        # 하트 양쪽 볼록한 곳 + 왼쪽 아래
    "오리지널": (-22.0, 19.0),
    "아몬드": (22.0, 19.0),
    "화이트줄무늬": (-27.0, 3.0),
}
BODY_LOGO = {"scale": 0.56, "angle": -42.0, "xy": (-16.5, -9.5)}


def neck_w(y: float) -> float:
    t = (y - HEEL_Y) / (NUT_Y - HEEL_Y)
    return W_HEEL + (W_NUT - W_HEEL) * t


def neck_outline(y0: float, y1: float, extra: float = 0.0) -> CrossSection:
    ys = np.linspace(y0, y1, 12)
    right = [(neck_w(y) / 2 + extra, y) for y in ys]
    left = [(-neck_w(y) / 2 - extra, y) for y in reversed(ys)]
    return CrossSection([right + left])


def box(x0, x1, y0, y1, z0, z1) -> Manifold:
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def rounded_rect(cx, cy, wx, wy, r, z0, z1) -> Manifold:
    cs = CrossSection.square((wx - 2 * r, wy - 2 * r)).translate((cx - wx / 2 + r, cy - wy / 2 + r)).offset(r, circular_segments=SEG)
    return Manifold.extrude(cs, z1 - z0).translate((0, 0, z0))


def rod(points, r) -> Manifold:
    """점들을 잇는 둥근 막대 (구 사이 hull)."""
    balls = [Manifold.sphere(r, 16).translate(p) for p in points]
    return Manifold.batch_boolean([Manifold.batch_hull([a, b]) for a, b in zip(balls, balls[1:])],
                                  manifold3d.OpType.Add)


def string_x(i: int, y: float) -> float:
    t = (y - BRIDGE_Y) / SCALE_LEN
    pitch = PITCH_BRIDGE + (PITCH_NUT - PITCH_BRIDGE) * t
    return (i - 1.5) * pitch


def fret_y(n: int) -> float:
    return NUT_Y - SCALE_LEN * (1 - 2 ** (-n / 12))


# ---------------- 부품 ----------------

def body_wood() -> Manifold:
    pocket = Manifold.extrude(neck_outline(HEEL_Y - FIT, 60, FIT), POCKET_D + 1).translate((0, 0, NECK_Z0))
    return slab(BODY_H) - pocket - pepero_holes()


def pepero_holes() -> Manifold:
    """빼빼로 손잡이를 꽂는 구멍 (입구는 살짝 넓힘)."""
    parts = []
    for x, y in PEPERO_HOLES.values():
        parts.append(Manifold.cylinder(PEPERO_SOCKET + 1, HOLE_R, HOLE_R, SEG).translate((x, y, BODY_H - PEPERO_SOCKET)))
        parts.append(Manifold.cylinder(1.01, HOLE_R, HOLE_R + 0.8, SEG).translate((x, y, BODY_H - 1.0)))
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def pickups() -> Manifold:
    # 넥 쪽: P 픽업 (두 조각 엇갈림), 브리지 쪽: J 픽업
    p1 = rounded_rect(-3.6, 5.2, 8.0, 4.0, 1.2, BODY_H, FB_TOP)
    p2 = rounded_rect(3.6, 4.0, 8.0, 4.0, 1.2, BODY_H, FB_TOP)
    j = rounded_rect(0, -6.0, 17.0, 3.6, 1.4, BODY_H, FB_TOP)
    return p1 + p2 + j


def bridge() -> Manifold:
    plate = rounded_rect(0, BRIDGE_Y - 1.0, 19.0, 9.0, 1.5, BODY_H, BODY_H + 0.8)
    saddles = [rounded_rect(string_x(i, BRIDGE_Y), BRIDGE_Y, 3.2, 2.6, 0.6, BODY_H, FB_TOP)
               for i in range(4)]
    return plate + Manifold.batch_boolean(saddles, manifold3d.OpType.Add)


def knobs() -> Manifold:
    parts = []
    for x, y in [(17.0, -9.0), (22.5, -3.5), (28.0, 2.0)]:
        parts.append(Manifold.cylinder(2.6, 2.0, 1.7, SEG).translate((x, y, BODY_H - 0.2)))
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def body_strings() -> Manifold:
    parts = []
    for i, r in enumerate(STRING_R):
        z = FB_TOP + r * SINK
        tail_y = BRIDGE_Y - 4.0
        parts.append(rod([(string_x(i, HEEL_Y - FIT), HEEL_Y - FIT, z),
                          (string_x(i, BRIDGE_Y), BRIDGE_Y, z),
                          (string_x(i, BRIDGE_Y), tail_y, BODY_H + 0.8 + r * SINK)], r))
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def headstock_cs() -> CrossSection:
    n = NUT_Y
    pts = [(-W_NUT / 2, n), (W_NUT / 2, n), (5.5, n + 10), (7.5, n + 30), (8.5, n + 42),
           (6.5, n + HEAD_LEN), (-2.5, n + HEAD_LEN - 1), (-7.5, n + 41), (-7.5, n + 8)]
    return CrossSection([pts]).offset(1.5).offset(-2.5).offset(1.0)


def neck_wood() -> Manifold:
    neck = Manifold.extrude(neck_outline(HEEL_Y, NUT_Y + 0.5), NECK_T).translate((0, 0, NECK_Z0))
    head = Manifold.extrude(headstock_cs(), NECK_T).translate((0, 0, NECK_Z0))
    return neck + head


def fretboard() -> Manifold:
    fb = Manifold.extrude(neck_outline(HEEL_Y, NUT_Y), FB_T).translate((0, 0, NECK_Z0 + NECK_T))
    # 포지션 마크: 얕게 판 점 (미리보기에선 흰색)
    return fb - inlays(depth_only=True)


def inlay_points():
    pts = []
    for n in (3, 5, 7, 9, 15, 17, 19, 21):
        pts.append((0.0, (fret_y(n - 1) + fret_y(n)) / 2))
    for n in (12, 24):
        y = (fret_y(n - 1) + fret_y(n)) / 2
        pts += [(-neck_w(y) / 4, y), (neck_w(y) / 4, y)]
    return pts


def inlays(depth_only: bool = False) -> Manifold:
    parts = [Manifold.cylinder(0.31 if depth_only else 0.3, 0.8, 0.8, SEG)
             .translate((x, y, FB_TOP - 0.3)) for x, y in inlay_points()]
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def frets() -> Manifold:
    parts = []
    for n in range(1, FRETS + 1):
        y = fret_y(n)
        w = neck_w(y) - 0.4
        parts.append(box(-w / 2, w / 2, y - 0.25, y + 0.25, FB_TOP - 0.2, FB_TOP + 0.35))
    nut = box(-W_NUT / 2 + 0.2, W_NUT / 2 - 0.2, NUT_Y, NUT_Y + 1.5, NECK_Z0 + NECK_T - 0.1, FB_TOP + 0.9)
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add) + nut


def tuners() -> Manifold:
    head_top = NECK_Z0 + NECK_T
    parts = []
    for dy in POSTS_DY:
        y = NUT_Y + dy
        parts.append(Manifold.cylinder(3.5, 1.2, 1.2, SEG).translate((POST_X, y, head_top - 0.1)))
        parts.append(Manifold.cylinder(0.6, 1.8, 1.8, SEG).translate((POST_X, y, head_top - 0.1)))  # 와셔
        # 손잡이: 헤드 옆으로 납작하게 (바닥에 붙어서 출력)
        stem = box(-11.0, -6.5, y - 0.8, y + 0.8, NECK_Z0, NECK_Z0 + 2.4)
        key = Manifold.extrude(CrossSection.circle(2.6, SEG).scale((1.0, 1.35)), 2.4).translate((-13.0, y, NECK_Z0))
        parts += [stem, key]
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def neck_strings() -> Manifold:
    head_top = NECK_Z0 + NECK_T
    parts = []
    for i, r in enumerate(STRING_R):
        z = FB_TOP + r * SINK
        post_y = NUT_Y + POSTS_DY[i]
        down_y = NUT_Y + 5.0
        down_x = string_x(i, NUT_Y) + (POST_X - string_x(i, NUT_Y)) * 5.0 / POSTS_DY[i]
        parts.append(rod([(string_x(i, HEEL_Y), HEEL_Y, z),
                          (string_x(i, NUT_Y + 1.5), NUT_Y + 1.5, z),
                          (down_x, down_y, head_top + r * SINK),
                          (POST_X + 1.2, post_y, head_top + r * SINK)], r))
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def logo(scale: float, angle: float, x: float, y: float, surface_z: float, raise_: float) -> Manifold:
    """'11.11' 글자를 (x, y) 가운데에 놓고 surface_z 면에서 raise_ 만큼 튀어나오게."""
    t = text()
    lo, hi = t.bounding_box()[:3], t.bounding_box()[3:]
    c = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]
    t = t.translate((-c[0], -c[1], -c[2])).scale((scale, scale, 1.0)).rotate((0, 0, angle))
    h = hi[2] - lo[2]
    return t.translate((x, y, surface_z + raise_ - h))


def head_logo() -> Manifold:
    """헤드에 '11.11' (세로로, 0.4mm 튀어나옴)."""
    return logo(0.6, 90, 3.0, NUT_Y + 30.0, NECK_Z0 + NECK_T, 0.4)


def body_logo() -> Manifold:
    """바디 왼쪽 아래 가장자리를 따라 '11.11' (0.6mm 튀어나옴)."""
    return logo(BODY_LOGO["scale"], BODY_LOGO["angle"], *BODY_LOGO["xy"], BODY_H, 0.6)


# ---------------- 조립 / 저장 ----------------

def parts() -> dict[str, Manifold]:
    return {
        "바디": body_wood(),
        "픽업": pickups(),
        "금속_바디": bridge() + knobs(),
        "줄_바디": body_strings(),
        "넥": neck_wood(),
        "지판": fretboard(),
        "인레이": inlays(),
        "금속_넥": frets() + tuners(),
        "줄_넥": neck_strings(),
        "로고_바디": body_logo(),
        "로고_넥": head_logo(),
    }


def save(m: Manifold, path: Path) -> trimesh.Trimesh:
    t = to_trimesh(m)
    t.export(path)
    ext = t.bounds[1] - t.bounds[0]
    print(f"{path.stem:14s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:5.1f} mm  "
          f"watertight={t.is_watertight}  {t.volume / 1000:5.2f} cm³")
    return t


def main() -> None:
    p = parts()
    add = lambda names: Manifold.batch_boolean([p[n] for n in names], manifold3d.OpType.Add)
    body = add(["바디", "픽업", "금속_바디", "줄_바디", "로고_바디"])
    neck = add(["넥", "지판", "금속_넥", "줄_넥", "로고_넥"])
    OUT.mkdir(exist_ok=True)
    save(body, OUT / "베이스기타_바디.stl")
    # 넥은 뒷면이 바닥(z=0)에 오게 내려서 저장
    save(neck.translate((0, 0, -NECK_Z0)), OUT / "베이스기타_넥.stl")
    save(body + neck, OUT / "베이스기타_전체.stl")

    # 조립 확인: 넥이 바디에 박혀 들어가지 않는지 (포켓 틈만큼 떨어져 있어야 함)
    clash = (p["바디"] ^ p["넥"]).volume()
    print(f"넥-바디 겹침 부피: {clash:.3f} mm³")

    if "--parts" in sys.argv:
        d = ROOT / "build" / "parts"
        d.mkdir(parents=True, exist_ok=True)
        for name, m in p.items():
            to_trimesh(m).export(d / f"{name}.stl")
        print("부품별 저장:", d)


if __name__ == "__main__":
    main()
