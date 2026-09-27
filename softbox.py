"""
Plastic Lighthouse — mini softbox for a standard E27 lamp holder.

Parts (all fit Bambu Lab A1 mini, 180 x 180 x 180 mm):
  frame     – conical reflector body; Ø37 sleeve slides onto the E27 socket
  diffuser  – thin white front cover that snaps over the frame rim
  baffle    – optional inner diffuser that wedges inside the taper (kills hotspot)
  fit_test  – small plate with the mounting hole, to check the fit before the big print

Usage:  python3 softbox.py   -> writes stl/round/*.stl, stl/square/*.stl, stl/fit_test.stl
All sizes in mm. Change parameters below and re-run.
"""

import os

import numpy as np
from manifold3d import CrossSection, JoinType, Manifold

# ---------------------------------------------------------------- parameters
SOCKET_D = 37.0        # measured outer diameter of the E27 socket body
HOLE_CLEAR = 0.2       # sleeve bore = Ø37.2 in CAD
HOLE_D = SOCKET_D + HOLE_CLEAR
PLATE_T = 3.0          # back plate thickness
TUBE_LEN = 10.0        # socket sleeve length, total incl. plate (spreads the load)
TUBE_WALL = 2.4        # sleeve wall
TUBE_FILLET = 3.0      # conical fillet where the sleeve meets the plate
BACK_R = 40.0          # back plate radius (Ø80)
VENT_D = 6.0           # ring of vent holes around the socket (0 = none)
VENT_N = 8
VENT_RING_R = 31.0

DEPTH = 140.0          # total frame depth (bulb tip is ~95 mm from the plate)
FRONT_R = 86.0         # front opening outer radius (Ø172)
WALL = 1.6             # wall thickness (4 perimeters @ 0.4 nozzle)
RIM_H = 9.0            # straight rim at the front the diffuser snaps over
RIM_WALL = 2.4         # rim thickness (groove is cut into it)

GROOVE_DEPTH = 0.6     # snap groove in rim / bumps on diffuser skirt
GROOVE_HALF_H = 1.0
GROOVE_FROM_FRONT = 4.5

DIFF_T = 0.8           # diffuser sheet thickness (0.6 = brighter, 1.0 = softer)
SKIRT_T = 1.2
SKIRT_H = 8.0
CLEARANCE = 0.2        # skirt-to-rim gap
BUMP = 0.45            # snap bump height (slightly less than groove depth)
BUMP_N = 6             # number of bump segments around the skirt
BUMP_DEG = 25          # angular length of each bump

BAFFLE_T = 0.6
BAFFLE_Z = 108.0       # where the inner diffuser sits (from back plate bottom)

SHAPE = "round"        # "round" or "square" (set per build in __main__)
CORNER_FRAC = 0.16     # square: corner radius as a fraction of the half-size

SEG = 256              # circle resolution
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")


# ---------------------------------------------------------------- helpers
def cone(r0, r1, z0, z1, x=0.0, y=0.0):
    """Truncated cone (or cylinder) from z0 (radius r0) to z1 (radius r1)."""
    return Manifold.cylinder(z1 - z0, r0, r1, SEG).translate([x, y, z0])


