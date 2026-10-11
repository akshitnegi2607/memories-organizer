#!/usr/bin/env node
import * as path from 'path';
import * as fs from 'fs';
import { Command } from 'commander';
import { OrganizeOptions } from './types.js';
import { runIngestion } from './scanner.js';
import { printTerminalReport, generateHtmlReport } from './reportGenerator.js';
// Prevent Node 25 GC file descriptor edge case from aborting large batch jobs
process.on('uncaughtException', (err: any) => {
  if (err && err.code === 'ERR_INVALID_STATE') {
    return; // Safely ignore closed FileHandle GC warning in Node 25
  }
  console.error('⚠️ Uncaught Exception:', err);
});

const program = new Command();

program
  .name('organize-memories')
  .description('High-speed Mac tool to organize, deduplicate, and geotag 700GB+ photo & video backups')
  .version('1.0.0')
  .requiredOption('-i, --input <paths...>', 'One or more source folders on your SSD')
  .requiredOption('-o, --output <path>', 'Destination path for organized memories')
  .option('-e, --execute', 'Perform actual copy or move (defaults to safe dry-run preview if omitted)', false)
  .option('-a, --action <type>', 'Action to perform: "copy" (safe) or "move"', 'copy')
  .option('--no-dedup', 'Skip duplicate detection')
  .option('--no-geo', 'Skip offline reverse geocoding')
  .option('--no-report', 'Skip generating HTML summary report')
  .option('-v, --verbose', 'Verbose progress output', false)
  .action(async (opts) => {
    const rawInputs: string[] = Array.isArray(opts.input) ? opts.input : [opts.input];
    const inputDirs = rawInputs.map(p => path.resolve(p));
    const outputDir = path.resolve(opts.output);
    const dryRun = !opts.execute;
    const action = opts.action === 'move' ? 'move' : 'copy';

    for (const dir of inputDirs) {
      if (!fs.existsSync(dir)) {
        console.error(`❌ Error: Source directory does not exist: ${dir}`);
        process.exit(1);
      }
    }

    const options: OrganizeOptions = {
      inputDirs,
      outputDir,
      dryRun,
      action,
      dedup: opts.dedup,
      geo: opts.geo,
      verbose: opts.verbose
    };

    console.log('\n🚀 Starting SSD Memory Organizer');
    console.log(`📁 Input Sources (${inputDirs.length}):`);
    inputDirs.forEach(d => console.log(`   • ${d}`));
    console.log(`📂 Output: ${outputDir}`);
    console.log(`🛡️ Mode:   ${dryRun ? 'DRY-RUN PREVIEW (No files will be modified)' : action.toUpperCase()}`);
    console.log(`📍 Geotag: ${opts.geo ? 'Enabled (Offline reverse geocoding)' : 'Disabled'}`);
    console.log(`👯 Dedup:  ${opts.dedup ? 'Enabled (Fast checksum)' : 'Disabled'}\n`);

    if (dryRun) {
      console.log('💡 TIP: You are running in DRY-RUN mode. When you are happy with the preview,');
      console.log('   add "--execute" to perform the actual organization!\n');
    }

    try {
      const stats = await runIngestion(options, (msg) => {
        console.log(msg);
      });

      // Terminal summary
      printTerminalReport(stats, options);

      // HTML Report
      if (opts.report) {
        const reportPath = path.join(outputDir, 'organize_summary.html');
        await generateHtmlReport(stats, options, reportPath);
        console.log(`📄 Visual HTML Report saved: ${reportPath}`);
        console.log('   Open this file in Safari or Chrome to inspect the complete breakdown!\n');
      }
    } catch (err: any) {
      console.error(`❌ Ingestion failed: ${err.message}`);
      process.exit(1);
    }
  });

program.parse(process.argv);
