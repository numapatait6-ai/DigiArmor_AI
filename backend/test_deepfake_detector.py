"""
DigiArmor AI - deepfake detector test.
Measures ACTUAL model behaviour. It does not assert that real must be real or AI must be fake.

Put images in backend/test_images/ named: real.(jpg|png|webp), ai.(...), nonface.(...)
or pass --real/--ai/--nonface paths.
"""
import os
import sys
import math
import argparse
import tempfile

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from utils import deepfake_detect as dd  # noqa: E402

FAILURES = []


def fail(msg):
    FAILURES.append(msg)
    print("  [FAIL] " + msg)


def find_default(name):
    folder = os.path.join(BACKEND_DIR, "test_images")
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(folder, name + ext)
        if os.path.isfile(p):
            return p
    return None


def validate_success(res):
    p = res.get("deepfake_probability")
    r = res.get("real_probability")
    if p is None or r is None or not (0 <= p <= 1) or not (0 <= r <= 1) or math.isnan(p) or math.isnan(r):
        fail("Invalid probability values: fake=%r real=%r" % (p, r))
        return
    if abs(p + r - 1.0) > 1e-3:
        fail("fake + real != 1 (%.6f)" % (p + r))
    for face in res.get("faces", []):
        for key, m in face["models"].items():
            if any(math.isnan(v) or math.isinf(v) for v in m["raw_logits"]):
                fail("Non-finite raw logits from %s" % key)


def run_case(title, path, expect_face_hint):
    print("\n" + title)
    if not path or not os.path.isfile(path):
        fail("Image not found for '%s' (put it in backend/test_images/ or pass a path)." % title)
        return
    print("File: " + path)
    res = dd.run_full_deepfake_detection(path)
    status = res.get("status")
    if status == "error":
        fail("Detector error [%s]: %s" % (res.get("error_code"), res.get("message")))
        return
    if status == "no_face":
        print("Face detected: NO")
        print("Status: NO_FACE")
        print("Message: " + res.get("message", ""))
        return
    validate_success(res)
    print("Face detected: YES (faces found: %d, MTCNN confidence of deciding face: %.2f)"
          % (res["faces_detected"], res["face_confidence"]))
    for face in res["faces"]:
        print("  Face #%d box=%s side=%.0fpx" % (face["face_index"], face["face_box"], face["face_side_px"]))
        for key, m in face["models"].items():
            print("    %-16s raw_logits=%s fake_p=%.4f real_p=%.4f"
                  % (key, m["raw_logits"], m["fake_probability"], m["real_probability"]))
        print("    ensemble fake_p=%.4f (disagreement %.2f)" % (face["deepfake_probability"], face["model_disagreement"]))
    print("Fake probability: %.1f%%" % (res["deepfake_probability"] * 100))
    print("Prediction: %s | Risk: %s" % (res["prediction"], res["risk_level"]))
    for w in res.get("warnings", []):
        print("  Warning: " + w)
    if expect_face_hint is False:
        print("  Note: a face WAS detected in an image you labelled non-face; check the image.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real")
    ap.add_argument("--ai")
    ap.add_argument("--nonface")
    args = ap.parse_args()

    print("=" * 50)
    print("DIGIARMOR AI - DEEPFAKE DETECTOR TEST")
    print("=" * 50)

    try:
        info = dd.get_model_info()
    except Exception as exc:
        print("\n[FATAL] Model loading failed: %s" % exc)
        sys.exit(1)

    print("\nModel: " + info["model_name"])
    print("Type: " + info["model_type"])
    print("Input: %s" % info["input_size"])
    print("Device: " + info["device"])
    print("Preprocessing: " + info["preprocessing"])
    for m in info["models"]:
        print("  - %s @ %s | labels=%s | fake_index=%d | weight=%.2f"
              % (m["name"], m["revision"][:8], m["labels"], m["fake_index"], m["weight"]))
    print("Thresholds: SUSPICIOUS>=%.2f, HIGH>=%.2f" % (dd.SUSPICIOUS_THRESHOLD, dd.HIGH_RISK_THRESHOLD))

    run_case("REAL IMAGE", args.real or find_default("real"), True)
    run_case("AI IMAGE", args.ai or find_default("ai"), True)
    run_case("NON-FACE IMAGE", args.nonface or find_default("nonface"), False)

    # Corrupted-file handling
    print("\nCORRUPTED FILE")
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(b"this is not an image")
        tmp_path = tmp.name
    try:
        res = dd.run_full_deepfake_detection(tmp_path)
        if res.get("status") == "error" and res.get("error_code") == "INVALID_IMAGE":
            print("Status: rejected as INVALID_IMAGE (correct)")
        else:
            fail("Corrupted file was not rejected: %s" % res.get("status"))
    finally:
        os.remove(tmp_path)

    print("\n" + "=" * 50)
    if FAILURES:
        print("RESULT: %d FAILURE(S)" % len(FAILURES))
        for f in FAILURES:
            print(" - " + f)
        sys.exit(1)
    print("RESULT: pipeline ran correctly. (Classifications above are observed model behaviour,")
    print("not guarantees. Evaluate on your own labelled set before quoting accuracy.)")
    print("=" * 50)


if __name__ == "__main__":
    main()