"""
DIGIARMOR AI - Layer 1 identity-protection test / report.

Run from the backend folder:
    python test_identity_protection.py --image path\\to\\real_face_photo.jpg
Options:
    --epsilon 0.03   --iters 50   --eot 2   --ensemble   --no-eval

Every number printed is computed at run time. Functional checks (PASS/FAIL) test that the
pipeline works; attack-success numbers are REPORTED, never asserted, because whether a given
photo is protected is an empirical result, not something a test may force.
"""
import argparse
import glob
import io
import os
import re
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.adversarial_identity import (  # noqa: E402
    IdentityProtectionError, analyze_image_for_protection, apply_identity_protection,
    sha256_file, verify_protected_image,
)

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def fmt(v, spec):
    return "n/a" if v is None else format(v, spec)


def find_image(cli):
    if cli:
        return cli
    if os.environ.get("DIGIARMOR_TEST_IMAGE"):
        return os.environ["DIGIARMOR_TEST_IMAGE"]
    here = os.path.dirname(os.path.abspath(__file__))
    for pat in ("test_assets/*.jpg", "test_assets/*.jpeg", "test_assets/*.png"):
        hits = sorted(glob.glob(os.path.join(here, pat)))
        if hits:
            return hits[0]
    return None


def expect_error(label, path, accepted, **kw):
    try:
        apply_identity_protection(path, run_evaluation=False, iterations=5, **kw)
        check(label, False, "no error raised")
    except IdentityProtectionError as e:
        check(label, e.code in accepted, f"raised {e.code}: {e.message}")
    except Exception as e:  # unexpected exception type is a real bug
        check(label, False, f"unexpected {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image")
    ap.add_argument("--epsilon", type=float, default=0.03)
    ap.add_argument("--iters", type=int, default=50)
    ap.add_argument("--eot", type=int, default=2)
    ap.add_argument("--ensemble", action="store_true")
    ap.add_argument("--no-eval", action="store_true")
    a = ap.parse_args()

    img_path = find_image(a.image)
    if not img_path or not os.path.isfile(img_path):
        print("No test photograph found. Pass --image <real face photo> (a real photograph is required;\n"
              "this test never substitutes a fake image for the main test).")
        sys.exit(2)

    out_dir = tempfile.mkdtemp(prefix="digiarmor_test_")
    print("=" * 50)
    print("DIGIARMOR AI - IDENTITY PROTECTION TEST")
    print("=" * 50)
    try:
        # ---------------- analysis ----------------
        an = analyze_image_for_protection(img_path)
        print("\nOriginal:")
        print(f"  Size: {an['width']}x{an['height']}  Format: {an['format']}")
        print(f"  Faces detected: {len(an['faces'])}")
        check("Face detection (>=1 eligible face)", an["protectable"])
        if not an["protectable"]:
            print("  Cannot continue: no eligible face.")
            sys.exit(1)

        # ---------------- protection ----------------
        r = apply_identity_protection(img_path, epsilon=a.epsilon, output_dir=out_dir, iterations=a.iters,
                                      eot_samples=a.eot, ensemble=a.ensemble, run_evaluation=not a.no_eval)
        m, g, res = r["protection_metrics"], r["geometry"], r["deepfake_resistance"]
        prot_path = os.path.join(out_dir, r["protected_image_name"])

        print("\nProtection:")
        print(f"  Protection ID: {r['protection_id']}")
        print(f"  Iterations: {r['settings']['iterations']}   EOT samples/iter: {r['settings']['eot_samples_per_iter']}")
        print(f"  Epsilon: {r['settings']['epsilon']} (~{r['settings']['epsilon_8bit_levels']}/255 levels)")
        print(f"  Models attacked: {', '.join(r['model_used'])}")
        print(f"  Runtime: {r['runtime_seconds']} s")

        print("\nQuality:")
        print(f"  PSNR: {m['psnr']:.2f} dB   (face region {m['psnr_face_region']:.2f} dB)   target >= {m['quality_targets']['psnr_target']}: "
              f"{'MET' if m['quality_targets']['psnr_met'] else 'NOT MET'}")
        print(f"  SSIM: {m['ssim']:.4f}       (face region {m['ssim_face_region']:.4f})       target >= {m['quality_targets']['ssim_target']}: "
              f"{'MET' if m['quality_targets']['ssim_met'] else 'NOT MET'}")
        print(f"  L2: {m['l2_norm']:.2f}   Linf: {m['linf_norm']:.4f} ({m['linf_8bit_levels']}/255)   "
              f"Mean perturbation: {m['mean_absolute_perturbation']:.6f}   Max pixel change: {m['max_pixel_change']}")

        print("\nIdentity (attacked model: VGGFace2 FaceNet):")
        print(f"  Baseline similarity (orig vs unprotected JPEG-95 copy): {m['identity_similarity_before']:.4f}")
        print(f"  Protected similarity (orig vs protected):               {m['identity_similarity_after']:.4f}")
        print(f"  Cosine distance: {m['identity_cosine_distance']:.4f}   L2 embedding distance: {m['identity_distance']:.4f}")
        print(f"  Match threshold (cosine, approximate, uncalibrated): {res['match_threshold_cosine']}")
        print(f"  Attack success on attacked model: {'YES' if res['identity_attack_success'] else 'NO'}")

        print("\nGeometry:")
        print(f"  Face re-detected: {'YES' if g['face_redetected'] else 'NO'}   Confidence: {fmt(g['face_confidence'], '.4f')}")
        print(f"  BBox IoU: {fmt(g['bbox_iou'], '.4f')}   Centre shift: {fmt(g['bbox_center_shift_px'], '.2f')} px")
        print(f"  Landmark displacement: {fmt(g['landmark_displacement_px'], '.2f')} px")
        print(f"  Geometry score: {fmt(g['geometry_score'], '.4f')}")

        print("\nRobustness (cosine similarity to ORIGINAL identity; control = same transform on unprotected original):")
        if res["tested"]:
            print(f"  {'Model':<42}{'Type':<20}{'Condition':<22}{'Control':>8}{'Protected':>11}  Outcome")
            for row in res["results"]:
                print(f"  {row['model']:<42}{row['evaluation_type']:<20}{row['condition']:<22}"
                      f"{fmt(row['original_similarity'], '.3f'):>8}{fmt(row['protected_similarity'], '.3f'):>11}  {row['outcome']}")
            s = res["summary"]
            print(f"  White-box success under transforms: {fmt(s['whitebox_success_rate_under_transforms'], '.0%')}")
            print(f"  Transfer (held-out) success, no transform: {s['transfer_success_no_transform']}")
            print(f"  Overall success rate over all conditions: {fmt(s['overall_success_rate'], '.0%')}")
        else:
            print("  (skipped)")

        print("\nWatermark:")
        print(f"  Embedded: {r['watermark']['embedded']}   Re-read from saved PNG: {r['watermark']['verified_on_saved_png']}")
        print(f"  Survives JPEG re-encode: {r['watermark']['survives']}")

        print("\nHashes:")
        print(f"  Original  SHA-256: {r['image_info']['original_sha256']}")
        print(f"  Protected SHA-256: {r['image_info']['protected_sha256']}")

        print(f"\nSTATUS: {r['protection_status']}  ({r['status_level'].upper()})")
        for x in r["status_reasons"]:
            print(f"  - {x}")
        if r["warnings"]:
            print("WARNINGS:")
            for x in r["warnings"]:
                print(f"  - {x}")
        print("\n" + r["disclaimer"])

        # ---------------- functional checks ----------------
        print("\nFunctional checks:")
        check("Protected file exists", os.path.isfile(prot_path))
        check("Protection ID format DIGI-YYYY-XXXXXXXX", re.fullmatch(r"DIGI-\d{4}-[0-9A-F]{8}", r["protection_id"]) is not None)
        check("Backward-compat keys present", all(k in r for k in ("protected_image_name", "unique_id", "protection_metrics",
                                                                    "deepfake_resistance", "psnr")))
        check("Embedding generated (finite similarities)", np.isfinite(m["identity_similarity_after"]) and np.isfinite(m["identity_similarity_before"]))
        check("Identity distance > 0", m["identity_distance"] > 0)
        check("SHA-256 in result matches file on disk", sha256_file(prot_path) == r["image_info"]["protected_sha256"])
        check("Protected differs from original (hash)", r["image_info"]["protected_sha256"] != r["image_info"]["original_sha256"])
        check("Linf within epsilon budget + watermark allowance (<= eps*255 + 6 levels)",
              m["linf_8bit_levels"] <= round(r["settings"]["epsilon"] * 255) + 6, f"{m['linf_8bit_levels']} levels")
        v = verify_protected_image(prot_path, r["image_info"]["protected_sha256"])
        check("verify_protected_image: hash matches", v.get("sha256_matches_record") is True)
        check("verify_protected_image: watermark ID matches",
              v["watermark"].get("protection_id") == r["protection_id"], str(v["watermark"].get("found")))
        check("No internal paths leaked in result", out_dir not in repr(r))

        # ---------------- failure cases ----------------
        print("\nFailure-case checks:")
        rng = np.random.RandomState(0)
        noface = os.path.join(out_dir, "noface.png")
        Image.fromarray((rng.rand(400, 400, 3) * 255).astype(np.uint8)).save(noface)
        expect_error("No-face image -> NO_FACE", noface, {"NO_FACE"}, output_dir=out_dir)

        junk = os.path.join(out_dir, "junk.jpg")
        with open(junk, "wb") as fh:
            fh.write(os.urandom(2048))
        expect_error("Random bytes named .jpg -> rejected", junk, {"UNSUPPORTED_FORMAT", "CORRUPT_IMAGE"}, output_dir=out_dir)

        raw = open(img_path, "rb").read()
        trunc = os.path.join(out_dir, "trunc.jpg")
        with open(trunc, "wb") as fh:
            fh.write(raw[: max(64, len(raw) // 3)])
        expect_error("Truncated image -> CORRUPT_IMAGE", trunc, {"CORRUPT_IMAGE", "UNSUPPORTED_FORMAT"}, output_dir=out_dir)

        gif = os.path.join(out_dir, "x.gif")
        buf = io.BytesIO()
        Image.new("P", (64, 64)).save(buf, "GIF")
        open(gif, "wb").write(buf.getvalue())
        expect_error("GIF -> UNSUPPORTED_FORMAT", gif, {"UNSUPPORTED_FORMAT"}, output_dir=out_dir)

        tiny = os.path.join(out_dir, "tiny.png")
        im = Image.open(img_path).convert("RGB")
        s = 100.0 / max(im.size)
        im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s)))).save(tiny)
        expect_error("Tiny image (face < 64px) -> FACE_TOO_SMALL/NO_FACE", tiny, {"FACE_TOO_SMALL", "NO_FACE"}, output_dir=out_dir)

        expect_error("Missing file -> CORRUPT_IMAGE", os.path.join(out_dir, "missing.png"), {"CORRUPT_IMAGE"}, output_dir=out_dir)

    finally:
        keep = os.environ.get("DIGIARMOR_KEEP_TEST_OUTPUT")
        if keep:
            print(f"\nOutputs kept in: {out_dir}")
        else:
            shutil.rmtree(out_dir, ignore_errors=True)

    failed = [n for n, ok in CHECKS if not ok]
    print("\n" + "=" * 50)
    print(f"Functional checks: {len(CHECKS) - len(failed)}/{len(CHECKS)} passed")
    print("Attack-success figures above are measurements, not pass/fail criteria.")
    print("=" * 50)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
