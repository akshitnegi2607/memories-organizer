import { test } from 'node:test';
import * as assert from 'node:assert';
import * as fs from 'fs';
import * as path from 'path';
import { reverseGeocode, calculateHaversineDistance, sanitizeFolderName } from '../src/geoCoder.js';
import { parseDateFromFileName } from '../src/exifExtractor.js';
import { planTargetPath } from '../src/fileOrganizer.js';
import { FastDeduplicator } from '../src/deduplicator.js';
import { runIngestion } from '../src/scanner.js';
import { PhotoMetadata } from '../src/types.js';

test('calculateHaversineDistance calculates accurate distance', () => {
  // Distance between London (51.5074, -0.1278) and Paris (48.8566, 2.3522) is ~343 km
  const dist = calculateHaversineDistance(51.5074, -0.1278, 48.8566, 2.3522);
  assert.ok(dist > 330 && dist < 360, `Expected ~343 km, got ${dist}`);
});

test('reverseGeocode identifies major world cities correctly', () => {
  // Test London
  const london = reverseGeocode(51.5074, -0.1278);
  assert.ok(london);
  assert.strictEqual(london.city, 'London');
  assert.strictEqual(london.country, 'United Kingdom');

  // Test Paris
  const paris = reverseGeocode(48.8566, 2.3522);
  assert.ok(paris);
  assert.strictEqual(paris.city, 'Paris');
  assert.strictEqual(paris.country, 'France');

  // Test New York
  const ny = reverseGeocode(40.7128, -74.0060);
  assert.ok(ny);
  assert.strictEqual(ny.city, 'New York');
  assert.strictEqual(ny.country, 'USA');

  // Test Mumbai
  const mumbai = reverseGeocode(19.0760, 72.8777);
  assert.ok(mumbai);
  assert.strictEqual(mumbai.city, 'Mumbai');
  assert.strictEqual(mumbai.country, 'India');

  // Test invalid coordinates
  assert.strictEqual(reverseGeocode(NaN, NaN), null);
});

test('sanitizeFolderName strips illegal characters', () => {
  assert.strictEqual(sanitizeFolderName('Paris: City of Lights / France?'), 'Paris_City_of_Lights_France');
});

test('parseDateFromFileName extracts timestamps from camera roll naming conventions', () => {
  // Pattern 1: Camera roll
  const d1 = parseDateFromFileName('IMG_20230815_143022.jpg');
  assert.ok(d1);
  assert.strictEqual(d1.getFullYear(), 2023);
  assert.strictEqual(d1.getMonth(), 7); // August (0-indexed)
  assert.strictEqual(d1.getDate(), 15);
  assert.strictEqual(d1.getHours(), 14);

  // Pattern 2: WhatsApp
  const d2 = parseDateFromFileName('WhatsApp Image 2022-04-10 at 14.22.10.jpeg');
  assert.ok(d2);
  assert.strictEqual(d2.getFullYear(), 2022);
  assert.strictEqual(d2.getMonth(), 3); // April
  assert.strictEqual(d2.getDate(), 10);

  // Pattern 3: Date only
  const d3 = parseDateFromFileName('Photo_2021-11-25.png');
  assert.ok(d3);
  assert.strictEqual(d3.getFullYear(), 2021);
  assert.strictEqual(d3.getMonth(), 10); // November
  assert.strictEqual(d3.getDate(), 25);
});

test('planTargetPath formats monthly and location folders neatly', () => {
  const meta: PhotoMetadata = {
    sourcePath: '/tmp/test.jpg',
    fileName: 'IMG_1024.jpg',
    fileSize: 1024,
    extension: '.jpg',
    date: new Date(2023, 7, 15, 14, 30, 22),
    dateSource: 'exif',
    location: {
      city: 'Paris',
      country: 'France',
      distanceKm: 2
    },
    targetDir: '',
    targetFileName: '',
    targetPath: ''
  };

  const plan = planTargetPath(meta, '/output');
  assert.strictEqual(plan.targetDir, path.join('/output', '2023', '2023-08_August_Paris_France'));
  assert.strictEqual(plan.targetFileName, '2023-08-15_14-30-22_IMG_1024.jpg');

  // Duplicate plan
  const dupePlan = planTargetPath(meta, '/output', true);
  assert.strictEqual(dupePlan.targetDir, path.join('/output', '_Duplicates', '2023', '2023-08_August'));
});

