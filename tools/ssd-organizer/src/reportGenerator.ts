import * as fs from 'fs';
import * as path from 'path';
import { OrganizeStats, OrganizeOptions } from './types.js';

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

export function formatDuration(ms: number): string {
  const seconds = Math.floor((ms / 1000) % 60);
  const minutes = Math.floor((ms / (1000 * 60)) % 60);
  const hours = Math.floor(ms / (1000 * 60 * 60));

  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Prints a clean, formatted report directly to the terminal
 */
export function printTerminalReport(stats: OrganizeStats, options: OrganizeOptions): void {
  const duration = (stats.endTime || Date.now()) - stats.startTime;

  console.log('\n======================================================');
  console.log(options.dryRun ? ' 🔍 DRY-RUN PREVIEW COMPLETE' : ' ✅ ORGANIZATION COMPLETE');
  console.log('======================================================');
  console.log(`📁 Input Sources:         ${options.inputDirs.join('\n                          ')}`);
  console.log(`📂 Output Destination:    ${options.outputDir}`);
  console.log(`⚡ Execution Mode:        ${options.dryRun ? 'Dry-Run (Simulated, no files touched)' : options.action.toUpperCase()}`);
  console.log(`⏱️ Duration:              ${formatDuration(duration)}`);
  console.log('------------------------------------------------------');
  console.log(`📊 Total Files Scanned:   ${stats.totalScanned.toLocaleString()}`);
  console.log(`📸 Media Files Found:     ${stats.mediaFiles.toLocaleString()}`);
  console.log(`⏭️ Non-Media Skipped:     ${stats.nonMediaSkipped.toLocaleString()}`);
  console.log(`📍 Geotagged Locations:   ${stats.withLocation.toLocaleString()} photos (${stats.mediaFiles > 0 ? ((stats.withLocation / stats.mediaFiles) * 100).toFixed(1) : 0}%)`);
  console.log(`📅 Date-only (No GPS):    ${stats.withoutLocation.toLocaleString()} photos`);
  console.log(`👯 Duplicates Detected:   ${stats.duplicatesFound.toLocaleString()} files`);
  console.log(`💾 Duplicate Size Saved:  ${formatBytes(stats.duplicateBytesSaved)}`);
  console.log(`📦 Files to Organize:     ${stats.organizedCount.toLocaleString()}`);

  if (stats.errors.length > 0) {
    console.log(`⚠️ Errors Encountered:     ${stats.errors.length}`);
  }

  // Top locations
  const topLocations = Object.entries(stats.byLocation)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  if (topLocations.length > 0) {
    console.log('\n📍 Top Locations Identified:');
    for (const [loc, count] of topLocations) {
      console.log(`   • ${loc.padEnd(30)}: ${count.toLocaleString()} photos`);
    }
  }

  // Timeline preview (last 5 months)
  const timeline = Object.entries(stats.byYearMonth)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-8);

  if (timeline.length > 0) {
    console.log('\n📅 Timeline Sample:');
    for (const [ym, count] of timeline) {
      const bar = '█'.repeat(Math.min(30, Math.ceil(count / 10)));
      console.log(`   ${ym} | ${bar} ${count}`);
    }
  }

  console.log('======================================================\n');
}

/**
 * Generates an interactive HTML summary report that can be opened in any browser
 */
