import * as fs from 'fs';
import * as path from 'path';
import { PhotoMetadata, OrganizeOptions, OrganizeStats } from './types.js';
import { sanitizeFolderName } from './geoCoder.js';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

/**
 * Calculates target folder and file path based on date, location, and duplicate status
 */
export function planTargetPath(
  meta: PhotoMetadata,
  outputBaseDir: string,
  isDuplicate = false
): { targetDir: string; targetFileName: string; targetPath: string } {
  const d = meta.date;
  const year = d.getFullYear().toString();
  const monthNumber = (d.getMonth() + 1).toString().padStart(2, '0');
  const monthName = MONTH_NAMES[d.getMonth()];
  const day = d.getDate().toString().padStart(2, '0');
  const hours = d.getHours().toString().padStart(2, '0');
  const minutes = d.getMinutes().toString().padStart(2, '0');
  const seconds = d.getSeconds().toString().padStart(2, '0');

  let subfolderName: string;

  if (isDuplicate) {
    subfolderName = path.join('_Duplicates', year, `${year}-${monthNumber}_${monthName}`);
  } else if (meta.location) {
    const locTag = sanitizeFolderName(`${meta.location.city}_${meta.location.country}`);
    subfolderName = path.join(year, `${year}-${monthNumber}_${monthName}_${locTag}`);
  } else {
    subfolderName = path.join(year, `${year}-${monthNumber}_${monthName}`);
  }

  const targetDir = path.join(outputBaseDir, subfolderName);

  // Standardize filename: YYYY-MM-DD_HH-mm-ss_originalName.ext
  // Cleans duplicate prefixes if already present
  const baseName = path.basename(meta.fileName, meta.extension);
  const cleanBase = baseName.replace(/^\d{4}[-_]\d{2}[-_]\d{2}[-_]\d{2}[-_.]\d{2}[-_.]\d{2}_?/, '');
  const targetFileName = `${year}-${monthNumber}-${day}_${hours}-${minutes}-${seconds}_${cleanBase}${meta.extension.toLowerCase()}`;
  const targetPath = path.join(targetDir, targetFileName);

  return { targetDir, targetFileName, targetPath };
}

/**
 * Executes or simulates organizing a photo
 */
export async function organizeFile(
  meta: PhotoMetadata,
  options: OrganizeOptions,
  stats: OrganizeStats,
  usedPaths: Set<string>
): Promise<void> {
  const isDuplicate = !!meta.isDuplicate;
  const { targetDir, targetFileName } = planTargetPath(meta, options.outputDir, isDuplicate);

  // Avoid collisions with existing planned paths
  let finalFileName = targetFileName;
  let finalPath = path.join(targetDir, finalFileName);
  let counter = 1;

  while (usedPaths.has(finalPath)) {
    const ext = meta.extension.toLowerCase();
    const nameWithoutExt = path.basename(finalFileName, ext);
    finalFileName = `${nameWithoutExt}_${counter}${ext}`;
    finalPath = path.join(targetDir, finalFileName);
    counter++;
  }
  usedPaths.add(finalPath);

  meta.targetDir = targetDir;
  meta.targetFileName = finalFileName;
  meta.targetPath = finalPath;

  // Track statistics
  const yearMonth = `${meta.date.getFullYear()}-${(meta.date.getMonth() + 1).toString().padStart(2, '0')}`;
  stats.byYearMonth[yearMonth] = (stats.byYearMonth[yearMonth] || 0) + 1;

  if (meta.location) {
    const locKey = `${meta.location.city}, ${meta.location.country}`;
    stats.byLocation[locKey] = (stats.byLocation[locKey] || 0) + 1;
    stats.withLocation++;
  } else {
    stats.withoutLocation++;
  }

  if (isDuplicate) {
    stats.duplicatesFound++;
    stats.duplicateBytesSaved += meta.fileSize;
  } else {
    stats.organizedCount++;
  }

  // Perform physical copy or move if not in dry-run mode
  if (!options.dryRun) {
    try {
      await fs.promises.mkdir(targetDir, { recursive: true });

      if (options.action === 'move') {
        await fs.promises.rename(meta.sourcePath, finalPath);
      } else {
        await fs.promises.copyFile(meta.sourcePath, finalPath);
      }
    } catch (err: any) {
      stats.errors.push({
        path: meta.sourcePath,
        error: err.message || String(err)
      });
    }
  }
}