test('FastDeduplicator accurately detects exact duplicates without unnecessary disk reads', async () => {
  const tmpDir = path.join('/tmp', `dedup_test_${Date.now()}`);
  fs.mkdirSync(tmpDir, { recursive: true });

  const fileA = path.join(tmpDir, 'fileA.txt');
  const fileB = path.join(tmpDir, 'fileB.txt'); // Exact copy of A
  const fileC = path.join(tmpDir, 'fileC.txt'); // Different content, same size
  const fileD = path.join(tmpDir, 'fileD.txt'); // Different size

  fs.writeFileSync(fileA, 'Hello world memory test 123456');
  fs.writeFileSync(fileB, 'Hello world memory test 123456');
  fs.writeFileSync(fileC, 'Different content same len 123'); // same byte length 30
  fs.writeFileSync(fileD, 'Short');

  const dedup = new FastDeduplicator();
  dedup.registerFile(fileA, fs.statSync(fileA).size);
  dedup.registerFile(fileB, fs.statSync(fileB).size);
  dedup.registerFile(fileC, fs.statSync(fileC).size);
  dedup.registerFile(fileD, fs.statSync(fileD).size);

  const result = await dedup.analyzeDuplicates();
  assert.strictEqual(result.duplicateCount, 1);
  assert.strictEqual(dedup.isDuplicate(fileB), true);
  assert.strictEqual(dedup.isDuplicate(fileC), false);
  assert.strictEqual(dedup.isDuplicate(fileD), false);

  fs.rmSync(tmpDir, { recursive: true, force: true });
});

test('End-to-End Ingestion run (Dry-Run and Execute)', async () => {
  const fixtureBase = path.join('/tmp', `memories_test_${Date.now()}`);
  const inputDir = path.join(fixtureBase, 'input');
  const outputDir = path.join(fixtureBase, 'output');
  fs.mkdirSync(inputDir, { recursive: true });

  // Create sample photos with filenames indicating dates
  const sample1 = path.join(inputDir, 'IMG_20230815_143022.jpg');
  const sample1Dupe = path.join(inputDir, 'IMG_20230815_143022_copy.jpg');
  const sample2 = path.join(inputDir, 'WhatsApp Image 2022-04-10 at 14.22.10.jpeg');
  const nonMedia = path.join(inputDir, 'notes.txt');

  const content1 = Buffer.alloc(1024, 'a');
  fs.writeFileSync(sample1, content1);
  fs.writeFileSync(sample1Dupe, content1); // exact duplicate
  fs.writeFileSync(sample2, Buffer.alloc(2048, 'b'));
  fs.writeFileSync(nonMedia, 'Not a photo');

  // Test 1: Dry Run
  const dryStats = await runIngestion({
    inputDirs: [inputDir],
    outputDir,
    dryRun: true,
    action: 'copy',
    dedup: true,
    geo: true,
    verbose: false
  });

  assert.strictEqual(dryStats.mediaFiles, 3);
  assert.strictEqual(dryStats.nonMediaSkipped, 1);
  assert.strictEqual(dryStats.duplicatesFound, 1);
  assert.strictEqual(fs.existsSync(outputDir), false); // No files created during dry run!

  // Test 2: Active Copy with multiple input folders
  const secondInputDir = path.join(fixtureBase, 'input2');
  fs.mkdirSync(secondInputDir, { recursive: true });
  const sampleCrossDupe = path.join(secondInputDir, 'cross_folder_dupe.jpg');
  fs.writeFileSync(sampleCrossDupe, content1); // duplicate of sample1 in a different folder!

  const execStats = await runIngestion({
    inputDirs: [inputDir, secondInputDir],
    outputDir,
    dryRun: false,
    action: 'copy',
    dedup: true,
    geo: true,
    verbose: false
  });

  // sample1 + sample2 = 2 unique, sample1Dupe + sampleCrossDupe = 2 duplicates across folders!
  assert.strictEqual(execStats.organizedCount, 2);
  assert.strictEqual(execStats.duplicatesFound, 2);
  assert.strictEqual(fs.existsSync(outputDir), true);

  // Clean up
  fs.rmSync(fixtureBase, { recursive: true, force: true });
});
