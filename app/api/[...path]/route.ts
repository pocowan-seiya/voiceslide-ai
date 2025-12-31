import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = 'http://localhost:8001';

export async function GET(
    request: NextRequest,
    { params }: { params: { path: string[] } }
) {
    const path = params.path.join('/');
    const url = new URL(request.url);
    const targetUrl = `${BACKEND_URL}/api/${path}${url.search}`;

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
    { params }: { params: { path: string[] } }
) {
    const path = params.path.join('/');
    const url = new URL(request.url);
    const targetUrl = `${BACKEND_URL}/api/${path}${url.search}`;

    try {
        const contentType = request.headers.get('content-type') || '';
        let body;

        if (contentType.includes('multipart/form-data')) {
            // Handle file uploads
            const formData = await request.formData();
            body = formData;
        } else {
            // Handle JSON
            try {
                body = JSON.stringify(await request.json());
            } catch {
                body = undefined;
            }
        }

        const response = await fetch(targetUrl, {
            method: 'POST',
            headers: contentType.includes('multipart/form-data')
                ? {}
                : { 'Content-Type': 'application/json' },
            body: body,
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
    { params }: { params: { path: string[] } }
) {
    const path = params.path.join('/');
    const targetUrl = `${BACKEND_URL}/api/${path}`;

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
