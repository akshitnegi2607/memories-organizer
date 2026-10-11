"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.planTargetPath = planTargetPath;
exports.organizeFile = organizeFile;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const geoCoder_js_1 = require("./geoCoder.js");
const MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
];
/**
 * Calculates target folder and file path based on date, location, and duplicate status
 */
function planTargetPath(meta, outputBaseDir, isDuplicate = false) {
    const d = meta.date;
    const year = d.getFullYear().toString();
    const monthNumber = (d.getMonth() + 1).toString().padStart(2, '0');
    const monthName = MONTH_NAMES[d.getMonth()];
    const day = d.getDate().toString().padStart(2, '0');
    const hours = d.getHours().toString().padStart(2, '0');
    const minutes = d.getMinutes().toString().padStart(2, '0');
    const seconds = d.getSeconds().toString().padStart(2, '0');
    let subfolderName;
    if (isDuplicate) {
        subfolderName = path.join('_Duplicates', year, `${year}-${monthNumber}_${monthName}`);
    }
    else if (meta.location) {
        const locTag = (0, geoCoder_js_1.sanitizeFolderName)(`${meta.location.city}_${meta.location.country}`);
        subfolderName = path.join(year, `${year}-${monthNumber}_${monthName}_${locTag}`);
    }
    else {
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
async function organizeFile(meta, options, stats, usedPaths) {
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
    }
    else {
        stats.withoutLocation++;
    }
    if (isDuplicate) {
        stats.duplicatesFound++;
        stats.duplicateBytesSaved += meta.fileSize;
    }
    else {
        stats.organizedCount++;
    }
    // Perform physical copy or move if not in dry-run mode
    if (!options.dryRun) {
        try {
            await fs.promises.mkdir(targetDir, { recursive: true });
            if (options.action === 'move') {
                await fs.promises.rename(meta.sourcePath, finalPath);
            }
            else {
                await fs.promises.copyFile(meta.sourcePath, finalPath);
            }
        }
        catch (err) {
            stats.errors.push({
                path: meta.sourcePath,
                error: err.message || String(err)
            });
        }
    }
}
