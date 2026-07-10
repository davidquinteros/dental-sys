/**
 * Client-side image compression.
 *
 * Photos are downscaled and re-encoded as JPEG in the browser *before* upload,
 * so the backend/storage only ever receives small files (~150-400KB) — no
 * server-side image library needed. See FCLI-10.
 */

export interface CompressResult {
  blob: Blob;
  filename: string;
}

const DEFAULT_MAX_DIM = 1600;   // px, longest side
const DEFAULT_QUALITY = 0.7;    // JPEG quality 0..1

/**
 * Load `file` into an image, scale it so its longest side is at most `maxDim`,
 * and re-encode as JPEG. Returns the compressed Blob plus a `.jpg` filename.
 */
export function compressImage(
  file: File,
  maxDim: number = DEFAULT_MAX_DIM,
  quality: number = DEFAULT_QUALITY,
): Promise<CompressResult> {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const img = new Image();

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);

      let { width, height } = img;
      if (width > maxDim || height > maxDim) {
        const scale = Math.min(maxDim / width, maxDim / height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }

      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('No se pudo procesar la imagen'));
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);

      canvas.toBlob(
        blob => {
          if (!blob) {
            reject(new Error('No se pudo comprimir la imagen'));
            return;
          }
          const base = (file.name.replace(/\.[^.]+$/, '') || 'foto');
          resolve({ blob, filename: `${base}.jpg` });
        },
        'image/jpeg',
        quality,
      );
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error('Archivo de imagen inválido'));
    };

    img.src = objectUrl;
  });
}
