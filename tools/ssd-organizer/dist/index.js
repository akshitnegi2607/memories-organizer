#!/usr/bin/env node
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
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const commander_1 = require("commander");
const scanner_js_1 = require("./scanner.js");
const reportGenerator_js_1 = require("./reportGenerator.js");
// Prevent Node 25 GC file descriptor edge case from aborting large batch jobs
process.on('uncaughtException', (err) => {
    if (err && err.code === 'ERR_INVALID_STATE') {
        return; // Safely ignore closed FileHandle GC warning in Node 25
    }
    console.error('⚠️ Uncaught Exception:', err);
});
const program = new commander_1.Command();
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
    const rawInputs = Array.isArray(opts.input) ? opts.input : [opts.input];
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
    const options = {
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
        const stats = await (0, scanner_js_1.runIngestion)(options, (msg) => {
            console.log(msg);
        });
        // Terminal summary
        (0, reportGenerator_js_1.printTerminalReport)(stats, options);
        // HTML Report
        if (opts.report) {
            const reportPath = path.join(outputDir, 'organize_summary.html');
            await (0, reportGenerator_js_1.generateHtmlReport)(stats, options, reportPath);
            console.log(`📄 Visual HTML Report saved: ${reportPath}`);
            console.log('   Open this file in Safari or Chrome to inspect the complete breakdown!\n');
        }
    }
    catch (err) {
        console.error(`❌ Ingestion failed: ${err.message}`);
        process.exit(1);
    }
});
program.parse(process.argv);
