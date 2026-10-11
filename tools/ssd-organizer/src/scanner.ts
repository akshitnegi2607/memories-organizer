import * as fs from 'fs';
import * as path from 'path';
import { PhotoMetadata, OrganizeOptions, OrganizeStats } from './types.js';
import { isSupportedMedia, extractMetadata } from './exifExtractor.js';
import { FastDeduplicator } from './deduplicator.js';
import { organizeFile } from './fileOrganizer.js';

export async function runIngestion(
  options: OrganizeOptions,
  onProgress?: (msg: string) => void
): Promise<OrganizeStats> {
  const stats: OrganizeStats = {
    totalScanned: 0,
    mediaFiles: 0,
    nonMediaSkipped: 0,
    duplicatesFound: 0,
    duplicateBytesSaved: 0,
    withLocation: 0,
    withoutLocation: 0,
    organizedCount: 0,
    errors: [],
    byYearMonth: {},
    byLocation: {},
    startTime: Date.now()
  };

  const deduplicator = new FastDeduplicator();
  const mediaPaths: string[] = [];

  // Step 1: Fast directory crawl & file size indexing
  if (onProgress) onProgress('🔍 Phase 1/3: Crawling source directory and indexing file sizes...');

  async function crawlDirectory(dir: string): Promise<void> {
    let entries: fs.Dirent[];
    try {
      entries = await fs.promises.readdir(dir, { withFileTypes: true });
    } catch (err: any) {
      stats.errors.push({ path: dir, error: `Directory read error: ${err.message}` });
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);

      // Skip hidden files/directories (like .DS_Store, .Trash, etc.)
      if (entry.name.startsWith('.')) continue;

      if (entry.isDirectory()) {
        await crawlDirectory(fullPath);
      } else if (entry.isFile()) {
        stats.totalScanned++;
        if (isSupportedMedia(fullPath)) {
          stats.mediaFiles++;
          mediaPaths.push(fullPath);

          if (options.dedup) {
            try {
              const fileStat = await fs.promises.stat(fullPath);
              deduplicator.registerFile(fullPath, fileStat.size);
            } catch {
              // Skip if stat fails
            }
          }
        } else {
          stats.nonMediaSkipped++;
        }

        if (stats.totalScanned % 1000 === 0 && onProgress) {
          onProgress(`   Scanned ${stats.totalScanned.toLocaleString()} files (${stats.mediaFiles.toLocaleString()} media found)...`);
        }
      }
    }
  }

  for (const dir of options.inputDirs) {
    if (fs.existsSync(dir)) {
      if (onProgress) onProgress(`📂 Scanning directory: ${dir}`);
      await crawlDirectory(dir);
    } else {
      stats.errors.push({ path: dir, error: 'Directory does not exist' });
    }
  }

  if (onProgress) {
    onProgress(`✅ Phase 1 complete: Found ${stats.mediaFiles.toLocaleString()} media files across ${stats.totalScanned.toLocaleString()} items.`);
  }

  // Step 2: Deduplication Analysis
  if (options.dedup && stats.mediaFiles > 0) {
    if (onProgress) onProgress('👯 Phase 2/3: Checking for duplicate photos and videos...');
    await deduplicator.analyzeDuplicates((checked, total, dupes) => {
      if (onProgress && checked % 200 === 0) {
        onProgress(`   Deduplicating: verified ${checked}/${total} candidate files (${dupes} duplicates detected)...`);
      }
    });
    if (onProgress) {
      onProgress(`✅ Phase 2 complete: Identified ${deduplicator['duplicates'].size} exact duplicate files.`);
    }
  }

  // Step 3: Metadata extraction & Organization planning
  if (onProgress) onProgress(`📦 Phase 3/3: Extracting dates, locations, and organizing ${stats.mediaFiles.toLocaleString()} files...`);

  const usedTargetPaths = new Set<string>();
  let processed = 0;

  for (const filePath of mediaPaths) {
    processed++;
    if (processed % 250 === 0 && onProgress) {
      onProgress(`   Organizing: ${processed.toLocaleString()} / ${stats.mediaFiles.toLocaleString()} (${((processed / stats.mediaFiles) * 100).toFixed(0)}%)...`);
      await new Promise(resolve => setImmediate(resolve));
    }

    if (processed % 500 === 0) {
      const elapsedSec = Math.max(1, Math.round((Date.now() - stats.startTime) / 1000));
      const remainingSec = Math.round((elapsedSec / processed) * (stats.mediaFiles - processed));
      const progressData = {
        phase: 'Organizing & Geocoding',
        processed,
        total: stats.mediaFiles,
        percent: Math.round((processed / stats.mediaFiles) * 100),
        duplicatesFound: deduplicator['duplicates'].size,
        elapsedSeconds: elapsedSec,
        estimatedRemainingSeconds: remainingSec
      };
      try {
        await fs.promises.mkdir(options.outputDir, { recursive: true });
        await fs.promises.writeFile(
          path.join(options.outputDir, 'progress.json'),
          JSON.stringify(progressData, null, 2),
          'utf8'
        );
      } catch {
        // ignore progress write error
      }
    }

    try {
      const meta = await extractMetadata(filePath, options.geo);

      if (options.dedup && deduplicator.isDuplicate(filePath)) {
        meta.isDuplicate = true;
        meta.duplicateOf = deduplicator.getOriginal(filePath);
      }

      await organizeFile(meta, options, stats, usedTargetPaths);
    } catch (err: any) {
      stats.errors.push({
        path: filePath,
        error: `Processing error: ${err.message}`
      });
    }
  }

  stats.endTime = Date.now();
  return stats;
}
