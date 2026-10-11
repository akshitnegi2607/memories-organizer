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
exports.runIngestion = runIngestion;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const exifExtractor_js_1 = require("./exifExtractor.js");
const deduplicator_js_1 = require("./deduplicator.js");
const fileOrganizer_js_1 = require("./fileOrganizer.js");
async function runIngestion(options, onProgress) {
    const stats = {
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
    const deduplicator = new deduplicator_js_1.FastDeduplicator();
    const mediaPaths = [];
    // Step 1: Fast directory crawl & file size indexing
    if (onProgress)
        onProgress('🔍 Phase 1/3: Crawling source directory and indexing file sizes...');
    async function crawlDirectory(dir) {
        let entries;
        try {
            entries = await fs.promises.readdir(dir, { withFileTypes: true });
        }
        catch (err) {
            stats.errors.push({ path: dir, error: `Directory read error: ${err.message}` });
            return;
        }
        for (const entry of entries) {
            const fullPath = path.join(dir, entry.name);
            // Skip hidden files/directories (like .DS_Store, .Trash, etc.)
            if (entry.name.startsWith('.'))
                continue;
            if (entry.isDirectory()) {
                await crawlDirectory(fullPath);
            }
            else if (entry.isFile()) {
                stats.totalScanned++;
                if ((0, exifExtractor_js_1.isSupportedMedia)(fullPath)) {
                    stats.mediaFiles++;
                    mediaPaths.push(fullPath);
                    if (options.dedup) {
                        try {
                            const fileStat = await fs.promises.stat(fullPath);
                            deduplicator.registerFile(fullPath, fileStat.size);
                        }
                        catch {
                            // Skip if stat fails
                        }
                    }
                }
                else {
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
            if (onProgress)
                onProgress(`📂 Scanning directory: ${dir}`);
            await crawlDirectory(dir);
        }
        else {
            stats.errors.push({ path: dir, error: 'Directory does not exist' });
        }
    }
    if (onProgress) {
        onProgress(`✅ Phase 1 complete: Found ${stats.mediaFiles.toLocaleString()} media files across ${stats.totalScanned.toLocaleString()} items.`);
    }
    // Step 2: Deduplication Analysis
    if (options.dedup && stats.mediaFiles > 0) {
        if (onProgress)
            onProgress('👯 Phase 2/3: Checking for duplicate photos and videos...');
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
    if (onProgress)
        onProgress(`📦 Phase 3/3: Extracting dates, locations, and organizing ${stats.mediaFiles.toLocaleString()} files...`);
    const usedTargetPaths = new Set();
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
                await fs.promises.writeFile(path.join(options.outputDir, 'progress.json'), JSON.stringify(progressData, null, 2), 'utf8');
            }
            catch {
                // ignore progress write error
            }
        }
        try {
            const meta = await (0, exifExtractor_js_1.extractMetadata)(filePath, options.geo);
            if (options.dedup && deduplicator.isDuplicate(filePath)) {
                meta.isDuplicate = true;
                meta.duplicateOf = deduplicator.getOriginal(filePath);
            }
            await (0, fileOrganizer_js_1.organizeFile)(meta, options, stats, usedTargetPaths);
        }
        catch (err) {
            stats.errors.push({
                path: filePath,
                error: `Processing error: ${err.message}`
            });
        }
    }
    stats.endTime = Date.now();
    return stats;
}
