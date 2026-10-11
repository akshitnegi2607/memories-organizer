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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SUPPORTED_EXTENSIONS = void 0;
exports.isSupportedMedia = isSupportedMedia;
exports.parseDateFromFileName = parseDateFromFileName;
exports.extractMetadata = extractMetadata;
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
const exifr_1 = __importDefault(require("exifr"));
const geoCoder_js_1 = require("./geoCoder.js");
exports.SUPPORTED_EXTENSIONS = new Set([
    // Photos
    '.jpg', '.jpeg', '.heic', '.heif', '.png', '.webp', '.tiff', '.tif',
    '.raw', '.dng', '.cr2', '.nef', '.arw',
    // Videos
    '.mp4', '.mov', '.m4v', '.3gp', '.avi'
]);
function isSupportedMedia(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return exports.SUPPORTED_EXTENSIONS.has(ext);
}
/**
 * Attempts to parse date patterns commonly used in camera roll filenames
 */
function parseDateFromFileName(fileName) {
    // Pattern 1: YYYYMMDD_HHMMSS or YYYYMMDD-HHMMSS (e.g. IMG_20230815_143022)
    const p1 = /(?:IMG_|VID_|PXL_|PHOTO_)?(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})/i.exec(fileName);
    if (p1) {
        const d = new Date(parseInt(p1[1]), parseInt(p1[2]) - 1, parseInt(p1[3]), parseInt(p1[4]), parseInt(p1[5]), parseInt(p1[6]));
        if (isValidDate(d))
            return d;
    }
    // Pattern 2: YYYY-MM-DD (e.g. WhatsApp Image 2022-04-10 at 14.22.10)
    const p2 = /(\d{4})-(\d{2})-(\d{2})[_\s\w]*?(\d{2})[.:](\d{2})[.:](\d{2})/i.exec(fileName);
    if (p2) {
        const d = new Date(parseInt(p2[1]), parseInt(p2[2]) - 1, parseInt(p2[3]), parseInt(p2[4]), parseInt(p2[5]), parseInt(p2[6]));
        if (isValidDate(d))
            return d;
    }
    // Pattern 3: Simple YYYYMMDD or YYYY-MM-DD
    const p3 = /(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})/.exec(fileName);
    if (p3) {
        const year = parseInt(p3[1]);
        const month = parseInt(p3[2]);
        const day = parseInt(p3[3]);
        if (year >= 1990 && year <= new Date().getFullYear() + 1 && month >= 1 && month <= 12 && day >= 1 && day <= 31) {
            const d = new Date(year, month - 1, day, 12, 0, 0);
            if (isValidDate(d))
                return d;
        }
    }
    return null;
}
function isValidDate(d) {
    if (!(d instanceof Date) || isNaN(d.getTime()))
        return false;
    const year = d.getFullYear();
    const currentYear = new Date().getFullYear();
    return year >= 1990 && year <= currentYear + 1;
}
/**
 * Extracts EXIF, GPS location, and capture date from a photo or video file
 */
async function extractMetadata(filePath, enableGeo = true) {
    const fileName = path.basename(filePath);
    const ext = path.extname(filePath).toLowerCase();
    const stats = await fs.promises.stat(filePath);
    const fileSize = stats.size;
    let date = null;
    let dateSource = 'filesystem';
    let latitude;
    let longitude;
    let location;
    // 1. Try reading EXIF metadata using explicit buffer management (prevents Node 25 GC file descriptor errors)
    if (fileSize > 0) {
        let handle = null;
        try {
            handle = await fs.promises.open(filePath, 'r');
            // Read first 512 KB which holds EXIF/XMP/GPS headers
            const bytesToRead = Math.min(fileSize, 512 * 1024);
            const buffer = Buffer.alloc(bytesToRead);
            await handle.read(buffer, 0, bytesToRead, 0);
            const exifData = await exifr_1.default.parse(buffer, {
                tiff: true,
                xmp: true,
                gps: true,
                mergeOutput: true
            });
            if (exifData) {
                // Date from EXIF
                const rawDate = exifData.DateTimeOriginal || exifData.CreateDate || exifData.ModifyDate;
                if (rawDate && isValidDate(new Date(rawDate))) {
                    date = new Date(rawDate);
                    dateSource = 'exif';
                }
                // GPS Coordinates
                if (typeof exifData.latitude === 'number' && typeof exifData.longitude === 'number') {
                    latitude = exifData.latitude;
                    longitude = exifData.longitude;
                    if (enableGeo && latitude !== undefined && longitude !== undefined) {
                        const resolved = (0, geoCoder_js_1.reverseGeocode)(latitude, longitude);
                        if (resolved) {
                            location = resolved;
                        }
                    }
                }
            }
        }
        catch {
            // Some formats or corrupt files may fail EXIF parsing; gracefully fall back
        }
        finally {
            if (handle) {
                try {
                    await handle.close();
                }
                catch {
                    // ignore
                }
            }
        }
    }
    // 2. Fallback to filename timestamp
    if (!date) {
        const fromName = parseDateFromFileName(fileName);
        if (fromName) {
            date = fromName;
            dateSource = 'filename';
        }
    }
    // 3. Fallback to file system birthtime / mtime
    if (!date) {
        const fileDate = stats.birthtime && isValidDate(stats.birthtime) && stats.birthtime.getFullYear() > 1990
            ? stats.birthtime
            : stats.mtime;
        date = isValidDate(fileDate) ? fileDate : new Date();
        dateSource = 'filesystem';
    }
    return {
        sourcePath: filePath,
        fileName,
        fileSize,
        extension: ext,
        date,
        dateSource,
        latitude,
        longitude,
        location,
        targetDir: '',
        targetFileName: '',
        targetPath: ''
    };
}
