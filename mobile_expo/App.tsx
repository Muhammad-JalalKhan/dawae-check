/**
 * Dawae-Check — Expo React Native verification client (single-file).
 *
 * Runs seamlessly on:
 *  - Web (Expo web / browser): dark drag-and-drop + file-picker upload zone.
 *    No native CameraView is initialized on web; picked/dropped images are
 *    converted to a Blob before multipart upload.
 *  - Native (Expo Go / dev build on iOS & Android): live camera viewfinder
 *    with 3x macro zoom, torch, front/back flip, plus gallery upload.
 *    Native uploads stream `{ uri, name, type }` through RN's FormData.
 *
 * Flow: Viewfinder / Upload → Scanning HUD (20s timeout + retry) → Result
 * screen with defect bounding boxes (absolute-positioned Views), verdict
 * banner, confidence score, batch/DRAP registry details and print forensics.
 *
 * Backend: POST https://dawae-check-api.onrender.com/api/v1/verify-packaging
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { StatusBar } from "expo-status-bar";
import {
  Animated,
  Image,
  LayoutChangeEvent,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Svg, { Circle, Line, Path, Rect } from "react-native-svg";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Haptics from "expo-haptics";
import * as ImagePicker from "expo-image-picker";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";

// ── API contract ────────────────────────────────────────────────────────────

type Verdict = "GENUINE" | "REVIEW_RECOMMENDED" | "SUSPECTED_COUNTERFEIT" | "FAILED";
type DrapStatus = "INFERRED_FROM_REGISTRY" | "VERIFIED_MATCH" | "MISMATCH";

interface DetectedDefect {
  label: string;
  confidence: number;
  /** [ymin, xmin, ymax, xmax] normalized to integers 0–1000. */
  bbox_2d: number[];
}

interface MatchedRecord {
  gtin: string | null;
  brand_name: string;
  batch_number: string;
  manufacturer: string | null;
  official_expiry: string;
  drap_reg_number: string | null;
  drap_status: DrapStatus;
}

interface Layer1DatabaseCheck {
  status: "PASSED" | "FAILED";
  reasons: string[];
  matched_record: MatchedRecord | null;
}

interface Layer2VisualCheck {
  status: "PASSED" | "FAILED";
  print_quality_score: number;
  detected_defects: DetectedDefect[];
}

interface VerifyResponse {
  request_id: string;
  verdict: Verdict;
  authenticity_score: number;
  layer1_database_check: Layer1DatabaseCheck;
  layer2_visual_check: Layer2VisualCheck;
  technical_summary: string;
}

// ── Constants & theme ───────────────────────────────────────────────────────

const COLORS = {
  background: "#0B0F19",
  surface: "#111827",
  border: "#1E293B",
  text: "#E7ECF5",
  textMuted: "#8B98AC",
  cyan: "#06B6D4",
  emerald: "#10B981",
  red: "#EF4444",
  amber: "#F59E0B",
  white: "#FFFFFF",
} as const;

const IS_WEB = Platform.OS === "web";

const API_BASE_URL =
  (process.env as Record<string, string | undefined>).EXPO_PUBLIC_API_URL ??
  "https://dawae-check-api.onrender.com";
const VERIFY_ENDPOINT = `${API_BASE_URL}/api/v1/verify-packaging`;

const API_TIMEOUT_MS = 45_000;
const MAX_IMAGE_BYTES = 15 * 1024 * 1024;

const DEVICE_ID = "EXPO-98421";
const FACILITY_ID = "ALK-DISP-KHI-04";

const GUIDANCE_TEXT = "Tip: Align carton flap showing Batch No & Expiry";

const VERDICT_META: Record<Verdict, { title: string; subtitle: string; color: string }> = {
  GENUINE: {
    title: "GENUINE MEDICINE",
    subtitle: "Packaging passed registry and print-forensic checks",
    color: COLORS.emerald,
  },
  REVIEW_RECOMMENDED: {
    title: "REVIEW RECOMMENDED",
    subtitle: "Some checks raised concerns — pharmacist review advised",
    color: COLORS.amber,
  },
  SUSPECTED_COUNTERFEIT: {
    title: "SUSPECTED COUNTERFEIT",
    subtitle: "Packaging failed critical verification checks",
    color: COLORS.red,
  },
  FAILED: {
    title: "VERIFICATION FAILED",
    subtitle: "Packaging failed critical verification checks",
    color: COLORS.red,
  },
};

// ── Network layer ───────────────────────────────────────────────────────────

interface ScanImage {
  uri: string;
  width: number;
  height: number;
}

class VerificationError extends Error {
  constructor(
    public readonly title: string,
    message: string,
  ) {
    super(message);
    this.name = "VerificationError";
  }
}

function timeoutError(): VerificationError {
  return new VerificationError(
    "Verification timed out",
    "The scan took longer than 45 seconds. The service may be waking up — please retry.",
  );
}

function networkError(): VerificationError {
  return new VerificationError(
    "Network problem",
    "Couldn't reach the Dawae-Check verification service. Check your connection and retry.",
  );
}

function serverError(detail: string): VerificationError {
  return new VerificationError(
    "Service rejected the scan",
    detail.length > 160 ? `${detail.slice(0, 160)}…` : detail,
  );
}

function unexpectedResponseError(): VerificationError {
  return new VerificationError(
    "Unexpected response",
    "The verification service returned an unreadable response. Please retry.",
  );
}

/** Web-only: draw the image on a canvas scaled to a max dimension of 1280px,
 *  then re-encode as JPEG via canvas.toBlob — collapses ~10MB phone photos
 *  down to ~250KB so uploads take ~0.5s instead of ~20s on slow links. */
async function toCompressedWebJpeg(
  image: ScanImage,
): Promise<{ blob: Blob; width: number; height: number }> {
  const img = await new Promise<HTMLImageElement | null>((resolve) => {
    const el = new window.Image();
    el.onload = () => resolve(el);
    el.onerror = () => resolve(null);
    el.src = image.uri;
  });

  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    const MAX_DIMENSION = 1280;
    const longest = Math.max(img.naturalWidth, img.naturalHeight);
    const scale = longest > MAX_DIMENSION ? MAX_DIMENSION / longest : 1;
    const width = Math.max(1, Math.round(img.naturalWidth * scale));
    const height = Math.max(1, Math.round(img.naturalHeight * scale));

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(img, 0, 0, width, height);
      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((b) => resolve(b), "image/jpeg", 0.75);
      });
      if (blob) {
        return { blob, width, height };
      }
    }
  }

  // Fallback (decode failure): upload the original bytes untouched.
  const blob = await (await fetch(image.uri)).blob();
  return { blob, width: image.width, height: image.height };
}

