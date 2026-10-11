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
exports.FastDeduplicator = void 0;
exports.computeFileHash = computeFileHash;
const fs = __importStar(require("fs"));
const crypto = __importStar(require("crypto"));
/**
 * Computes SHA-256 hash of a file or chunk
 */
async function computeFileHash(filePath, sampleSize) {
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
class FastDeduplicator {
    sizeMap = new Map();
    duplicates = new Map(); // duplicatePath -> originalPath
    duplicateBytes = 0;
    /**
     * Register a file's size during initial directory traversal
     */
    registerFile(filePath, size) {
        if (size <= 0)
            return;
        const existing = this.sizeMap.get(size);
        if (existing) {
            existing.push(filePath);
        }
        else {
            this.sizeMap.set(size, [filePath]);
        }
    }
    /**
     * Analyze all registered files and resolve true duplicates
     * @param onProgress optional callback for progress updates
     */
    async analyzeDuplicates(onProgress) {
        // Filter to only sizes that have 2 or more files
        const candidateGroups = [];
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
            const partialHashMap = new Map();
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
                    }
                    else {
                        partialHashMap.set(partialHash, [file]);
                    }
                }
                catch {
                    // File read error, skip
                }
            }
            // For matching partial hashes, verify with full SHA-256
            for (const [, matchingFiles] of partialHashMap.entries()) {
                if (matchingFiles.length <= 1)
                    continue;
                const fullHashMap = new Map();
                for (const file of matchingFiles) {
                    try {
                        const fullHash = await computeFileHash(file);
                        if (fullHashMap.has(fullHash)) {
                            const original = fullHashMap.get(fullHash);
                            this.duplicates.set(file, original);
                            this.duplicateBytes += group.size;
                        }
                        else {
                            fullHashMap.set(fullHash, file);
                        }
                    }
                    catch {
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
    isDuplicate(filePath) {
        return this.duplicates.has(filePath);
    }
    getOriginal(filePath) {
        return this.duplicates.get(filePath);
    }
}
exports.FastDeduplicator = FastDeduplicator;
