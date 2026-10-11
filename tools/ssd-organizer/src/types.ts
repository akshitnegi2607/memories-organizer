export interface GeoLocation {
  city: string;
  region?: string;
  country: string;
  distanceKm: number;
}

export interface PhotoMetadata {
  sourcePath: string;
  fileName: string;
  fileSize: number;
  extension: string;
  
  // Date detection
  date: Date;
  dateSource: 'exif' | 'filename' | 'filesystem';
  
  // Location detection
  latitude?: number;
  longitude?: number;
  location?: GeoLocation;
  
  // Duplicate detection
  hash?: string;
  isDuplicate?: boolean;
  duplicateOf?: string;
  
  // Target organization
  targetDir: string;
  targetFileName: string;
  targetPath: string;
}

export interface OrganizeOptions {
  inputDirs: string[];
  outputDir: string;
  dryRun: boolean;
  action: 'copy' | 'move';
  dedup: boolean;
  geo: boolean;
  verbose: boolean;
}

export interface CityData {
  name: string;
  region?: string;
  country: string;
  lat: number;
  lng: number;
}

export interface OrganizeStats {
  totalScanned: number;
  mediaFiles: number;
  nonMediaSkipped: number;
  duplicatesFound: number;
  duplicateBytesSaved: number;
  withLocation: number;
  withoutLocation: number;
  organizedCount: number;
  errors: { path: string; error: string }[];
  byYearMonth: Record<string, number>;
  byLocation: Record<string, number>;
  startTime: number;
  endTime?: number;
}