async function verifyPackaging(image: ScanImage): Promise<VerifyResponse> {
  const form = new FormData();
  form.append("device_id", DEVICE_ID);
  form.append("facility_id", FACILITY_ID);

  if (IS_WEB) {
    // Web: canvas-compress to ≤1280px JPEG before appending.
    const { blob } = await toCompressedWebJpeg(image);
    form.append("file", blob, "scan.jpg");
  } else {
    // Native: RN's FormData streams the file directly from its URI.
    form.append("file", {
      uri: image.uri,
      name: "scan.jpg",
      type: "image/jpeg",
    } as any);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const res = await fetch(VERIFY_ENDPOINT, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    if (!res.ok) {
      let detail = `The server responded with HTTP ${res.status}.`;
      let rawBody = "";
      try {
        rawBody = await res.text();
        try {
          const body = JSON.parse(rawBody) as { detail?: string } | null;
          if (body && typeof body.detail === "string" && body.detail.length > 0) {
            detail = body.detail;
          }
        } catch {
          // Non-JSON error body — keep the generic HTTP detail.
        }
      } catch {
        // Body unreadable — keep the generic HTTP detail.
      }
      // Surface the exact rejection (detail, status, raw body) in the console.
      console.error("Verification error:", detail, res.status, rawBody);
      throw serverError(detail);
    }
    let data: VerifyResponse;
    try {
      data = (await res.json()) as VerifyResponse;
    } catch {
      throw unexpectedResponseError();
    }
    if (
      !data ||
      !data.verdict ||
      !data.layer1_database_check ||
      !data.layer2_visual_check
    ) {
      throw unexpectedResponseError();
    }
    return data;
  } catch (err) {
    if (err instanceof VerificationError) throw err;
    // Surface raw network rejections (fetch TypeError / AbortError) too.
    console.error("Verification error:", err);
    if ((err as Error | null)?.name === "AbortError") throw timeoutError();
    throw networkError();
  } finally {
    clearTimeout(timer);
  }
}

/** Haptics must never fire on web — expo-haptics is native-only feedback. */
function triggerHaptic(): void {
  if (Platform.OS !== "web") {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => undefined);
  }
}

// ── Inline SVG icons (Feather-style strokes) ────────────────────────────────

interface IconProps {
  size?: number;
  color?: string;
  strokeWidth?: number;
}

