/**
 * Node.js HTML-to-Image Renderer
 * 
 * Usage: node node_renderer.js <html_file_path> <output_png_path> [width] [height]
 * 
 * This script renders HTML to PNG using html-to-image library,
 * providing a lightweight alternative to Playwright (~50MB vs ~500MB per process)
 */

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');
const { toPng } = require('html-to-image');

// Default dimensions matching current slide setup
const DEFAULT_WIDTH = 1600;
const DEFAULT_HEIGHT = 900;

async function renderHtmlToImage(htmlPath, outputPath, width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT) {
    try {
        // Read HTML content
        const htmlContent = fs.readFileSync(htmlPath, 'utf-8');

        // Create virtual DOM
        const dom = new JSDOM(htmlContent, {
            runScripts: 'outside-only',
            resources: 'usable',
            pretendToBeVisual: true
        });

        const document = dom.window.document;
        const body = document.body;

        // Set viewport size
        body.style.width = `${width}px`;
        body.style.height = `${height}px`;
        body.style.margin = '0';
        body.style.padding = '0';
        body.style.overflow = 'hidden';

        // Wait for fonts and images to load
        await new Promise(resolve => setTimeout(resolve, 500));

        // Generate PNG
        const dataUrl = await toPng(body, {
            width: width,
            height: height,
            backgroundColor: '#1a1a2e',  // Default dark background
            pixelRatio: 1,
            quality: 0.95
        });

        // Convert data URL to buffer and save
        const base64Data = dataUrl.replace(/^data:image\/png;base64,/, '');
        const buffer = Buffer.from(base64Data, 'base64');
        fs.writeFileSync(outputPath, buffer);

        console.log(JSON.stringify({
            success: true,
            output: outputPath,
            dimensions: { width, height }
        }));

        dom.window.close();
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

    renderHtmlToImage(htmlPath, outputPath, width, height);
}

module.exports = { renderHtmlToImage };
