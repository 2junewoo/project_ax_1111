"""빼빼로 3D 모델 생성기 (11/11 빼빼로 데이).

출력: stl/ 폴더
  - <종류>.stl          한 색으로 뽑을 때 (과자+초코 합친 모양)
  - <종류>_과자.stl      두 색으로 뽑을 때 과자 부분
  - <종류>_초코.stl      두 색으로 뽑을 때 초코 부분
  - 빼빼로_세트.stl      3종을 한 판에 배치

프린터 바닥에 눕혀서 뽑도록 아랫면을 평평하게 잘라 둠 (서포트 불필요).

세워서 뽑는 버전 (이름 끝에 _세움): 손잡이 끝이 바닥, 둥근 단면이 그대로라 더 진짜 같음.
  - <종류>_세움.stl / _세움_과자.stl / _세움_초코.stl
  - 빼빼로_세트_세움.stl   3종을 25mm 간격으로 세워 배치
  키 120mm에 바닥 지름 6mm라 슬라이서에서 브림(5~8mm)을 꼭 켤 것.
"""
from pathlib import Path
import math
import random

import numpy as np
import trimesh
from manifold3d import Manifold

SEG = 48            # 원 둘레 분할 수
STICK_R = 3.0       # 과자 반지름 (mm)
STICK_LEN = 120.0   # 전체 길이
HANDLE_LEN = 30.0   # 초코 안 묻은 손잡이 길이
COAT_R = 4.0        # 초코 바깥 반지름
CENTER_Z = 2.4      # 눕혔을 때 축 높이 → 아래를 잘라 평평한 바닥 만들기
STAND_GAP = 25.0    # 세움 세트에서 막대 사이 간격 (노즐이 옆 막대를 덜 건드리게)

OUT = Path(__file__).parent / "stl"


def stick(flat_end: bool = False) -> Manifold:
    """과자 막대 (z축 방향, 0~STICK_LEN). 손잡이 끝은 살짝 둥글게.

    flat_end=True 이면 끝을 평평하게 둬서 세워 뽑을 때 바닥 접착 면적을 넓힘
    (베이스 구멍에 꽂히는 쪽이라 안 보임)."""
    if flat_end:
        return Manifold.cylinder(STICK_LEN, STICK_R, STICK_R, SEG)
    body = Manifold.cylinder(STICK_LEN - 1.0, STICK_R, STICK_R, SEG).translate((0, 0, 1.0))
    end = Manifold.cylinder(1.0, STICK_R - 0.6, STICK_R, SEG)
    return body + end


def coat_base() -> Manifold:
    """초코 코팅 기본형: 끝이 둥근 원통."""
    length = STICK_LEN - HANDLE_LEN - COAT_R * 0.5
    body = Manifold.cylinder(length, COAT_R, COAT_R, SEG).translate((0, 0, HANDLE_LEN))
    tip = Manifold.sphere(COAT_R, SEG).scale((1, 1, 0.5)).translate((0, 0, HANDLE_LEN + length))
    # 코팅 시작 부분은 살짝 경사 (초코가 흘러내린 느낌)
    lip = Manifold.cylinder(1.5, STICK_R, COAT_R, SEG).translate((0, 0, HANDLE_LEN - 1.5))
    return body + tip + lip


def almond_bumps(rng: random.Random) -> Manifold:
    """아몬드 조각: 코팅 표면에 박힌 작은 덩어리들."""
    parts = []
    for _ in range(70):
        z = rng.uniform(HANDLE_LEN + 3, STICK_LEN - 4)
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.8, 1.3)
        p = Manifold.sphere(r, 16).scale((1, 1, rng.uniform(1.2, 1.8)))
        p = p.translate((math.cos(a) * (COAT_R - 0.2), math.sin(a) * (COAT_R - 0.2), z))
        parts.append(p)
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def drizzle() -> Manifold:
    """화이트 초코 줄무늬: 코팅을 감는 나선 두 줄."""
    parts = []
    start, end = HANDLE_LEN + 2, STICK_LEN - 4
    turns = 7
    steps = 420
    for phase in (0.0, math.pi):
        for i in range(steps):
            t = i / (steps - 1)
            z = start + (end - start) * t
            a = phase + 2 * math.pi * turns * t
            s = Manifold.sphere(0.75, 12).translate((math.cos(a) * COAT_R, math.sin(a) * COAT_R, z))
            parts.append(s)
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)


def lay_flat(m: Manifold) -> Manifold:
    """z축 막대를 x축으로 눕히고 바닥을 잘라 평평하게."""
    m = m.rotate((0, 90, 0)).translate((0, 0, CENTER_Z))
    floor = Manifold.cube((1000, 1000, 100), center=True).translate((0, 0, 50))
    return m ^ floor


def to_trimesh(m: Manifold) -> trimesh.Trimesh:
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=True)


def save(m: Manifold, name: str) -> None:
    t = to_trimesh(m)
    t.export(OUT / f"{name}.stl")
    ext = t.bounds[1] - t.bounds[0]
    print(f"{name:16s} {ext[0]:6.1f} x {ext[1]:5.1f} x {ext[2]:4.1f} mm  "
          f"watertight={t.is_watertight}  {t.volume / 1000:5.2f} cm³")


import manifold3d  # noqa: E402  (OpType 접근용)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    rng = random.Random(1111)

    biscuit = stick()
    kinds = {
        "오리지널": coat_base(),
        "아몬드": coat_base() + almond_bumps(rng),
        "화이트줄무늬": coat_base() + drizzle(),
    }

    plate = []
    for i, (name, coat) in enumerate(kinds.items()):
        choco = coat - biscuit
        whole = lay_flat(biscuit + coat)
        save(whole, name)
        save(lay_flat(biscuit), f"{name}_과자")
        save(lay_flat(choco), f"{name}_초코")
        plate.append(whole.translate((0, i * 15.0, 0)))

    save(Manifold.batch_boolean(plate, manifold3d.OpType.Add), "빼빼로_세트")

    # 세워서 뽑는 버전: 손잡이가 바닥, 초코 끝이 위. 깎아낸 면 없이 둥근 단면 그대로.
    upright_biscuit = stick(flat_end=True)
    standing = []
    for i, (name, coat) in enumerate(kinds.items()):
        save(upright_biscuit + coat, f"{name}_세움")
        save(upright_biscuit, f"{name}_세움_과자")
        save(coat - upright_biscuit, f"{name}_세움_초코")
        standing.append((upright_biscuit + coat).translate((i * STAND_GAP, 0, 0)))
    save(Manifold.batch_boolean(standing, manifold3d.OpType.Add), "빼빼로_세트_세움")


if __name__ == "__main__":
    main()
