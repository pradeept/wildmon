const MAX_EDGE = 1600;
const TARGET_BYTES = 2 * 1024 * 1024;

function jpegBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (value) => (value ? resolve(value) : reject(new Error('Could not prepare photo.'))),
      'image/jpeg',
      quality,
    );
  });
}

/** Resize before upload; lower JPEG quality only when the encoded photo remains large. */
export async function prepareImage(file: File): Promise<File> {
  const image = new Image();
  const url = URL.createObjectURL(file);
  try {
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('Could not read this photo.'));
      image.src = url;
    });
    let blob: Blob | null = null;
    for (const edge of [MAX_EDGE, 1200, 960]) {
      const scale = Math.min(1, edge / Math.max(image.width, image.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(image.width * scale);
      canvas.height = Math.round(image.height * scale);
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Could not prepare photo.');
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      for (const quality of [0.84, 0.72, 0.6]) {
        blob = await jpegBlob(canvas, quality);
        if (blob.size <= TARGET_BYTES) {
          return new File([blob], 'wildmon-capture.jpg', { type: 'image/jpeg' });
        }
      }
    }
    if (!blob || blob.size > TARGET_BYTES) {
      throw new Error('This photo is too large to upload. Try another photo.');
    }
    return new File([blob], 'wildmon-capture.jpg', { type: 'image/jpeg' });
  } finally {
    URL.revokeObjectURL(url);
  }
}
