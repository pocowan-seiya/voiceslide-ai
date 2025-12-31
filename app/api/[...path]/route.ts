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
        const response = await fetch(targetUrl, {
            headers: {
                'Content-Type': 'application/json',
            },
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

        if (contentType.includes('multipart/form-data')) {
            // Handle file uploads - pass through FormData
            body = await request.formData();
        } else if (contentType.includes('application/json')) {
            // Handle JSON
            try {
                body = JSON.stringify(await request.json());
                headers = { 'Content-Type': 'application/json' };
            } catch {
                body = undefined;
            }
        }

        const response = await fetch(targetUrl, {
            method: 'POST',
            headers,
            body,
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

export async function DELETE(
    request: NextRequest,
    context: RouteContext
) {
    const { path } = await context.params;
    const pathString = path.join('/');
    const targetUrl = `${BACKEND_URL}/api/${pathString}`;

    try {
        const response = await fetch(targetUrl, {
            method: 'DELETE',
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
