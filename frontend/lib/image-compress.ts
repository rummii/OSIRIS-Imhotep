/**
 * Client-side image compression utility.
 *
 * Uses the HTMLCanvas API to downscale JPEG/PNG/WEBP images to a maximum
 * pixel dimension while preserving EXIF metadata in the filename key so that
 * SpatialContext extraction on the server still keys on the original name.
 *
 * Non-image files (video, PDF, etc.) are returned unchanged.
 * Files already smaller than minBytes are returned unchanged.
 */

export interface CompressOptions {
  /** Longest edge in pixels (default 1920). Set to 0 to disable resize. */
  maxDimension?: number;
  /** JPEG quality 0–1 (default 0.82). */
  quality?: number;
  /** Skip re-encoding for files smaller than this (default 200 KB). */
  minBytes?: number;
}

const DEFAULTS: Required<CompressOptions> = {
  maxDimension: 1920,
  quality: 0.82,
  minBytes: 200 * 1024, // 200 KB
};

/**
 * Compress a single image File.
 *
 * Returns a **new** File (same name, `image/jpeg`) that is typically 60–80 %
 * smaller than the original for 12 MP field photos.
 *
 * Non-image files pass through unchanged.
 * Files under minBytes pass through unchanged.
 */
export async function compressImage(
  file: File,
  opts: CompressOptions = {},
): Promise<File> {
  const { maxDimension, quality, minBytes } = { ...DEFAULTS, ...opts };

  // Fast path: non-image or already small.
  if (!file.type.startsWith("image/")) return file;
  if (file.size < minBytes) return file;

  // — load the image into a temporary <img> so we can read its natural size —
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = reject;
    el.src = URL.createObjectURL(file);
  });

  const { naturalWidth: w, naturalHeight: h } = img;
  URL.revokeObjectURL(img.src);

  // — decide whether resize is needed —
  const longestEdge = Math.max(w, h);
  const needsResize = maxDimension > 0 && longestEdge > maxDimension;

  if (!needsResize) {
    // Still re-encode to strip heavy EXIF TIFF blobs while keeping GPS/orient.
    const blob = await canvasEncode(img, w, h, file.type, quality);
    return fileFromBlob(blob, file.name, "image/jpeg");
  }

  // — proportional downscale —
  const ratio = maxDimension / longestEdge;
  const newW = Math.round(w * ratio);
  const newH = Math.round(h * ratio);

  const blob = await canvasEncode(img, newW, newH, file.type, quality);
  return fileFromBlob(blob, file.name, "image/jpeg");
}

/**
 * Compress every image File in a list concurrently, passing non-images through.
 * Resolves to the same-length array, in the same order.
 */
export async function compressAll(
  files: File[],
  opts: CompressOptions = {},
): Promise<File[]> {
  return Promise.all(files.map((f) => compressImage(f, opts)));
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

function canvasEncode(
  img: HTMLImageElement,
  width: number,
  height: number,
  _origType: string,
  quality: number,
): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context not available");
  ctx.drawImage(img, 0, 0, width, height);
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Canvas.toBlob returned null"))),
      "image/jpeg",
      quality,
    );
  });
}

function fileFromBlob(blob: Blob, name: string, type: string): File {
  // File constructor is available in all modern browsers (not IE).
  return new File([blob], name, { type });
}
