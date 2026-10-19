"use client";

import { useOperationalText as useUiText } from "@/lib/i18n/operational";

import { Crop, ScanLine, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

type CropBox = { x: number; y: number; width: number; height: number };
type PhotoSource = "PASSPORT_AUTO_CROP" | "PASSPORT_MANUAL_CROP";

const initialCrop: CropBox = { x: 5, y: 15, width: 30, height: 55 };

export function PassportScanAssistant({
  file,
  setFile,
  mrz,
  setMrz,
  onPhoto,
  photoEnabled = true,
}: Readonly<{
  file: File | null;
  setFile: (file: File | null) => void;
  mrz: string;
  setMrz: (value: string) => void;
  onPhoto: (file: File, source: PhotoSource) => void;
  photoEnabled?: boolean;
}>) {
  const uiText = useUiText();
  const imageRef = useRef<HTMLImageElement>(null);
  const [preview, setPreview] = useState("");
  const [crop, setCrop] = useState<CropBox>(initialCrop);
  const [autoCrop, setAutoCrop] = useState(false);
  const [ocrProgress, setOcrProgress] = useState(0);
  const [ocrStatus, setOcrStatus] = useState("");
  const [error, setError] = useState("");
  const dragStart = useRef<{ x: number; y: number } | null>(null);
  const [selecting, setSelecting] = useState(false);

  useEffect(() => {
    if (!file || !file.type.startsWith("image/")) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    setCrop(initialCrop);
    setAutoCrop(false);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const selectionPoint = (event: ReactPointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(100, ((event.clientX - bounds.left) / bounds.width) * 100),
      ),
      y: Math.max(
        0,
        Math.min(100, ((event.clientY - bounds.top) / bounds.height) * 100),
      ),
    };
  };

  const startSelection = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!photoEnabled) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStart.current = selectionPoint(event);
    setSelecting(true);
    setAutoCrop(false);
  };

  const updateSelection = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragStart.current || !selecting) return;
    const start = dragStart.current;
    const current = selectionPoint(event);
    setCrop({
      x: Math.min(start.x, current.x),
      y: Math.min(start.y, current.y),
      width: Math.max(Math.abs(current.x - start.x), 1),
      height: Math.max(Math.abs(current.y - start.y), 1),
    });
  };

  const finishSelection = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!dragStart.current) return;
    updateSelection(event);
    dragStart.current = null;
    setSelecting(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const detectFace = async () => {
    const image = imageRef.current;
    if (!image) return;
    setError("");
    try {
      const Detector = (
        window as unknown as {
          FaceDetector?: new (options: {
            fastMode: boolean;
            maxDetectedFaces: number;
          }) => {
            detect: (
              source: HTMLImageElement,
            ) => Promise<Array<{ boundingBox: DOMRectReadOnly }>>;
          };
        }
      ).FaceDetector;
      if (!Detector)
        throw new Error(
          "Automatic face detection is unavailable in this browser. Adjust the crop manually.",
        );
      const result = await new Detector({
        fastMode: true,
        maxDetectedFaces: 1,
      }).detect(image);
      if (!result.length)
        throw new Error("No face was detected. Adjust the crop manually.");
      const box = result[0].boundingBox;
      const paddingX = box.width * 0.45;
      const paddingTop = box.height * 0.35;
      const paddingBottom = box.height * 0.55;
      const x = Math.max(0, box.x - paddingX);
      const y = Math.max(0, box.y - paddingTop);
      const width = Math.min(image.naturalWidth - x, box.width + paddingX * 2);
      const height = Math.min(
        image.naturalHeight - y,
        box.height + paddingTop + paddingBottom,
      );
      setCrop({
        x: (x / image.naturalWidth) * 100,
        y: (y / image.naturalHeight) * 100,
        width: (width / image.naturalWidth) * 100,
        height: (height / image.naturalHeight) * 100,
      });
      setAutoCrop(true);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Face detection failed.",
      );
    }
  };

  const useCroppedPhoto = async () => {
    const image = imageRef.current;
    if (!image) return;
    const canvas = document.createElement("canvas");
    const sourceX = (image.naturalWidth * crop.x) / 100;
    const sourceY = (image.naturalHeight * crop.y) / 100;
    const sourceWidth = (image.naturalWidth * crop.width) / 100;
    const sourceHeight = (image.naturalHeight * crop.height) / 100;
    canvas.width = 600;
    canvas.height = Math.max(
      600,
      Math.round((600 * sourceHeight) / sourceWidth),
    );
    canvas
      .getContext("2d")
      ?.drawImage(
        image,
        sourceX,
        sourceY,
        sourceWidth,
        sourceHeight,
        0,
        0,
        canvas.width,
        canvas.height,
      );
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.9),
    );
    if (!blob) {
      setError("The cropped photo could not be created.");
      return;
    }
    onPhoto(
      new File([blob], "traveler-passport-photo.jpg", { type: "image/jpeg" }),
      autoCrop ? "PASSPORT_AUTO_CROP" : "PASSPORT_MANUAL_CROP",
    );
    setOcrStatus(
      "Traveler photo is ready and will be saved with the passport.",
    );
  };

  const runOcr = async () => {
    if (!file?.type.startsWith("image/")) return;
    setError("");
    setOcrProgress(0);
    setOcrStatus("Loading local OCR…");
    let worker: Awaited<
      ReturnType<(typeof import("tesseract.js"))["createWorker"]>
    > | null = null;
    try {
      const { createWorker } = await import("tesseract.js");
      worker = await createWorker("eng", 1, {
        logger: (message) => {
          if (typeof message.progress === "number")
            setOcrProgress(Math.round(message.progress * 100));
          if (message.status) setOcrStatus(message.status);
        },
      });
      await worker.setParameters({
        tessedit_char_whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<",
        preserve_interword_spaces: "1",
      });
      const result = await worker.recognize(file);
      const detected = extractMrz(result.data.text);
      if (!detected)
        throw new Error(
          "MRZ was not detected reliably. Use a clearer image or paste the scanner text.",
        );
      setMrz(detected);
      setOcrStatus(
        "MRZ detected locally. Verify it, then detect passport data.",
      );
      setOcrProgress(100);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Passport OCR failed.",
      );
    } finally {
      await worker?.terminate();
    }
  };

  return (
    <div className="space-y-4 rounded-xl border bg-slate-50 p-4">
      <label className="block text-sm font-medium">
        {uiText("Passport scan")}
        <input
          type="file"
          accept="image/*,.pdf"
          className="mt-1 block w-full rounded-lg border bg-white px-3 py-2"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </label>
      {file && (
        <p className="text-xs text-slate-500">
          {file.name}{" "}
          {uiText("· OCR and photo crop run locally before upload.")}
        </p>
      )}
      {preview && (
        <>
          <div
            className={`relative touch-none overflow-hidden rounded-lg border bg-slate-900 ${photoEnabled ? "cursor-crosshair" : ""}`}
            onPointerDown={startSelection}
            onPointerMove={updateSelection}
            onPointerUp={finishSelection}
            onPointerCancel={finishSelection}
          >
            <img
              ref={imageRef}
              src={preview}
              alt={uiText("Passport scan preview")}
              draggable={false}
              className="pointer-events-none block w-full select-none"
            />
            <div
              className="pointer-events-none absolute border-2 border-cyan-400 bg-cyan-300/10"
              style={{
                left: `${crop.x}%`,
                top: `${crop.y}%`,
                width: `${crop.width}%`,
                height: `${crop.height}%`,
              }}
            />
          </div>
          {photoEnabled && (
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
              <span>
                {selecting
                  ? uiText("Release to set the passenger photo area.")
                  : uiText(
                      "Click and drag over the passenger photo, then release.",
                    )}
              </span>
              <button
                type="button"
                onClick={() => {
                  setCrop(initialCrop);
                  setAutoCrop(false);
                }}
                className="rounded border border-slate-300 bg-white px-2 py-1 font-medium text-slate-700 hover:bg-slate-100"
              >
                {uiText("Reset crop")}
              </button>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={runOcr}
              className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium text-cyan-800"
            >
              <ScanLine className="size-4" />
              {uiText("Read MRZ with local OCR")}
            </button>
            {photoEnabled && (
              <>
                <button
                  type="button"
                  onClick={detectFace}
                  className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium"
                >
                  <UserRound className="size-4" />
                  {uiText("Detect face")}
                </button>
                <button
                  type="button"
                  onClick={useCroppedPhoto}
                  className="inline-flex items-center gap-2 rounded-lg border bg-white px-3 py-2 text-sm font-medium"
                >
                  <Crop className="size-4" />
                  {uiText("Use cropped photo")}
                </button>
              </>
            )}
          </div>
        </>
      )}
      {(ocrStatus || ocrProgress > 0) && (
        <div>
          <p className="text-xs text-slate-600">{uiText(ocrStatus)}</p>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-slate-200">
            <div
              className="h-full bg-cyan-700"
              style={{ width: `${ocrProgress}%` }}
            />
          </div>
        </div>
      )}
      {error && (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
          {uiText(error)}
        </p>
      )}
      <label className="block text-sm font-medium">
        {uiText("MRZ / scanner text")}
        <textarea
          dir="ltr"
          style={{ textAlign: "left", unicodeBidi: "isolate" }}
          className="mt-1 min-h-20 w-full rounded-lg border bg-white px-3 py-2 font-mono text-xs"
          value={mrz}
          onChange={(event) => setMrz(event.target.value)}
          placeholder={uiText("Two 44-character TD3 MRZ lines")}
        />
      </label>
    </div>
  );
}

function extractMrz(text: string): string | null {
  const lines = text
    .split(/\r?\n/)
    .map((line) =>
      line
        .toUpperCase()
        .replace(/\s/g, "")
        .replace(/[^A-Z0-9<]/g, ""),
    )
    .filter((line) => line.length >= 35);
  for (let index = 0; index < lines.length - 1; index += 1) {
    if (lines[index].startsWith("P") && lines[index + 1].length >= 40)
      return `${lines[index].slice(0, 44)}\n${lines[index + 1].slice(0, 44)}`;
  }
  const candidates = lines.filter((line) => line.includes("<")).slice(-2);
  return candidates.length === 2
    ? `${candidates[0].slice(0, 44)}\n${candidates[1].slice(0, 44)}`
    : null;
}