function ShieldCheckIcon({ size = 24, color = COLORS.emerald, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M12 2L4 5v6c0 5.2 3.4 9.4 8 11 4.6-1.6 8-5.8 8-11V5l-8-3z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
      <Path
        d="M9 12l2 2 4-4"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function AlertTriangleIcon({ size = 24, color = COLORS.red, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M10.3 3.8L1.9 18a2 2 0 001.7 3h16.8a2 2 0 001.7-3L13.7 3.8a2 2 0 00-3.4 0z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
      <Line x1="12" y1="9" x2="12" y2="13" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
      <Circle cx="12" cy="17" r="1" fill={color} />
    </Svg>
  );
}

function CheckCircleIcon({ size = 24, color = COLORS.emerald, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={strokeWidth} />
      <Path
        d="M8 12.5l2.5 2.5L16 9.5"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function InfoIcon({ size = 24, color = COLORS.cyan, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="12" cy="12" r="10" stroke={color} strokeWidth={strokeWidth} />
      <Line x1="12" y1="11" x2="12" y2="16" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
      <Circle cx="12" cy="8" r="1" fill={color} />
    </Svg>
  );
}

function CameraIcon({ size = 24, color = COLORS.text, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
      <Circle cx="12" cy="13" r="4" stroke={color} strokeWidth={strokeWidth} />
    </Svg>
  );
}

function GalleryIcon({ size = 24, color = COLORS.text, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="3" y="3" width="18" height="18" rx="2" stroke={color} strokeWidth={strokeWidth} />
      <Circle cx="8.5" cy="8.5" r="1.5" fill={color} />
      <Path
        d="M21 15l-5-5L5 21"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </Svg>
  );
}

function ZoomInIcon({ size = 24, color = COLORS.text, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Circle cx="11" cy="11" r="7" stroke={color} strokeWidth={strokeWidth} />
      <Line x1="16.5" y1="16.5" x2="21" y2="21" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
      <Line x1="11" y1="8" x2="11" y2="14" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
      <Line x1="8" y1="11" x2="14" y2="11" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" />
    </Svg>
  );
}

function FlipCameraIcon({ size = 24, color = COLORS.text, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M20 12a8 8 0 01-13.7 5.6M4 12a8 8 0 0113.7-5.6"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
      />
      <Path d="M17.5 3v3.5H14" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M6.5 21v-3.5H10" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function ZapIcon({ size = 24, color = COLORS.text, strokeWidth = 2 }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M13 2L4 14h6l-1 8 9-12h-6l1-8z"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// ── Defect bounding-box overlay (absolute-positioned Views) ────────────────

interface ScaledBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

function scaleBBox(bbox: number[] | undefined, w: number, h: number): ScaledBox | null {
  if (!Array.isArray(bbox) || bbox.length < 4) return null;
  const [ymin = Number.NaN, xmin = Number.NaN, ymax = Number.NaN, xmax = Number.NaN] = bbox;
  if (![ymin, xmin, ymax, xmax].every((v) => Number.isFinite(v))) return null;
  const left = (Math.min(Math.max(xmin, 0), 1000) / 1000) * w;
  const top = (Math.min(Math.max(ymin, 0), 1000) / 1000) * h;
  const right = (Math.min(Math.max(xmax, 0), 1000) / 1000) * w;
  const bottom = (Math.min(Math.max(ymax, 0), 1000) / 1000) * h;
  const width = right - left;
  const height = bottom - top;
  if (width < 5 || height < 5) return null;
  return { left, top, width, height };
}

function DefectImageCard({ image, defects }: { image: ScanImage; defects: DetectedDefect[] }) {
  const [wrapWidth, setWrapWidth] = useState(0);
  const onLayout = useCallback((e: LayoutChangeEvent) => {
    setWrapWidth(e.nativeEvent.layout.width);
  }, []);

  if (wrapWidth <= 0) {
    // First pass: measure the available width before sizing the image box.
    return (
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Scanned Packaging</Text>
        <View style={styles.imageWrap} onLayout={onLayout} />
      </View>
    );
  }

  const aspect = image.width > 0 && image.height > 0 ? image.width / image.height : 4 / 3;
  const MAX_DISPLAY_HEIGHT = 360;
  let displayWidth = wrapWidth;
  let displayHeight = wrapWidth / aspect;
  if (displayHeight > MAX_DISPLAY_HEIGHT) {
    displayHeight = MAX_DISPLAY_HEIGHT;
    displayWidth = displayHeight * aspect;
  }

  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Scanned Packaging</Text>
      <View style={styles.imageWrap} onLayout={onLayout}>
        <View style={{ width: displayWidth, height: displayHeight }}>
          <Image source={{ uri: image.uri }} style={StyleSheet.absoluteFill} resizeMode="cover" />
          {defects.map((defect, index) => {
            const box = scaleBBox(defect.bbox_2d, displayWidth, displayHeight);
            if (!box) return null;
            const tagAbove = box.top >= 20;
            const tagMaxWidth = tagAbove ? 170 : Math.max(40, box.width - 4);
            return (
              <View
                key={`${defect.label}-${index}`}
                style={[
                  styles.bbox,
                  { left: box.left, top: box.top, width: box.width, height: box.height },
                ]}
              >
                <View
                  style={[
                    styles.bboxTag,
                    tagAbove ? styles.bboxTagAbove : styles.bboxTagInside,
                    { maxWidth: tagMaxWidth },
                  ]}
                >
                  <Text style={styles.bboxTagText} numberOfLines={1}>
                    {index + 1}. {defect.label}
                  </Text>
                </View>
              </View>
            );
          })}
        </View>
      </View>
      {defects.length > 0 ? (
        <View style={styles.legend}>
          {defects.map((defect, index) => (
            <View key={`${defect.label}-legend-${index}`} style={styles.legendRow}>
              <View style={styles.legendIndex}>
                <Text style={styles.legendIndexText}>{index + 1}</Text>
              </View>
              <Text style={styles.legendLabel} numberOfLines={1}>
                {defect.label}
              </Text>
              <Text style={styles.legendConfidence}>{Math.round(defect.confidence * 100)}%</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

// ── Web upload zone (drag & drop + file picker) ─────────────────────────────

function WebUploadZone({
  onPickFromLibrary,
  onDroppedFile,
  disabled,
}: {
  onPickFromLibrary: () => void;
  onDroppedFile: (file: File) => void;
  disabled: boolean;
}) {
  const zoneRef = useRef<View | null>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (Platform.OS !== "web") return;
    const el = zoneRef.current as unknown as HTMLElement | null;
    if (!el) return;

    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
      setDragActive(true);
    };
    const handleDragLeave = (e: DragEvent) => {
      e.preventDefault();
      // Ignore transitions into child elements to avoid highlight flicker.
      if (e.relatedTarget && el.contains(e.relatedTarget as Node)) return;
      setDragActive(false);
    };
    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer?.files?.[0];
      if (file) onDroppedFile(file);
    };

    el.addEventListener("dragenter", handleDragOver);
    el.addEventListener("dragover", handleDragOver);
    el.addEventListener("dragleave", handleDragLeave);
    el.addEventListener("drop", handleDrop);
    return () => {
      el.removeEventListener("dragenter", handleDragOver);
      el.removeEventListener("dragover", handleDragOver);
      el.removeEventListener("dragleave", handleDragLeave);
      el.removeEventListener("drop", handleDrop);
    };
  }, [onDroppedFile]);

  return (
    <View style={styles.webWrap}>
      <View style={styles.webHeader}>
        <View style={styles.brandRow}>
          <View style={styles.badgeDot} />
          <Text style={styles.badgeText}>DAWAE-CHECK</Text>
        </View>
        <Text style={styles.badgeSubtitle}>DRAP Automated Verification</Text>
      </View>

      <View style={[styles.dropZone, dragActive && styles.dropZoneActive]} ref={zoneRef}>
        <View style={styles.dropReticle} pointerEvents="none">
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
        </View>
        <Pressable
          onPress={onPickFromLibrary}
          disabled={disabled}
          style={({ pressed }) => [
            styles.dropPress,
            pressed && styles.pressDim,
            disabled && styles.zoneDisabled,
          ]}
        >
          <GalleryIcon size={36} color={dragActive ? COLORS.cyan : COLORS.textMuted} />
          <Text style={[styles.dropTitle, dragActive && styles.dropTitleActive]}>
            {dragActive ? "Release to verify" : "Drop packaging photo here"}
          </Text>
          <Text style={styles.dropHint}>
            or click to browse — a carton flap photo showing Batch No & Expiry works best
          </Text>
        </Pressable>
      </View>

      <View style={styles.banner}>
        <InfoIcon size={16} color={COLORS.cyan} />
        <Text style={styles.bannerText}>{GUIDANCE_TEXT}</Text>
      </View>
    </View>
  );
}

// ── Root App: state machine + capture orchestration ─────────────────────────

type Screen = "capture" | "result";

const HUD_STEPS = [
  "Uploading carton macro image…",
  "Running Qwen2.5-VL packaging print forensics & checking DRAP registry…",
  "Scoring authenticity verdict…",
] as const;

export default function App() {
  const [screen, setScreen] = useState<Screen>("capture");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [hudStep, setHudStep] = useState(0);
  const [pendingImage, setPendingImage] = useState<ScanImage | null>(null);
  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [error, setError] = useState<VerificationError | null>(null);

  const [cameraFacing, setCameraFacing] = useState<"front" | "back">("back");
  const [torchOn, setTorchOn] = useState(false);
  const [isZoomed, setIsZoomed] = useState(false);
  const cameraRef = useRef<CameraView | null>(null);

  const [cameraPermission, requestCameraPermission] = useCameraPermissions();

  // Ask for camera access once on native so the viewfinder opens directly.
  const didRequestPermission = useRef(false);
  useEffect(() => {
    if (IS_WEB || didRequestPermission.current) return;
    didRequestPermission.current = true;
    void requestCameraPermission();
  }, [requestCameraPermission]);

  // Rotate the HUD step text while a verification is in flight.
  useEffect(() => {
    if (!isAnalyzing) return;
    setHudStep(0);
    const id = setInterval(() => {
      setHudStep((step) => (step + 1) % HUD_STEPS.length);
    }, 2600);
    return () => clearInterval(id);
  }, [isAnalyzing]);

  const runVerification = useCallback(async (image: ScanImage) => {
    setIsAnalyzing(true);
    setError(null);
    try {
      const data = await verifyPackaging(image);
      setResult(data);
      setScreen("result");
    } catch (err) {
      setError(
        err instanceof VerificationError
          ? err
          : new VerificationError("Something went wrong", "Verification failed unexpectedly. Please retry."),
      );
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  const resetScan = useCallback(() => {
    triggerHaptic();
    setScreen("capture");
    setResult(null);
    setPendingImage(null);
    setError(null);
    setIsZoomed(false);
    setTorchOn(false);
  }, []);

  const captureFromCamera = useCallback(async () => {
    const camera = cameraRef.current;
    if (!camera || isAnalyzing) return;
    triggerHaptic();
    try {
      const shot = await camera.takePictureAsync({ quality: 0.7 });
      if (!shot?.uri) return;
      const image: ScanImage = {
        uri: shot.uri,
        width: shot.width ?? 1280,
        height: shot.height ?? 1707,
      };
      setPendingImage(image);
      setTorchOn(false);
      await runVerification(image);
    } catch {
      setError(
        new VerificationError("Camera capture failed", "Couldn't take the photo. Please try again."),
      );
    }
  }, [isAnalyzing, runVerification]);

  const handlePickedAsset = useCallback(
    (asset: ImagePicker.ImagePickerAsset) => {
      if (!asset.uri) return;
      if (typeof asset.fileSize === "number" && asset.fileSize > MAX_IMAGE_BYTES) {
        setError(
          new VerificationError(
            "Image too large",
            "Please pick a photo under 15 MB so it can be uploaded reliably.",
          ),
        );
        return;
      }
      const image: ScanImage = {
        uri: asset.uri,
        width: asset.width > 0 ? asset.width : 1280,
        height: asset.height > 0 ? asset.height : 1707,
      };
      setPendingImage(image);
      void runVerification(image);
    },
    [runVerification],
  );

  const pickFromGallery = useCallback(async () => {
    if (isAnalyzing) return;
    triggerHaptic();
    try {
      if (Platform.OS !== "web") {
        const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (!perm.granted) {
          setError(
            new VerificationError(
              "Photos permission needed",
              "Allow photo library access to upload a packaging photo.",
            ),
          );
          return;
        }
      }
      const pick = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        quality: 0.7,
        allowsMultipleSelection: false,
      });
      if (pick.canceled) return;
      const asset = pick.assets[0];
      if (!asset) return;
      handlePickedAsset(asset);
    } catch {
      setError(
        new VerificationError("Could not open picker", "The photo picker failed to open. Please retry."),
      );
    }
  }, [handlePickedAsset, isAnalyzing]);

  /** Web drop-zone files arrive as raw File objects (no ImagePicker involved). */
  const handleDroppedFile = useCallback(
    (file: File) => {
      if (isAnalyzing) return;
      triggerHaptic();
      if (!file.type.startsWith("image/")) {
        setError(
          new VerificationError("Unsupported file", "Please drop an image file (JPG, PNG or WebP)."),
        );
        return;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setError(
          new VerificationError("Image too large", "Please pick a photo under 15 MB."),
        );
        return;
      }
      const url = URL.createObjectURL(file);
      const image: ScanImage = { uri: url, width: 1280, height: 1707 };
      // Read real dimensions so defect boxes keep the correct aspect ratio.
      const img = new window.Image();
      img.onload = () => {
        const sized: ScanImage = {
          uri: url,
          width: img.naturalWidth > 0 ? img.naturalWidth : 1280,
          height: img.naturalHeight > 0 ? img.naturalHeight : 1707,
        };
        setPendingImage(sized);
        void runVerification(sized);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        setError(
          new VerificationError("Unreadable image", "That file could not be decoded as an image."),
        );
      };
      img.src = url;
    },
    [isAnalyzing, runVerification],
  );

  const retryPending = useCallback(() => {
    setError(null);
    if (pendingImage) {
      void runVerification(pendingImage);
    }
  }, [pendingImage, runVerification]);

  const showCamera = !IS_WEB && (cameraPermission?.granted ?? false);

  const handleRequestCameraPermission = useCallback(() => {
    triggerHaptic();
    void requestCameraPermission();
  }, [requestCameraPermission]);

  return (
    <SafeAreaProvider>
      <StatusBar style="light" />
      <SafeAreaView style={styles.safe} edges={["top", "bottom", "left", "right"]}>
        {screen === "result" && result ? (
          <ResultScreen result={result} image={pendingImage} onReset={resetScan} />
        ) : showCamera ? (
          <CaptureScreen
            cameraRef={cameraRef}
            facing={cameraFacing}
            torchOn={torchOn}
            isZoomed={isZoomed}
            isAnalyzing={isAnalyzing}
            onToggleFacing={() => {
              triggerHaptic();
              setCameraFacing((f) => (f === "back" ? "front" : "back"));
            }}
            onToggleTorch={() => {
              triggerHaptic();
              setTorchOn((on) => !on);
            }}
            onToggleZoom={() => {
              triggerHaptic();
              setIsZoomed((z) => !z);
            }}
            onCapture={captureFromCamera}
            onPickFromGallery={pickFromGallery}
          />
        ) : !IS_WEB ? (
          <NativePermissionGate
            onRequestPermission={handleRequestCameraPermission}
            onPickFromGallery={pickFromGallery}
            isAnalyzing={isAnalyzing}
          />
        ) : (
          <WebUploadZone
            onPickFromLibrary={pickFromGallery}
            onDroppedFile={handleDroppedFile}
            disabled={isAnalyzing}
          />
        )}

        {isAnalyzing ? <ScanningHud step={hudStep} /> : null}

        <ErrorSheet
          error={error}
          canRetry={pendingImage !== null}
          onRetry={retryPending}
          onClose={() => setError(null)}
        />
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

// ── Scanning HUD ────────────────────────────────────────────────────────────

function ScanningHud({ step }: { step: number }) {
  const spin = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(spin, { toValue: 1, duration: 1100, useNativeDriver: true }),
    );
    loop.start();
    return () => loop.stop();
  }, [spin]);

  const activeStep = Math.min(step, HUD_STEPS.length - 1);
  const rotations = spin.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });

  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      <View style={styles.hudBackdrop}>
        <Animated.View
          style={[
            styles.hudRing,
            { transform: [{ rotate: rotations }] },
          ]}
        >
          <View style={styles.hudRingTrack} />
          <View style={styles.hudRingArc} />
        </Animated.View>
        <Text style={styles.hudTitle}>Verifying Packaging</Text>
        <Text style={styles.hudStep}>{HUD_STEPS[activeStep] ?? ""}</Text>
        <View style={styles.hudDots}>
          {HUD_STEPS.map((_, i) => (
            <View key={i} style={[styles.hudDot, i === activeStep && styles.hudDotActive]} />
          ))}
        </View>
      </View>
    </View>
  );
}

// ── Error sheet ─────────────────────────────────────────────────────────────

function ErrorSheet({
  error,
  canRetry,
  onRetry,
  onClose,
}: {
  error: VerificationError | null;
  canRetry: boolean;
  onRetry: () => void;
  onClose: () => void;
}) {
  if (!error) return null;
  return (
    <Modal transparent visible animationType="fade" onRequestClose={onClose}>
      <View style={styles.sheetBackdrop}>
        <View style={styles.sheetCard}>
          <View style={styles.sheetIconRow}>
            <AlertTriangleIcon size={28} color={COLORS.amber} />
            <Text style={styles.sheetTitle}>{error.title}</Text>
          </View>
          <Text style={styles.sheetMessage}>{error.message}</Text>
          <View style={styles.sheetActions}>
            {canRetry ? (
              <Pressable
                style={({ pressed }) => [styles.sheetButton, pressed && styles.pressDim]}
                onPress={() => {
                  triggerHaptic();
                  onRetry();
                }}
              >
                <Text style={styles.sheetButtonText}>Retry Scan</Text>
              </Pressable>
            ) : null}
            <Pressable
              style={({ pressed }) => [styles.sheetButtonGhost, pressed && styles.pressDim]}
              onPress={() => {
                triggerHaptic();
                onClose();
              }}
            >
              <Text style={styles.sheetButtonGhostText}>Dismiss</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

// ── Native permission gate (iOS/Android only) ──────────────────────────────

function NativePermissionGate({
  onRequestPermission,
  onPickFromGallery,
  isAnalyzing,
}: {
  onRequestPermission: () => void;
  onPickFromGallery: () => void;
  isAnalyzing: boolean;
}) {
  return (
    <View style={styles.webWrap}>
      <View style={styles.webHeader}>
        <View style={styles.brandRow}>
          <View style={styles.badgeDot} />
          <Text style={styles.badgeText}>DAWAE-CHECK</Text>
        </View>
        <Text style={styles.badgeSubtitle}>DRAP Automated Verification</Text>
      </View>

      <View style={styles.card}>
        <View style={styles.gateIconWrap}>
          <CameraIcon size={32} color={COLORS.cyan} />
        </View>
        <Text style={styles.gateTitle}>Camera access needed</Text>
        <Text style={styles.gateMessage}>
          Dawae-Check photographs the carton flap to verify it. Grant camera
          access to start scanning, or upload a flap photo instead.
        </Text>
        <Pressable
          style={({ pressed }) => [styles.primaryButton, pressed && styles.pressDim]}
          onPress={onRequestPermission}
          disabled={isAnalyzing}
        >
          <Text style={styles.primaryButtonText}>Grant Camera Access</Text>
        </Pressable>
        <Pressable
          style={({ pressed }) => [styles.ghostButton, pressed && styles.pressDim]}
          onPress={onPickFromGallery}
          disabled={isAnalyzing}
        >
          <Text style={styles.ghostButtonText}>Upload Flap Photo</Text>
        </Pressable>
      </View>

      <View style={styles.banner}>
        <InfoIcon size={16} color={COLORS.cyan} />
        <Text style={styles.bannerText}>{GUIDANCE_TEXT}</Text>
      </View>
    </View>
  );
}

// ── Native viewfinder (iOS/Android only) ───────────────────────────────────

interface CaptureScreenProps {
  cameraRef: { current: CameraView | null };
  facing: "front" | "back";
  torchOn: boolean;
  isZoomed: boolean;
  isAnalyzing: boolean;
  onToggleFacing: () => void;
  onToggleTorch: () => void;
  onToggleZoom: () => void;
  onCapture: () => void;
  onPickFromGallery: () => void;
}

function CaptureScreen({
  cameraRef,
  facing,
  torchOn,
  isZoomed,
  isAnalyzing,
  onToggleFacing,
  onToggleTorch,
  onToggleZoom,
  onCapture,
  onPickFromGallery,
}: CaptureScreenProps) {
  // Breathing ring around the shutter button.
  const pulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0, duration: 900, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const pulseOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.85, 0.1] });
  const pulseScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 1.28] });

  return (
    <View style={styles.camera}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing={facing}
        enableTorch={torchOn}
        zoom={isZoomed ? 0.35 : 0}
      />

      <View style={styles.camTopBar} pointerEvents="box-none">
        <View pointerEvents="none">
          <View style={styles.camBadge}>
            <View style={styles.badgeDot} />
            <Text style={styles.camBadgeText}>DAWAE-CHECK</Text>
          </View>
          <Text style={styles.camBadgeSub}>DRAP Automated Verification</Text>
        </View>
        <View style={styles.camTopActions} pointerEvents="box-none">
          <Pressable
            style={({ pressed }) => [
              styles.iconButton,
              torchOn && styles.iconButtonActive,
              pressed && styles.pressDim,
            ]}
            onPress={onToggleTorch}
            hitSlop={8}
          >
            <ZapIcon size={20} color={torchOn ? "#04222B" : COLORS.text} />
          </Pressable>
          <Pressable
            style={({ pressed }) => [styles.iconButton, pressed && styles.pressDim]}
            onPress={onToggleFacing}
            hitSlop={8}
          >
            <FlipCameraIcon size={20} color={COLORS.text} />
          </Pressable>
        </View>
      </View>

      <View style={styles.reticleHolder} pointerEvents="none">
        <View style={styles.reticle}>
          <View style={[styles.corner, styles.cornerTL]} />
          <View style={[styles.corner, styles.cornerTR]} />
          <View style={[styles.corner, styles.cornerBL]} />
          <View style={[styles.corner, styles.cornerBR]} />
        </View>
      </View>

      <View style={styles.camBottom} pointerEvents="box-none">
        <View style={styles.guidanceChip} pointerEvents="none">
          <Text style={styles.guidanceChipText}>{GUIDANCE_TEXT}</Text>
        </View>
        <View style={styles.camControls}>
          <Pressable
            style={({ pressed }) => [styles.sideButton, pressed && styles.pressDim]}
            onPress={onPickFromGallery}
            disabled={isAnalyzing}
          >
            <GalleryIcon size={22} color={COLORS.text} />
            <Text style={styles.sideLabel}>Upload{"\n"}Flap Photo</Text>
          </Pressable>

          <Pressable onPress={onCapture} disabled={isAnalyzing} style={styles.shutterHit}>
            <Animated.View
              style={[
                styles.shutterPulse,
                { opacity: pulseOpacity, transform: [{ scale: pulseScale }] },
              ]}
            />
            <View style={styles.shutterOuter}>
              <View style={styles.shutter} />
            </View>
          </Pressable>

          <Pressable
            style={({ pressed }) => [
              styles.sideButton,
              isZoomed && styles.sideButtonActive,
              pressed && styles.pressDim,
            ]}
            onPress={onToggleZoom}
          >
            <ZoomInIcon size={22} color={isZoomed ? COLORS.cyan : COLORS.text} />
            <Text style={[styles.sideLabel, isZoomed && styles.sideLabelActive]}>3x Macro</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

// ── Result screen helpers ───────────────────────────────────────────────────

function Badge({ label, fg, bg, border }: { label: string; fg: string; bg: string; border: string }) {
  return (
    <View style={[styles.badge, { backgroundColor: bg, borderColor: border }]}>
      <Text style={[styles.badgeChipText, { color: fg }]}>{label}</Text>
    </View>
  );
}

function drapBadgeProps(status: DrapStatus): { label: string; fg: string; bg: string; border: string } {
  switch (status) {
    case "VERIFIED_MATCH":
      return {
        label: "DRAP: Reg # Verified",
        fg: "#6EE7B7",
        bg: "rgba(16,185,129,0.12)",
        border: "rgba(16,185,129,0.45)",
      };
    case "MISMATCH":
      return {
        label: "DRAP: Registry Mismatch",
        fg: "#FCA5A5",
        bg: "rgba(239,68,68,0.12)",
        border: "rgba(239,68,68,0.45)",
      };
    case "INFERRED_FROM_REGISTRY":
    default:
      return {
        label: "DRAP: Inferred from Official Batch",
        fg: "#7DE3F4",
        bg: "rgba(6,182,212,0.12)",
        border: "rgba(6,182,212,0.45)",
      };
  }
}

function DetailRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text
        style={[styles.detailValue, mono === true ? styles.detailMono : null]}
        numberOfLines={1}
      >
        {value}
      </Text>
    </View>
  );
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  const clamped = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  return (
    <View style={styles.forensicRow}>
      <View style={styles.forensicHeader}>
        <Text style={styles.forensicLabel}>{label}</Text>
        <Text style={[styles.forensicValue, { color }]}>{clamped.toFixed(0)} / 100</Text>
      </View>
      <View style={styles.scoreMeter}>
        <View style={[styles.scoreMeterFill, { width: `${clamped}%`, backgroundColor: color }]} />
      </View>
    </View>
  );
}

function ExpiryRow({ layer1 }: { layer1: Layer1DatabaseCheck }) {
  const record = layer1.matched_record;
  const reasons = layer1.reasons ?? [];
  const expiryReason = reasons.find((reason) => /expiry/i.test(reason));

  if (record && expiryReason) {
    const dates = expiryReason.match(/\d{4}-\d{2}-\d{2}/g);
    const extracted = dates?.[0] ?? "unreadable";
    const official = dates?.[1] ?? record.official_expiry;
    return (
      <View style={styles.expiryBlock}>
        <View style={styles.detailRowNoBorder}>
          <Text style={styles.detailLabel}>Expiry Verification</Text>
          <Badge
            label="MISMATCH"
            fg="#FCA5A5"
            bg="rgba(239,68,68,0.12)"
            border="rgba(239,68,68,0.45)"
          />
        </View>
        <Text style={styles.expiryNote}>
          Extracted {extracted} · Official {official}
        </Text>
      </View>
    );
  }

  if (record) {
    return (
      <View style={styles.detailRowNoBorder}>
        <Text style={styles.detailLabel}>Expiry Verification</Text>
        <Badge
          label="VERIFIED"
          fg="#6EE7B7"
          bg="rgba(16,185,129,0.12)"
          border="rgba(16,185,129,0.45)"
        />
      </View>
    );
  }

  return (
    <View style={styles.detailRowNoBorder}>
      <Text style={styles.detailLabel}>Expiry Verification</Text>
      <Badge
        label="NO REGISTRY MATCH"
        fg="#FCA5A5"
        bg="rgba(239,68,68,0.12)"
        border="rgba(239,68,68,0.45)"
      />
    </View>
  );
}

// ── Result screen ───────────────────────────────────────────────────────────

function ResultScreen({
  result,
  image,
  onReset,
}: {
  result: VerifyResponse;
  image: ScanImage | null;
  onReset: () => void;
}) {
  const meta = VERDICT_META[result.verdict] ?? VERDICT_META.FAILED;
  const layer1 = result.layer1_database_check;
  const layer2 = result.layer2_visual_check;
  const record = layer1.matched_record;
  const defects = Array.isArray(layer2.detected_defects) ? layer2.detected_defects : [];
  const gatePassed = layer1.status === "PASSED";
  const cloneReason = (layer1.reasons ?? []).some((reason) => /clone/i.test(reason));
  const sRule = gatePassed ? 100 : cloneReason ? 50 : 0;
  const score = Number.isFinite(result.authenticity_score) ? result.authenticity_score : 0;
  const scorePct = Math.max(0, Math.min(100, score));

  return (
    <ScrollView style={styles.resultScroll} contentContainerStyle={styles.resultWrap}>
      {image ? <DefectImageCard image={image} defects={defects} /> : null}

      <View style={[styles.verdictBanner, { borderColor: `${meta.color}66`, backgroundColor: `${meta.color}14` }]}>
        <View style={[styles.verdictIconWrap, { backgroundColor: `${meta.color}22` }]}>
          {result.verdict === "GENUINE" ? (
            <ShieldCheckIcon size={26} color={meta.color} />
          ) : (
            <AlertTriangleIcon size={26} color={meta.color} />
          )}
        </View>
        <View style={styles.verdictTextWrap}>
          <Text style={[styles.verdictTitle, { color: meta.color }]}>{meta.title}</Text>
          <Text style={styles.verdictSubtitle}>{meta.subtitle}</Text>
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Authenticity Score</Text>
        <View style={styles.scoreRow}>
          <Text style={[styles.scoreValue, { color: meta.color }]}>{score.toFixed(1)}</Text>
          <Text style={styles.scoreMax}>/ 100</Text>
        </View>
        <View style={styles.scoreMeter}>
          <View style={[styles.scoreMeterFill, { width: `${scorePct}%`, backgroundColor: meta.color }]} />
        </View>
        <ScoreBar
          label="Print Forensics (S_visual)"
          value={layer2.print_quality_score}
          color={COLORS.cyan}
        />
        <ScoreBar
          label="Registry Check (S_rule)"
          value={sRule}
          color={gatePassed ? COLORS.emerald : COLORS.red}
        />
        {result.technical_summary ? (
          <Text style={styles.summaryText}>{result.technical_summary}</Text>
        ) : null}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Batch & Registry Details</Text>
        {record ? (
          <>
            <DetailRow label="Brand" value={record.brand_name || "Unknown"} />
            <DetailRow label="Manufacturer" value={record.manufacturer ?? "Not listed"} />
            <DetailRow label="Batch No" value={record.batch_number} mono />
            <DetailRow label="GTIN" value={record.gtin ?? "Not encoded"} mono />
            <View style={styles.detailRowNoBorder}>
              <Text style={styles.detailLabel}>DRAP Status</Text>
              <Badge {...drapBadgeProps(record.drap_status)} />
            </View>
            <ExpiryRow layer1={layer1} />
          </>
        ) : (
          <View style={styles.unregisteredBox}>
            <AlertTriangleIcon size={18} color={COLORS.red} />
            <Text style={styles.unregisteredText}>
              Batch not found in the DRAP registry — treated as an unregistered product
            </Text>
          </View>
        )}
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Micro-Texture Print Forensics</Text>
        {defects.length === 0 ? (
          <View style={styles.cleanRow}>
            <CheckCircleIcon size={18} color={COLORS.emerald} />
            <Text style={styles.cleanText}>
              Clean industrial offset print — no micro-texture defects detected
            </Text>
          </View>
        ) : (
          <View>
            {defects.map((defect, index) => (
              <View
                key={`${defect.label}-${index}`}
                style={[styles.defectRow, index === defects.length - 1 && styles.defectRowLast]}
              >
                <View style={styles.defectDot} />
                <Text style={styles.defectLabel} numberOfLines={2}>
                  {defect.label}
                </Text>
                <Text style={styles.defectConfidence}>
                  {Math.round((defect.confidence ?? 0) * 100)}%
                </Text>
              </View>
            ))}
          </View>
        )}
      </View>

      <View style={styles.requestChip}>
        <Text style={styles.requestText}>Request {result.request_id}</Text>
      </View>

      <Pressable
        style={({ pressed }) => [styles.resetButton, pressed && styles.pressDim]}
        onPress={onReset}
      >
        <Text style={styles.resetButtonText}>Scan Another Medicine</Text>
      </Pressable>
    </ScrollView>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  // Root
  safe: { flex: 1, backgroundColor: COLORS.background },

  // Shared cards
  card: {
    backgroundColor: COLORS.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 16,
    marginBottom: 14,
  },
  cardTitle: {
    color: COLORS.text,
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 12,
    letterSpacing: 0.3,
  },

  // Defect image + bounding boxes
  imageWrap: {
    borderRadius: 12,
    overflow: "hidden",
    alignItems: "center",
    backgroundColor: "#0A0D15",
  },
  bbox: { position: "absolute", borderWidth: 2, borderColor: COLORS.red, borderRadius: 4 },
  bboxTag: {
    position: "absolute",
    backgroundColor: "rgba(0,0,0,0.85)",
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
  bboxTagAbove: { bottom: "100%", marginBottom: 4, left: -2 },
  bboxTagInside: { left: 2, top: 2 },
  bboxTagText: { color: COLORS.white, fontSize: 10, fontWeight: "700" },
  legend: { marginTop: 12 },
  legendRow: { flexDirection: "row", alignItems: "center", marginBottom: 6 },
  legendIndex: {
    width: 18,
    height: 18,
    borderRadius: 5,
    backgroundColor: COLORS.red,
    alignItems: "center",
    justifyContent: "center",
  },
  legendIndexText: { color: COLORS.white, fontSize: 10, fontWeight: "700" },
  legendLabel: { flex: 1, color: COLORS.text, fontSize: 13, marginLeft: 8 },
  legendConfidence: { color: COLORS.textMuted, fontSize: 12 },

  // Web upload zone / permission gate wrapper
  webWrap: {
    flex: 1,
    padding: 20,
    maxWidth: 640,
    width: "100%",
    alignSelf: "center",
    justifyContent: "center",
  },
  webHeader: { alignItems: "center", marginBottom: 20 },
  brandRow: { flexDirection: "row", alignItems: "center" },
  badgeDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: COLORS.cyan,
    marginRight: 8,
  },
  badgeText: { color: COLORS.text, fontSize: 20, fontWeight: "800", letterSpacing: 2 },
  badgeSubtitle: { color: COLORS.textMuted, fontSize: 12, marginTop: 4, letterSpacing: 0.5 },

  dropZone: {
    borderRadius: 18,
    borderWidth: 2,
    borderColor: COLORS.border,
    backgroundColor: "#0E1420",
    overflow: "hidden",
  },
  dropZoneActive: { borderColor: COLORS.cyan, backgroundColor: "#0C1B26" },
  dropReticle: { position: "absolute", top: 18, left: 18, right: 18, bottom: 18 },
  corner: { position: "absolute", width: 34, height: 34, borderColor: COLORS.cyan, borderWidth: 3 },
  cornerTL: { top: 0, left: 0, borderRightWidth: 0, borderBottomWidth: 0, borderTopLeftRadius: 10 },
  cornerTR: { top: 0, right: 0, borderLeftWidth: 0, borderBottomWidth: 0, borderTopRightRadius: 10 },
  cornerBL: { bottom: 0, left: 0, borderRightWidth: 0, borderTopWidth: 0, borderBottomLeftRadius: 10 },
  cornerBR: { bottom: 0, right: 0, borderLeftWidth: 0, borderTopWidth: 0, borderBottomRightRadius: 10 },
  dropPress: { alignItems: "center", justifyContent: "center", paddingVertical: 56, paddingHorizontal: 24 },
  dropTitle: { color: COLORS.text, fontSize: 17, fontWeight: "700", marginTop: 14 },
  dropTitleActive: { color: COLORS.cyan },
  dropHint: {
    color: COLORS.textMuted,
    fontSize: 12,
    marginTop: 6,
    textAlign: "center",
    maxWidth: 320,
  },
  zoneDisabled: { opacity: 0.5 },
  pressDim: { opacity: 0.75 },

  banner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(6,182,212,0.08)",
    borderWidth: 1,
    borderColor: "rgba(6,182,212,0.35)",
    borderRadius: 12,
    padding: 12,
    marginTop: 16,
  },
  bannerText: { color: "#7DE3F4", fontSize: 12, marginLeft: 8, flex: 1 },

  // Permission gate
  gateIconWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "rgba(6,182,212,0.12)",
    borderWidth: 1,
    borderColor: "rgba(6,182,212,0.35)",
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
    marginBottom: 14,
  },
  gateTitle: {
    color: COLORS.text,
    fontSize: 17,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 8,
  },
  gateMessage: {
    color: COLORS.textMuted,
    fontSize: 13,
    lineHeight: 19,
    textAlign: "center",
    marginBottom: 18,
  },
  primaryButton: {
    backgroundColor: COLORS.cyan,
    borderRadius: 12,
    paddingVertical: 13,
    alignItems: "center",
    marginBottom: 10,
  },
  primaryButtonText: { color: "#04222B", fontSize: 14, fontWeight: "800" },
  ghostButton: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingVertical: 13,
    alignItems: "center",
  },
  ghostButtonText: { color: COLORS.text, fontSize: 14, fontWeight: "600" },

  // Native camera viewfinder
  camera: { flex: 1, backgroundColor: "#000000" },
  camTopBar: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  camBadge: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(11,15,25,0.72)",
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 6,
    alignSelf: "flex-start",
  },
  camBadgeText: { color: COLORS.text, fontSize: 13, fontWeight: "800", letterSpacing: 1.5 },
  camBadgeSub: {
    color: "rgba(231,236,245,0.75)",
    fontSize: 10,
    marginTop: 4,
    letterSpacing: 0.4,
  },
  camTopActions: { flexDirection: "row" },
  iconButton: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "rgba(11,15,25,0.72)",
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 10,
  },
  iconButtonActive: { backgroundColor: "rgba(6,182,212,0.9)" },

  reticleHolder: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
  },
  reticle: { width: "75%", aspectRatio: 4 / 3 },
  camBottom: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    paddingBottom: 20,
    paddingTop: 12,
  },
  guidanceChip: {
    alignSelf: "center",
    backgroundColor: "rgba(11,15,25,0.82)",
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(6,182,212,0.4)",
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginBottom: 20,
  },
  guidanceChipText: { color: "#7DE3F4", fontSize: 12 },
  camControls: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 28,
  },
  sideButton: {
    width: 64,
    height: 64,
    borderRadius: 16,
    backgroundColor: "rgba(17,24,39,0.88)",
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 6,
  },
  sideButtonActive: { borderColor: COLORS.cyan, backgroundColor: "rgba(6,182,212,0.18)" },
  sideLabel: {
    color: COLORS.textMuted,
    fontSize: 9,
    marginTop: 4,
    textAlign: "center",
    lineHeight: 11,
  },
  sideLabelActive: { color: COLORS.cyan, fontWeight: "700" },
  shutterHit: { width: 96, height: 96, alignItems: "center", justifyContent: "center" },
  shutterPulse: {
    position: "absolute",
    width: 78,
    height: 78,
    borderRadius: 39,
    borderWidth: 2,
    borderColor: COLORS.cyan,
  },
  shutterOuter: {
    width: 78,
    height: 78,
    borderRadius: 39,
    borderWidth: 4,
    borderColor: COLORS.cyan,
    alignItems: "center",
    justifyContent: "center",
  },
  shutter: { width: 60, height: 60, borderRadius: 30, backgroundColor: COLORS.white },

  // Scanning HUD
  hudBackdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(5,8,15,0.9)",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  hudRing: { width: 84, height: 84 },
  hudRingTrack: {
    position: "absolute",
    width: 84,
    height: 84,
    borderRadius: 42,
    borderWidth: 4,
    borderColor: "rgba(6,182,212,0.18)",
  },
  hudRingArc: {
    width: 84,
    height: 84,
    borderRadius: 42,
    borderWidth: 4,
    borderColor: COLORS.cyan,
    borderRightColor: "transparent",
    borderTopColor: "transparent",
    borderBottomColor: "transparent",
  },
  hudTitle: { color: COLORS.text, fontSize: 18, fontWeight: "800", marginTop: 24, letterSpacing: 0.5 },
  hudStep: { color: COLORS.cyan, fontSize: 13, marginTop: 10, textAlign: "center" },
  hudDots: { flexDirection: "row", marginTop: 16 },
  hudDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: "rgba(139,152,172,0.35)",
    marginHorizontal: 4,
  },
  hudDotActive: { backgroundColor: COLORS.cyan },

  // Error sheet
  sheetBackdrop: {
    flex: 1,
    backgroundColor: "rgba(5,8,15,0.78)",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  sheetCard: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: COLORS.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 20,
  },
  sheetIconRow: { flexDirection: "row", alignItems: "center", marginBottom: 10 },
  sheetTitle: { color: COLORS.text, fontSize: 17, fontWeight: "700", marginLeft: 10, flex: 1 },
  sheetMessage: { color: COLORS.textMuted, fontSize: 13, lineHeight: 19 },
  sheetActions: { flexDirection: "row", marginTop: 18, alignItems: "center" },
  sheetButton: {
    flex: 1,
    backgroundColor: COLORS.cyan,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    marginRight: 10,
  },
  sheetButtonText: { color: "#04222B", fontWeight: "800", fontSize: 14 },
  sheetButtonGhost: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: "center",
  },
  sheetButtonGhostText: { color: COLORS.textMuted, fontWeight: "600", fontSize: 14 },

  // Result screen
  resultScroll: { flex: 1, backgroundColor: COLORS.background },
  resultWrap: {
    padding: 16,
    paddingBottom: 44,
    maxWidth: 640,
    width: "100%",
    alignSelf: "center",
  },
  verdictBanner: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: 16,
    borderWidth: 1.5,
    padding: 16,
    marginBottom: 14,
  },
  verdictIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  verdictTextWrap: { flex: 1 },
  verdictTitle: { fontSize: 18, fontWeight: "800", letterSpacing: 0.5 },
  verdictSubtitle: { color: COLORS.textMuted, fontSize: 12, marginTop: 3 },
  scoreRow: { flexDirection: "row", alignItems: "flex-end", marginBottom: 10 },
  scoreValue: { fontSize: 44, fontWeight: "900", lineHeight: 46 },
  scoreMax: { color: COLORS.textMuted, fontSize: 16, fontWeight: "700", marginLeft: 6, marginBottom: 7 },
  scoreMeter: {
    height: 8,
    borderRadius: 4,
    backgroundColor: "rgba(139,152,172,0.18)",
    overflow: "hidden",
  },
  scoreMeterFill: { height: 8, borderRadius: 4 },
  forensicRow: { marginTop: 12 },
  forensicHeader: { flexDirection: "row", justifyContent: "space-between", marginBottom: 5 },
  forensicLabel: { color: COLORS.textMuted, fontSize: 12 },
  forensicValue: { color: COLORS.text, fontSize: 12, fontWeight: "700" },
  summaryText: { color: COLORS.textMuted, fontSize: 12, lineHeight: 18, marginTop: 14 },

  detailRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 9,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border,
  },
  detailRowNoBorder: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 9,
  },
  detailLabel: { color: COLORS.textMuted, fontSize: 12 },
  detailValue: {
    color: COLORS.text,
    fontSize: 13,
    fontWeight: "600",
    flexShrink: 1,
    marginLeft: 12,
    textAlign: "right",
  },
  detailMono: {
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace" }) ?? "monospace",
    fontSize: 12,
  },
  badge: { borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4, borderWidth: 1 },
  badgeChipText: { fontSize: 10, fontWeight: "700", letterSpacing: 0.3 },
  expiryBlock: { marginTop: 2 },
  expiryNote: { color: COLORS.textMuted, fontSize: 11, marginTop: 2 },
  unregisteredBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(239,68,68,0.1)",
    borderWidth: 1,
    borderColor: "rgba(239,68,68,0.4)",
    borderRadius: 12,
    padding: 12,
  },
  unregisteredText: { color: "#FCA5A5", fontSize: 12, marginLeft: 10, flex: 1 },
  cleanRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "rgba(16,185,129,0.08)",
    borderWidth: 1,
    borderColor: "rgba(16,185,129,0.35)",
    borderRadius: 12,
    padding: 12,
  },
  cleanText: { color: "#6EE7B7", fontSize: 12, marginLeft: 10, flex: 1 },
  defectRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 9,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border,
  },
  defectRowLast: { borderBottomWidth: 0 },
  defectDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: COLORS.red },
  defectLabel: { color: COLORS.text, fontSize: 13, marginLeft: 10, flex: 1 },
  defectConfidence: { color: COLORS.textMuted, fontSize: 12, marginLeft: 8 },
  requestChip: {
    alignSelf: "center",
    marginTop: 2,
    marginBottom: 14,
    backgroundColor: "rgba(139,152,172,0.1)",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  requestText: { color: COLORS.textMuted, fontSize: 10 },
  resetButton: {
    backgroundColor: COLORS.cyan,
    borderRadius: 14,
    paddingVertical: 15,
    alignItems: "center",
    justifyContent: "center",
  },
  resetButtonText: { color: "#04222B", fontSize: 15, fontWeight: "800", letterSpacing: 0.3 },
});
