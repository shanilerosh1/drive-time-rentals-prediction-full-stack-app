import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class DownloadService {
  /** Saves a fetched blob under `filename`, then releases the object URL. */
  save(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}
