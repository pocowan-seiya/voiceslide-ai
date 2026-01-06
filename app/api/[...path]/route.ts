import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = 'http://localhost:8001';

type RouteContext = {
    params: Promise<{ path: string[] }>;
};

export async function GET(
    request: NextRequest,
    context: RouteContext
) {
    const { path } = await context.params;
    const pathString = path.join('/');
    const url = new URL(request.url);
    const targetUrl = `${BACKEND_URL}/api/${pathString}${url.search}`;

    try {
        // Forward API keys from headers
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
        };

        const openaiKey = request.headers.get('x-openai-key');
        const geminiKey = request.headers.get('x-gemini-key');
        if (openaiKey) headers['x-openai-key'] = openaiKey;
        if (geminiKey) headers['x-gemini-key'] = geminiKey;

        const response = await fetch(targetUrl, { headers });

        // Check content type for binary files (video, audio, download)
        const contentType = response.headers.get('content-type') || '';
        const isBinary = contentType.includes('video/') ||
            contentType.includes('audio/') ||
            contentType.includes('application/octet-stream') ||
            pathString.includes('download');

        if (isBinary) {
            // Stream binary file directly
            const responseHeaders = new Headers();
            response.headers.forEach((value, key) => {
                responseHeaders.set(key, value);
            });

            return new NextResponse(response.body, {
                status: response.status,
                headers: responseHeaders
            });
        }

        const data = await response.json();
        return NextResponse.json(data, { status: response.status });
    } catch (error) {
        console.error('Proxy error:', error);
        return NextResponse.json(
            { error: 'Backend connection failed' },
            { status: 502 }
        );
    }
}

export async function POST(
    request: NextRequest,
    context: RouteContext
) {
    const { path } = await context.params;
    const pathString = path.join('/');
    const url = new URL(request.url);
    const targetUrl = `${BACKEND_URL}/api/${pathString}${url.search}`;

    try {
        const contentType = request.headers.get('content-type') || '';
        let body: BodyInit | undefined;
        let headers: HeadersInit = {};

        // Forward API keys from headers
        const openaiKey = request.headers.get('x-openai-key');
        const geminiKey = request.headers.get('x-gemini-key');
        if (openaiKey) headers['x-openai-key'] = openaiKey;
        if (geminiKey) headers['x-gemini-key'] = geminiKey;

        if (contentType.includes('multipart/form-data')) {
            // Handle file uploads - pass through FormData
            body = await request.formData();
        } else if (contentType.includes('application/json')) {
            // Handle JSON
            try {
                body = JSON.stringify(await request.json());
                headers['Content-Type'] = 'application/json';
            } catch {
                body = undefined;
            }
        }

        // Add timeout for long-running requests (like AI slide generation)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 minutes

        const response = await fetch(targetUrl, {
            method: 'POST',
            headers,
            body,
            signal: controller.signal,
        });

        clearTimeout(timeoutId);

        const data = await response.json();
        return NextResponse.json(data, { status: response.status });
    } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
            console.error('Proxy timeout: Request took too long');
            return NextResponse.json(
                { error: 'Request timeout - operation took too long' },
                { status: 504 }
            );
        }
        console.error('Proxy error:', error);
        return NextResponse.json(
            { error: 'Backend connection failed' },
            { status: 502 }
        );
    }
}

export async function DELETE(
    request: NextRequest,
    context: RouteContext
) {
    const { path } = await context.params;
    const pathString = path.join('/');
    const targetUrl = `${BACKEND_URL}/api/${pathString}`;

    try {
        const headers: HeadersInit = {};
        const openaiKey = request.headers.get('x-openai-key');
        const geminiKey = request.headers.get('x-gemini-key');
        if (openaiKey) headers['x-openai-key'] = openaiKey;
        if (geminiKey) headers['x-gemini-key'] = geminiKey;

        const response = await fetch(targetUrl, {
            method: 'DELETE',
            headers,
        });

        const data = await response.json();
        return NextResponse.json(data, { status: response.status });
    } catch (error) {
        console.error('Proxy error:', error);
        return NextResponse.json(
            { error: 'Backend connection failed' },
            { status: 502 }
        );
    }
}