def rrect(half, r):
    """Rounded square centred on origin, outer half-size `half`, corner radius `r`."""
    core = CrossSection.square([2 * (half - r)] * 2, center=True)
    return core.offset(r, JoinType.Round, circular_segments=SEG // 4)


def taper(h0, h1, z0, z1):
    """Body cross-section tapering from half-size h0 at z0 to h1 at z1 (round or square)."""
    if SHAPE == "round":
        return cone(h0, h1, z0, z1)
    slab = lambda h, z: Manifold.extrude(rrect(h, h * CORNER_FRAC), 0.01).translate([0, 0, z])
    return Manifold.batch_hull([slab(h0, z0), slab(h1, z1 - 0.01)])


def cyl(d, z0, z1, x=0.0, y=0.0):
    return cone(d / 2, d / 2, z0, z1, x, y)


def sectors(n, deg, r):
    """n pie wedges of `deg` degrees each, as a 2D cross-section."""
    pts = []
    for i in range(n):
        a0 = np.radians(i * 360 / n - deg / 2)
        a1 = np.radians(i * 360 / n + deg / 2)
        arc = [(r * np.cos(a), r * np.sin(a)) for a in np.linspace(a0, a1, 16)]
        pts.append([(0.0, 0.0)] + arc)
    return CrossSection(pts)


def lerp(a, b, t):
    return a + (b - a) * t


# ---------------------------------------------------------------- geometry
FLARE_END = DEPTH - RIM_H                     # where the cone meets the rim
_slope = (FRONT_R - BACK_R) / FLARE_END
WALL_H = WALL * np.sqrt(1 + _slope ** 2)      # horizontal thickness of sloped wall


def inner_r_at(z):
    """Inner radius of the conical cavity at height z."""
    return BACK_R - WALL_H + _slope * z


def frame():
    outer = taper(BACK_R, FRONT_R, 0, FLARE_END) + taper(FRONT_R, FRONT_R, FLARE_END - 0.01, DEPTH)

    # conical cavity above the back plate; 45° chamfer where it meets the thicker rim
    z_ch = FLARE_END - (RIM_WALL - WALL_H)
    cavity = taper(inner_r_at(PLATE_T), inner_r_at(z_ch), PLATE_T, z_ch)
    rim_in = FRONT_R - RIM_WALL
    cavity += taper(inner_r_at(z_ch), rim_in, z_ch - 0.01, FLARE_END)
    cavity += taper(rim_in, rim_in, FLARE_END - 0.01, DEPTH + 1)

    body = outer - cavity

    body += sleeve()

    # centre hole for the socket + ring of vents
    body -= cyl(HOLE_D, -1, TUBE_LEN + 1)
    for i in range(VENT_N if VENT_D > 0 else 0):
        a = 2 * np.pi * (i + 0.5) / VENT_N
        body -= cyl(VENT_D, -1, PLATE_T + 1, VENT_RING_R * np.cos(a), VENT_RING_R * np.sin(a))

    # V-groove around the rim for the diffuser snap
    zc = DEPTH - GROOVE_FROM_FRONT
    h, d = GROOVE_HALF_H, GROOVE_DEPTH
    keep = taper(FRONT_R, FRONT_R - d, zc - h, zc) + taper(FRONT_R - d, FRONT_R, zc - 0.01, zc + h)
    band = taper(FRONT_R + 1, FRONT_R + 1, zc - h, zc + h) - taper(
        FRONT_R - d - 0.5, FRONT_R - d - 0.5, zc - h - 1, zc + h + 1
    )
    body -= band - keep
    return body


def sleeve():
    """Tube around the socket, growing from the plate into the box (prints without supports)."""
    r = HOLE_D / 2 + TUBE_WALL
    tube = cone(r, r, 0, TUBE_LEN)
    fillet = cone(r + TUBE_FILLET, r, PLATE_T - 0.01, PLATE_T + TUBE_FILLET)
    return tube + fillet


def diffuser():
    """Printed face-down: sheet on the bed, skirt pointing up."""
    r_in = FRONT_R + CLEARANCE
    r_out = r_in + SKIRT_T

    part = taper(r_out, r_out, 0, DIFF_T + SKIRT_H) - taper(r_in, r_in, DIFF_T, DIFF_T + SKIRT_H + 1)

    # V-shaped snap bumps on the inner face of the skirt, split into segments
    zc = DIFF_T + GROOVE_FROM_FRONT
    h = GROOVE_HALF_H
    v_cut = taper(r_in, r_in - BUMP, zc - h, zc) + taper(r_in - BUMP, r_in, zc - 0.01, zc + h)
    ring = taper(r_in + 0.3, r_in + 0.3, zc - h, zc + h) - v_cut
    # round: BUMP_N segments; square: one bump in the middle of each side
    n, deg = (BUMP_N, BUMP_DEG) if SHAPE == "round" else (4, 30)
    mask = Manifold.extrude(sectors(n, deg, 2 * r_out), 2 * h + 2).translate([0, 0, zc - h - 1])
    return part + (ring ^ mask)


def baffle():
    r = inner_r_at(BAFFLE_Z) - 0.4
    plate = taper(r, r, 0, BAFFLE_T)
    # small pull ring in the centre so it can be pushed / pulled out
    tab = cyl(12, BAFFLE_T - 0.01, BAFFLE_T + 2.0) - cyl(7, BAFFLE_T, BAFFLE_T + 3)
    return plate + tab


def fit_test():
    """Strip with three sleeves: HOLE_D - 0.3, HOLE_D, HOLE_D + 0.3 (marked by notches)."""
    pitch = HOLE_D + 2 * (TUBE_WALL + TUBE_FILLET) + 6
    part = Manifold.cube([3 * pitch, pitch, PLATE_T]).translate([-1.5 * pitch, -pitch / 2, 0])
    for i, dd in enumerate((-0.3, 0.0, 0.3)):
        x = (i - 1) * pitch
        part += sleeve().translate([x, 0, 0])
        part -= cyl(HOLE_D + dd, -1, TUBE_LEN + 1, x)
        for k in range(i + 1):  # 1, 2, 3 notches = small, nominal, large
            part -= Manifold.cube([1.5, 3, PLATE_T + 2]).translate([x - 4 + k * 3, pitch / 2 - 2, -1])
    return part


# ---------------------------------------------------------------- export
def write_stl(m: Manifold, path):
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties)[:, :3].astype(np.float32)
    f = np.asarray(mesh.tri_verts, dtype=np.int64)
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    data = np.zeros(len(f), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    data["n"], data["v"] = n, tri
    with open(path, "wb") as fh:
        fh.write(b"plastic-lighthouse".ljust(80, b" "))
        fh.write(np.uint32(len(f)).tobytes())
        fh.write(data.tobytes())


PARTS = {"frame": frame, "diffuser": diffuser, "baffle": baffle, "fit_test": fit_test}

def build(name, fn, path):
    m = fn()
    lo, hi = np.array(m.bounding_box()[:3]), np.array(m.bounding_box()[3:])
    size = hi - lo
    assert m.status().name == "NoError", (name, m.status())
    assert (size <= 180).all(), f"{name} does not fit A1 mini: {size}"
    write_stl(m, path)
    print(f"{os.path.relpath(path, OUT_DIR):20s} {size[0]:6.1f} x {size[1]:6.1f} x {size[2]:6.1f} mm  "
          f"vol {m.volume() / 1000:6.1f} cm3  genus {m.genus()}")


if __name__ == "__main__":
    for SHAPE in ("round", "square"):
        os.makedirs(os.path.join(OUT_DIR, SHAPE), exist_ok=True)
        for name in ("frame", "diffuser", "baffle"):
            build(name, PARTS[name], os.path.join(OUT_DIR, SHAPE, f"{name}.stl"))
    build("fit_test", fit_test, os.path.join(OUT_DIR, "fit_test.stl"))
