import * as fs from 'fs';
import * as crypto from 'crypto';

/**
 * Computes SHA-256 hash of a file or chunk
 */
export async function computeFileHash(filePath: string, sampleSize?: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash('sha256');
    const stream = sampleSize
      ? fs.createReadStream(filePath, { start: 0, end: sampleSize - 1 })
      : fs.createReadStream(filePath);

    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('end', () => resolve(hash.digest('hex')));
    stream.on('error', (err) => reject(err));
  });
}

/**
 * Two-stage fast deduplicator optimized for large multi-hundred-gigabyte drives:
 * 1. Groups by exact file size in bytes (skips 90% of unique files with 0 disk I/O)
 * 2. Compares 64 KB header hash for size collisions
 * 3. Compares full SHA-256 only if headers match
 */
export class FastDeduplicator {
  private sizeMap = new Map<number, string[]>();
  private duplicates = new Map<string, string>(); // duplicatePath -> originalPath
  private duplicateBytes = 0;

  /**
   * Register a file's size during initial directory traversal
   */
  public registerFile(filePath: string, size: number): void {
    if (size <= 0) return;
    const existing = this.sizeMap.get(size);
    if (existing) {
      existing.push(filePath);
    } else {
      this.sizeMap.set(size, [filePath]);
    }
  }

  /**
   * Analyze all registered files and resolve true duplicates
   * @param onProgress optional callback for progress updates
   */
  public async analyzeDuplicates(
    onProgress?: (checked: number, totalCandidates: number, dupes: number) => void
  ): Promise<{
    duplicateMap: Map<string, string>;
    totalDuplicateBytes: number;
    duplicateCount: number;
  }> {
    // Filter to only sizes that have 2 or more files
    const candidateGroups: Array<{ size: number; files: string[] }> = [];
    let totalCandidateFiles = 0;

    for (const [size, files] of this.sizeMap.entries()) {
      if (files.length > 1) {
        candidateGroups.push({ size, files });
        totalCandidateFiles += files.length;
      }
    }

    let processedCount = 0;
    const PARTIAL_SAMPLE_SIZE = 64 * 1024; // 64 KB

    for (const group of candidateGroups) {
      // Group by partial hash
      const partialHashMap = new Map<string, string[]>();

      for (const file of group.files) {
        processedCount++;
        if (onProgress && processedCount % 50 === 0) {
          onProgress(processedCount, totalCandidateFiles, this.duplicates.size);
        }

        try {
          const partialHash = await computeFileHash(file, PARTIAL_SAMPLE_SIZE);
          const list = partialHashMap.get(partialHash);
          if (list) {
            list.push(file);
          } else {
            partialHashMap.set(partialHash, [file]);
          }
        } catch {
          // File read error, skip
        }
      }

      // For matching partial hashes, verify with full SHA-256
      for (const [, matchingFiles] of partialHashMap.entries()) {
        if (matchingFiles.length <= 1) continue;

        const fullHashMap = new Map<string, string>();

        for (const file of matchingFiles) {
          try {
            const fullHash = await computeFileHash(file);
            if (fullHashMap.has(fullHash)) {
              const original = fullHashMap.get(fullHash)!;
              this.duplicates.set(file, original);
              this.duplicateBytes += group.size;
            } else {
              fullHashMap.set(fullHash, file);
            }
          } catch {
            // Skip unreadable files
          }
        }
      }
    }

    if (onProgress) {
      onProgress(processedCount, totalCandidateFiles, this.duplicates.size);
    }

    return {
      duplicateMap: this.duplicates,
      totalDuplicateBytes: this.duplicateBytes,
      duplicateCount: this.duplicates.size
    };
  }

  public isDuplicate(filePath: string): boolean {
    return this.duplicates.has(filePath);
  }

  public getOriginal(filePath: string): string | undefined {
    return this.duplicates.get(filePath);
  }
}