export async function generateHtmlReport(
  stats: OrganizeStats,
  options: OrganizeOptions,
  reportPath: string
): Promise<void> {
  const duration = (stats.endTime || Date.now()) - stats.startTime;

  const topLocations = Object.entries(stats.byLocation)
    .sort((a, b) => b[1] - a[1]);

  const timeline = Object.entries(stats.byYearMonth)
    .sort((a, b) => a[0].localeCompare(b[0]));

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SSD Memory Ingestion Report</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --primary: #38bdf8;
      --success: #34d399;
      --warning: #fbbf24;
      --accent: #818cf8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); padding: 2rem; }
    .container { max-width: 1100px; margin: 0 auto; }
    header { margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }
    .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
    .badge-dry { background: rgba(251, 191, 36, 0.2); color: var(--warning); border: 1px solid var(--warning); }
    .badge-exec { background: rgba(52, 211, 153, 0.2); color: var(--success); border: 1px solid var(--success); }
    h1 { font-size: 2rem; margin-top: 0.5rem; color: #fff; }
    .meta-sub { color: var(--muted); margin-top: 0.25rem; font-size: 0.95rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }
    .card-title { font-size: 0.85rem; text-transform: uppercase; color: var(--muted); letter-spacing: 0.05em; }
    .card-value { font-size: 1.85rem; font-weight: 700; color: #fff; margin-top: 0.5rem; }
    .card-sub { font-size: 0.8rem; color: var(--muted); margin-top: 0.25rem; }
    .section { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }
    .section h2 { font-size: 1.25rem; margin-bottom: 1rem; color: var(--primary); display: flex; align-items: center; gap: 0.5rem; }
    .table-container { max-height: 400px; overflow-y: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th { padding: 0.75rem 1rem; background: #0f172a; color: var(--muted); font-size: 0.85rem; position: sticky; top: 0; }
    td { padding: 0.75rem 1rem; border-top: 1px solid var(--border); font-size: 0.9rem; }
    .bar-wrap { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; font-size: 0.85rem; }
    .bar-label { width: 80px; color: var(--muted); font-family: monospace; }
    .bar-outer { flex: 1; background: #0f172a; border-radius: 4px; height: 20px; overflow: hidden; }
    .bar-inner { height: 100%; background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 4px; }
    .bar-count { width: 50px; text-align: right; color: #fff; font-weight: 600; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <span class="badge ${options.dryRun ? 'badge-dry' : 'badge-exec'}">
        ${options.dryRun ? '🔍 Dry-Run Simulation' : '✅ Active ' + options.action.toUpperCase()}
      </span>
      <h1>SSD Memory Ingestion Report</h1>
      <p class="meta-sub">Sources: ${options.inputDirs.join(' | ')} ➔ ${options.outputDir}</p>
      <p class="meta-sub">Execution Time: ${formatDuration(duration)} | Generated: ${new Date().toLocaleString()}</p>
    </header>

    <div class="grid">
      <div class="card">
        <div class="card-title">Media Files Found</div>
        <div class="card-value">${stats.mediaFiles.toLocaleString()}</div>
        <div class="card-sub">${stats.totalScanned.toLocaleString()} total files scanned</div>
      </div>
      <div class="card">
        <div class="card-title">Location Tagged</div>
        <div class="card-value">${stats.withLocation.toLocaleString()}</div>
        <div class="card-sub">${stats.mediaFiles > 0 ? ((stats.withLocation / stats.mediaFiles) * 100).toFixed(1) : 0}% of photos have GPS</div>
      </div>
      <div class="card">
        <div class="card-title">Duplicates Found</div>
        <div class="card-value" style="color: var(--warning);">${stats.duplicatesFound.toLocaleString()}</div>
        <div class="card-sub">${formatBytes(stats.duplicateBytesSaved)} reclaimable space</div>
      </div>
      <div class="card">
        <div class="card-title">Organized Vault</div>
        <div class="card-value" style="color: var(--success);">${stats.organizedCount.toLocaleString()}</div>
        <div class="card-sub">Categorized into Year/Month/City</div>
      </div>
    </div>

    <div class="section">
      <h2>📍 Top Identified Locations & Trips</h2>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Location</th>
              <th>Photos</th>
              <th>Percentage</th>
            </tr>
          </thead>
          <tbody>
            ${topLocations.map(([loc, count]) => `
              <tr>
                <td><strong>${loc}</strong></td>
                <td>${count.toLocaleString()}</td>
                <td>${stats.withLocation > 0 ? ((count / stats.withLocation) * 100).toFixed(1) : 0}%</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>📅 Monthly Timeline Distribution</h2>
      <div style="max-height: 400px; overflow-y: auto; padding-right: 0.5rem;">
        ${timeline.map(([ym, count]) => {
          const maxCount = Math.max(...timeline.map(t => t[1])) || 1;
          const pct = ((count / maxCount) * 100).toFixed(1);
          return `
            <div class="bar-wrap">
              <span class="bar-label">${ym}</span>
              <div class="bar-outer">
                <div class="bar-inner" style="width: ${pct}%"></div>
              </div>
              <span class="bar-count">${count}</span>
            </div>
          `;
        }).join('')}
      </div>
    </div>
  </div>
</body>
</html>`;

  await fs.promises.mkdir(path.dirname(reportPath), { recursive: true });
  await fs.promises.writeFile(reportPath, html, 'utf8');
}
