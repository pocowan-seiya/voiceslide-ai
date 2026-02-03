/**
 * Node.js Puppeteer-based HTML Renderer
 * 
 * Usage: node node_renderer.js <html_file_path> <output_png_path> [width] [height]
 * 
 * This script renders HTML to PNG using Puppeteer with minimal memory footprint.
 * Optimizations:
 * - Single browser instance reused across renders (launch once)
 * - Headless mode with minimal Chrome args
 * - Page creation is lightweight (~30MB vs Playwright's ~100MB per page)
 */

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

// Default dimensions matching current slide setup
const DEFAULT_WIDTH = 1600;
const DEFAULT_HEIGHT = 900;

// Browser instance (reused for efficiency)
let browser = null;

async function initBrowser() {
    if (!browser) {
        browser = await puppeteer.launch({
            headless: 'new',
            args: [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-default-apps',
                '--mute-audio',
                '--single-process',  // Reduces memory overhead
                '--disable-web-security'  // Allow local file access
            ]
        });
        console.error('[Puppeteer] Browser launched (lightweight mode)');
    }
    return browser;
}

async function renderHtmlToImage(htmlPath, outputPath, width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT) {
    try {
        const browser = await initBrowser();
        const page = await browser.newPage();

        // Set viewport
        await page.setViewport({ width, height });

        // Load HTML file
        const absolutePath = path.resolve(htmlPath);
        await page.goto(`file://${absolutePath}`, { waitUntil: 'networkidle0' });

        // Wait a bit for fonts and rendering
        await new Promise(resolve => setTimeout(resolve, 500));

        // Screenshot
        await page.screenshot({
            path: outputPath,
            type: 'png',
            fullPage: false
        });

        await page.close();

        console.log(JSON.stringify({
            success: true,
            output: outputPath,
            dimensions: { width, height }
        }));

        return true;

    } catch (error) {
        console.error(JSON.stringify({
            success: false,
            error: error.message,
            stack: error.stack
        }));
        process.exit(1);
    }
}

async function cleanup() {
    if (browser) {
        await browser.close();
        browser = null;
    }
}

// CLI interface
if (require.main === module) {
    const args = process.argv.slice(2);

    if (args.length < 2) {
        console.error('Usage: node node_renderer.js <html_file> <output_png> [width] [height]');
        process.exit(1);
    }

    const [htmlPath, outputPath, widthArg, heightArg] = args;
    const width = widthArg ? parseInt(widthArg) : DEFAULT_WIDTH;
    const height = heightArg ? parseInt(heightArg) : DEFAULT_HEIGHT;

    renderHtmlToImage(htmlPath, outputPath, width, height)
        .then(() => cleanup())
        .catch(err => {
            console.error(err);
            cleanup();
            process.exit(1);
        });
}

module.exports = { renderHtmlToImage, initBrowser, cleanup };
