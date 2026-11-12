"""하트 바디 모양 공용 함수 (bass.py 가 씀).

  - heart(): 하트 윤곽 (폭 약 77mm)
  - slab(): 바닥 평평, 윗모서리 둥근 하트 판
  - text(): '11.11' 글자 (assets/글자_1111.stl, Blender 에서 Verdana Bold 로 만듦)
"""
from pathlib import Path
import math

import manifold3d
import numpy as np
import trimesh
from manifold3d import CrossSection, Manifold


ROOT = Path(__file__).parent
BASE_H = 14.0       # slab 기본 높이
ROUND = 2.0         # 윗모서리 둥글기 반지름
ROUND_STEPS = 8
SCALE = 2.4         # 하트 크기 (폭 약 77mm)


def heart() -> CrossSection:
    pts = []
    for i in range(240):
        t = 2 * math.pi * i / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * SCALE, y * SCALE + 4))
    pts.reverse()  # 반시계 방향
    # 위쪽 오목한 홈과 아래 뾰족한 끝을 살짝 둥글게
    return CrossSection([pts]).offset(1.5).offset(-2.5).offset(1.0)


def slab(height: float = BASE_H) -> Manifold:
    """바닥 평평, 윗모서리만 둥근 하트 판."""
    cs = heart()
    body_h = height - ROUND
    parts = [Manifold.extrude(cs, body_h)]
    for i in range(ROUND_STEPS):
        z0 = body_h + ROUND * i / ROUND_STEPS
        dz = ROUND * (i + 1) / ROUND_STEPS
        inset = ROUND - math.sqrt(max(ROUND ** 2 - dz ** 2, 0)) if i < ROUND_STEPS - 1 else ROUND * 0.6
        parts.append(Manifold.extrude(cs.offset(-inset), ROUND / ROUND_STEPS + 0.01)
                     .translate((0, 0, z0)))
    return Manifold.batch_boolean(parts, manifold3d.OpType.Add)



def text() -> Manifold:
    t = trimesh.load(ROOT / "assets" / "글자_1111.stl")
    mesh = manifold3d.Mesh(vert_properties=np.asarray(t.vertices, np.float32),
                           tri_verts=np.asarray(t.faces, np.uint32))
    return Manifold(mesh)
